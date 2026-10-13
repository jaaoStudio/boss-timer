import { defineStore } from 'pinia';
import { isAxiosError } from 'axios';
import apiService from '@/services/apiService';
import { useWebSocketStore } from '@/stores/websocketStore';
import { generateRandomName } from '@/utils/anonymousName';

export interface User {
  id: number;
  display_name: string | null;
  avatar_url: string | null;
  preferences: Record<string, unknown>;
  is_admin: boolean;
}

interface UserState {
  user: User | null;
  isLoggedIn: boolean;
  isLoading?: boolean;
  anonymousName: string | null;
  _channel?: BroadcastChannel;
  _initialized: boolean;
  _initPromise?: Promise<void>;
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    user: null,
    isLoggedIn: false,
    isLoading: false,
    anonymousName: null,
    _channel: undefined,
    _initialized: false,
    _initPromise: undefined,
  }),
  getters: {
    isAdmin(): boolean {
      return this.user ? this.user.is_admin : false;
    },
  },

  actions: {
    // 初始化 Broadcast Channel
    initBroadcastChannel() {
      if (typeof window !== 'undefined' && window.BroadcastChannel && !this._channel) {
        this._channel = new BroadcastChannel('user-auth');
        this._channel.onmessage = (event) => {
          if (event.data.type === 'LOGOUT') {
            this.clearAuth();
          } else if (event.data.type === 'LOGIN') {
            this.user = event.data.user;
            this.isLoggedIn = true;
          } else {
            return;
          }
          // cookie 已由該分頁更新；WebSocket 的身分由握手時的 cookie 決定，重連才會換成新身分
          useWebSocketStore().reconnect();
        };
      }
    },

    notifyLogin() {
      if (this._channel) {
        this._channel.postMessage({ type: 'LOGIN', user: JSON.parse(JSON.stringify(this.user)) });
      }
    },

    notifyLogout() {
      if (this._channel) {
        this._channel.postMessage({ type: 'LOGOUT' });
      }
    },

    async initializeAuth() {
      // 只在第一次初始化並建立 WebSocket 連線（_runInitializeAuth 的 finally）。之後路由切換不再呼叫 connect()：
      // 斷線一律交給 websocketStore 的退避重連（同 Socket.IO 只連一次），換頁時呼叫會繞過退避
      if (this._initialized) return;

      // App.vue onMounted 與 router beforeEach 會在首次載入時「同時」呼叫此方法，
      // 而 _initialized 要等 await 全部跑完才在 finally 翻成 true，
      // 不去重的話兩邊都會各打一次 /auth/session 與 /auth/validate。
      // 用 in-flight promise 讓併發呼叫共用同一次初始化流程。
      if (!this._initPromise) {
        this._initPromise = this._runInitializeAuth();
      }
      return this._initPromise;
    },

    async _runInitializeAuth() {
      const websocketStore = useWebSocketStore();
      this.initBroadcastChannel();
      this.isLoading = true;
      try {
        // 確保有伺服器簽發的匿名身分 cookie（已登入時不發放）
        await apiService.initSession();

        let res = await apiService.validateToken();


        if (!res.valid && localStorage.getItem('user_info')) {
          const refreshed = await this.tryRefreshToken();
          if (refreshed) {
            res = await apiService.validateToken();
          } else {
            await this.discardStaleLogin();
          }
        }

        if (res.valid) {
          this.user = res.user ?? null;
          this.isLoggedIn = true;
          localStorage.setItem('user_info', JSON.stringify(res.user));
        } else {
          this.clearAuth();
          this.anonymousName = this.getAnonymousName();
        }
      } catch (error) {
        console.error('Auth initialization failed:', error);
        // 被限流（例如同 IP 有人狂打導致 IP 天花板滿）不代表登入失效，token 仍然有效；
        // 保留本地的登入資訊，否則已登入的使用者會因為別人被登出。
        if (!(isAxiosError(error) && error.response?.status === 429 && this.restoreUserFromStorage())) {
          this.clearAuth();
          this.anonymousName = this.getAnonymousName();
        }
      } finally {
        this.isLoading = false;
        this._initialized = true;
        websocketStore.connect();
      }
    },

    // 嘗試用 refresh token 換新的 access token。
    // 成功回傳 true；任何失敗（無 refresh cookie / 已過期 / 被限流）回傳 false，
    // 由 axios interceptor 處理後續導向與提示。被限流也不恢復登入狀態：此時 validate 已回 valid:false，
    // 恢復的話畫面顯示已登入、WebSocket 卻以過期的 cookie 連成匿名。
    async tryRefreshToken(): Promise<boolean> {
      try {
        await apiService.refresh_token();
        return true;
      } catch {
        return false;
      }
    },

    // 換發失敗、改以匿名使用前，盡力清掉舊的登入 cookie：refresh cookie 還在時 /auth/session 不發匿名身分，
    // WebSocket 握手也會以它判斷為登入者，與畫面上的匿名狀態不一致
    async discardStaleLogin() {
      try {
        await apiService.logout();
      } catch (error) {
        console.warn('Failed to clear stale login cookies:', error);
      }
      await apiService.initSession();
    },

    // 只有 /auth/logout 成功才算登出：HttpOnly cookie 前端清不掉。失敗時什麼都不動（維持登入、不廣播、不重連），
    // 錯誤往外丟給呼叫端提示
    async logout() {
      const websocketStore = useWebSocketStore();
      await apiService.logout();
      this.clearAuth();
      this.anonymousName = this.getAnonymousName();
      try {
        // 登出後恢復匿名：先向伺服器取得匿名身分（cookie），其他分頁與 WebSocket 才能以它重連
        await apiService.initSession();
      } catch (error) {
        console.error('Failed to start anonymous session after logout:', error);
      } finally {
        // 即使取得匿名身分失敗也要通知其他分頁並重連，否則 WebSocket 會停留在登入身分。
        // 伺服器已撤銷 refresh token，重連後會是匿名（或無身分）
        this.notifyLogout();
        websocketStore.reconnect();
      }
    },

    async loginWithGoogle(payload: string | { credential?: string; code?: string }) {
      const websocketStore = useWebSocketStore();
      try {
        const requestPayload = typeof payload === 'string' ? { credential: payload } : payload;
        const response = await apiService.loginWithGoogle(requestPayload);
        this.user = response.user;
        this.isLoggedIn = true;
        localStorage.setItem('user_info', JSON.stringify(response.user));

        // 登入回應已設好 access_token cookie；WebSocket 身分由握手時的 cookie 決定，重連即換成登入身分
        websocketStore.reconnect();

        this.notifyLogin();

      } catch (error) {
        // 登入失敗不動登入狀態（登入按鈕只在未登入時顯示），交給呼叫端提示
        console.error('Google login failed:', error);
        throw error;
      }
    },

    async fetchUser() {
      try {
        this.user = await apiService.getMe();
      } catch (error) {
        this.user = null;
      }
    },

    async updatePreferences(preferences: Record<string, unknown>) {
      if (!this.user) return;
      try {
        this.user = await apiService.updateMyPreferences(preferences);
      } catch (error) {
        console.error('Failed to update preferences:', error);
      }
    },

    clearAuth() {
      this.user = null;
      this.isLoggedIn = false;
      localStorage.removeItem('user_info');
    },

    // 以 localStorage 的 user_info 恢復登入狀態；沒有或格式損壞時回傳 false
    restoreUserFromStorage(): boolean {
      const cached = localStorage.getItem('user_info');
      if (!cached) return false;
      try {
        this.user = JSON.parse(cached) as User;
        this.isLoggedIn = true;
        return true;
      } catch {
        return false;
      }
    },

    // --- Anonymous User Name Logic ---
    setAnonymousName(name: string) {
      if (this.validateNickname(name)) {
        this.anonymousName = name;
        localStorage.setItem('anonymous_name', name);
      } else {
        // 或者可以拋出錯誤或顯示提示
        console.warn("Invalid anonymous name provided.");
      }
    },

    getAnonymousName(): string {
      const storedName = localStorage.getItem('anonymous_name');
      if (this.validateNickname(storedName)) {
        return storedName!;
      }
      const locale = localStorage.getItem('language') ?? 'zh';
      const randomName = generateRandomName(locale);
      localStorage.setItem('anonymous_name', randomName);
      return randomName;
    },

    rerollAnonymousName(locale: string = 'zh'): void {
      const newName = generateRandomName(locale);
      this.anonymousName = newName;
      localStorage.setItem('anonymous_name', newName);
    },

    validateNickname(name: string | null): boolean {
      if (!name) return false;
      if (name.length > 20) return false;
      return true;
    },
  },
});