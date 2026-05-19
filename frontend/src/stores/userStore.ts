import { defineStore } from 'pinia';
import apiService from '@/services/apiService';
import { useWebSocketStore } from '@/stores/websocketStore';

interface User {
  id: number;
  display_name: string | null;
  avatar_url: string | null;
  preferences: { [key: string]: any };
  is_admin: boolean;
}

interface UserState {
  user: User | null;
  isLoggedIn: boolean;
  isLoading?: boolean;
  anonymousId: string | null;
  anonymousName: string | null;
  _channel?: BroadcastChannel;
  _initialized: boolean;
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    user: null,
    isLoggedIn: false,
    isLoading: false,
    anonymousId: null,
    anonymousName: null,
    _channel: undefined,
    _initialized: false,
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
          }
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
      const websocketStore = useWebSocketStore();

      // 只在第一次進行 API 初始化，後續路由切換僅確保 WS 連線
      if (this._initialized) {
        websocketStore.connect();
        return;
      }

      this.initBroadcastChannel();
      this.isLoading = true;
      try {
        const session = await apiService.initSession();

        if (session.anonymous_user_id) {
          this.anonymousId = session.anonymous_user_id;
          localStorage.setItem('anonymous_id', session.anonymous_user_id);
        }

        const res = await apiService.validateToken();
        if (res.valid) {
          this.user = res.user;
          this.isLoggedIn = true;
          localStorage.setItem('user_info', JSON.stringify(res.user));
        } else {
          this.clearAuth();
          this.anonymousName = this.getAnonymousName();
        }
      } catch (error) {
        console.error('Auth initialization failed:', error);
        this.clearAuth();
        this.anonymousName = this.getAnonymousName();
      } finally {
        this.isLoading = false;
        this._initialized = true;
        websocketStore.connect();
      }
    },

    async logout() {
      const websocketStore = useWebSocketStore();
      try {
        // 清理本地和後端的認證狀態
        this.clearAuth();
        await apiService.logout();
        this.notifyLogout();

        // 登出後，使用者恢復匿名身份，我們需要載入他的匿名名稱
        this.anonymousName = this.getAnonymousName();

        // 發送 deauthenticate 訊息通知 WebSocket 連線身份變更
        websocketStore.sendMessage({ type: 'deauthenticate' });

      } catch (error) {
        console.error('Logout error:', error);
      }
    },

    async loginWithGoogle(payload: string | { credential?: string; code?: string }) {
      const websocketStore = useWebSocketStore();
      try {
        if (this.isLoggedIn) {
          this.clearAuth();
          await apiService.logout();
          this.notifyLogout();
        }

        const requestPayload = typeof payload === 'string' ? { credential: payload } : payload;
        const response = await apiService.loginWithGoogle(requestPayload);
        this.user = response.user;
        this.isLoggedIn = true;
        localStorage.setItem('user_info', JSON.stringify(response.user));

        websocketStore.sendMessage({
          type: 'authenticate',
          token: response.access_token
        });

        this.notifyLogin();

      } catch (error) {
        console.error('Google login failed:', error);
        await this.logout();
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

    async updatePreferences(preferences: Record<string, any>) {
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
      localStorage.setItem('anonymous_name', '一個路人');
      return '一個路人'; // 預設匿名名稱
    },

    validateNickname(name: string | null): boolean {
      if (!name) return false;
      if (name.length > 20) return false;
      return true;
    },

    async canEstablishWebSocket() {
      try {
        const currentConnections = await apiService.getWebSocketConnectionsCount();
        return currentConnections < 1000;
      } catch (error) {
        console.error('Error checking WebSocket connections:', error);
        return false;
      }
    },
  },
});