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

type RefreshResult = 'refreshed' | 'rejected' | 'unavailable';

interface UserState {
  user: User | null;
  isLoggedIn: boolean;
  isLoading?: boolean;
  anonymousName: string | null;
  _channel?: BroadcastChannel;
  _initialized: boolean;
  _initPromise?: Promise<void>;
  _logoutPromise?: Promise<void>;
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
    _logoutPromise: undefined,
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
        await this._resolveLogin();
      } catch (error) {
        // 失敗（被限流、網路錯誤、5xx）不代表登入失效：曾登入過的使用者以 user_info 保留登入（見 _resolveLogin）
        console.error('Auth initialization failed:', error);
        if (!this.restoreUserFromStorage()) {
          this.becomeAnonymous();
        }
      } finally {
        this.isLoading = false;
        this._initialized = true;
        websocketStore.connect();
      }
    },

    /**
     * 決定登入狀態。曾登入過（有 user_info）的使用者只有兩種情況會變匿名：伺服器明確拒絕換發
     * （tryRefreshToken 回 rejected）或使用者登出。其他任何失敗都保留登入：refresh token 仍有效，
     * WebSocket 握手也會以它認出登入者，畫面改顯示匿名就會不一致；而且刪掉 user_info 後，之後的載入不會再嘗試換發。
     */
    async _resolveLogin() {
      // 確保有伺服器簽發的匿名身分 cookie（已登入時不發放）
      await apiService.initSession();
      const res = await apiService.validateToken();
      if (res.valid) {
        this.setLoggedInUser(res.user);
        return;
      }
      if (!localStorage.getItem('user_info')) {
        this.becomeAnonymous();
        return;
      }
      const refresh = await this.tryRefreshToken();
      if (refresh === 'rejected') {
        await this.discardStaleLogin();
        return;
      }
      const revalidated = refresh === 'refreshed' ? await apiService.validateToken() : undefined;
      if (revalidated?.valid) {
        this.setLoggedInUser(revalidated.user);
      } else {
        this.restoreUserFromStorage();
      }
    },

    // 嘗試用 refresh token 換新的 access token：
    // - 'rejected'：refresh token 無效（401），或被限流（429）——後端以 refresh token 裡的使用者計算額度，
    //   被限流代表前端多半陷入 refresh 迴圈，視為換發失敗並登出，迴圈才會停下
    // - 'unavailable'：其他失敗（網路錯誤、5xx 等），不能確定登入已失效，不可登出（會撤銷 30 天的登入）
    async tryRefreshToken(): Promise<RefreshResult> {
      try {
        await apiService.refresh_token();
        return 'refreshed';
      } catch (error) {
        const status = isAxiosError(error) ? error.response?.status : undefined;
        return status === 401 || status === 429 ? 'rejected' : 'unavailable';
      }
    },

    // 換發失敗、改以匿名使用前，盡力清掉舊的登入 cookie：refresh cookie 還在時 /auth/session 不發匿名身分，
    // WebSocket 握手也會以它判斷為登入者，與畫面上的匿名狀態不一致
    async discardStaleLogin() {
      // 先清本地登入狀態：之後的 initSession 失敗時，_runInitializeAuth 的 catch 才不會以 user_info 恢復成登入
      this.becomeAnonymous();
      try {
        await apiService.logout();
      } catch (error) {
        console.warn('Failed to clear stale login cookies:', error);
      }
      try {
        await apiService.initSession();
      } finally {
        // 撤銷的是所有分頁共用的 refresh token：通知其他分頁一起改為匿名並重連（取得匿名身分後再通知）
        this.notifyLogout();
      }
    },

    // 只有 /auth/logout 成功才算登出：HttpOnly cookie 前端清不掉。失敗時什麼都不動（維持登入、不廣播、不重連），
    // 錯誤往外丟給呼叫端提示
    logout(): Promise<void> {
      // 進行中再呼叫（例如連點登出）就共用同一次，不並行跑兩次完整流程
      if (!this._logoutPromise) {
        this._logoutPromise = this._runLogout().finally(() => {
          this._logoutPromise = undefined;
        });
      }
      return this._logoutPromise;
    },

    async _runLogout() {
      const websocketStore = useWebSocketStore();
      await apiService.logout();
      this.becomeAnonymous();
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

    setLoggedInUser(user: User | null | undefined) {
      this.user = user ?? null;
      this.isLoggedIn = true;
      localStorage.setItem('user_info', JSON.stringify(user));
    },

    becomeAnonymous() {
      this.clearAuth();
      this.anonymousName = this.getAnonymousName();
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