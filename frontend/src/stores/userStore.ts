import {defineStore} from 'pinia';
import apiService from '@/services/apiService';
import ApiService from "@/services/apiService";
import {showMessage} from "@/composables/useElementPlus";
import { useAppInfoStore} from "@/stores/appInfo";
import { useWebSocketStore } from '@/stores/websocketStore';

interface User {
  id: number;
  display_name: string | null;
  avatar_url: string | null;
  preferences: { [key: string]: any };
  is_admin: boolean;
  anonymousId: string | null;
  anonymousName: string | null;
}

interface UserState {
  user: User | null;
  token: string | null;
  isLoggedIn: boolean;
  isLoading?: boolean;
  _channel?: BroadcastChannel;
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    user: null,
    token: null,
    isLoggedIn: false,
    isLoading: false,
    _channel: undefined,
    anonymousId: null,
    anonymousName: null,
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
      this.initBroadcastChannel();
      this.isLoading = true;
      try {
        const res = await apiService.validateToken();
        if (res.valid) {
          this.user = res.user;
          this.isLoggedIn = true;
          localStorage.setItem('user_info', JSON.stringify(res.user));
        } else {
          this.clearAuth();
        }
        this.loadAnonymousUser();
      } catch (error) {
        console.error('Auth initialization failed:', error);
        this.clearAuth();
        this.loadAnonymousUser();
      } finally {
        this.isLoading = false;
        const websocketStore = useWebSocketStore();
        websocketStore.connect();
      }
    },

    async validateToken() {
      try {
        return await apiService.validateToken();
      } catch (error) {
        return { valid: false };
      }
    },

    async logout() {
      const websocketStore = useWebSocketStore();
      try {
        // 清理本地和後端的認證狀態
        this.clearAuth();
        await apiService.logout(); 
        this.notifyLogout();

        // 建立匿名身份
        this.loadAnonymousUser();

        // 發送 deauthenticate 訊息通知 WebSocket 連線身份變更
        websocketStore.sendMessage({ type: 'deauthenticate' });

      } catch (error) {
        console.error('Logout error:', error);
      }
    },

    async loginWithGoogle(credential: string) {
      const websocketStore = useWebSocketStore();
      try {
        // 如果已登入，先登出但不發送 deauthenticate 訊息
        if (this.isLoggedIn) {
          this.clearAuth();
          await apiService.logout();
          this.notifyLogout();
        }

        const response = await apiService.loginWithGoogle(credential);
        this.user = response.user;
        this.isLoggedIn = true;
        localStorage.setItem('user_info', JSON.stringify(response.user));
        
        // 發送 authenticate 訊息，並附上新的 token
        websocketStore.sendMessage({ 
          type: 'authenticate', 
          token: response.access_token 
        });

        this.notifyLogin();

      } catch (error) {
        console.error('Google login failed:', error);
        await this.logout(); // 如果登入失敗，執行完整的登出流程
        throw error;
      }
    },

    saveAuthToStorage() {
      // This function is no longer needed for tokens, but can be kept for user_info if necessary.
      if (this.user) {
        localStorage.setItem('user_info', JSON.stringify(this.user));
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

    checkAuthConsistency() {
      // This logic might need to be re-evaluated based on the cookie-only approach.
      return true;
    },

    clearAuth() {
      this.user = null;
      this.token = null;
      this.isLoggedIn = false;
      localStorage.removeItem('user_info');
      // No need to remove auth_token from local storage anymore
    },

    loadAnonymousUser() {
      if (this.isLoggedIn) {
        return;
      }
      let storedId = localStorage.getItem('anonymous_id');
      if (!this.isValidUUID(storedId)) {
        storedId = crypto.randomUUID();
        localStorage.setItem('anonymous_id', storedId);
      }
      this.anonymousId = storedId;
      this.anonymousName = this.getAnonymousName();
    },

    setAnonymousName(name: string) {
      this.anonymousName = name;
      localStorage.setItem('anonymous_name', name);
    },

    clearAnonymousUser() {
      this.anonymousId = null;
      this.anonymousName = null;
      localStorage.removeItem('anonymous_id');
      localStorage.removeItem('anonymous_name');
    },

    getAnonymousName(): string {
      const storedName = localStorage.getItem('anonymous_name');
      if (storedName === null) return '';
      if (this.validateNickname(storedName)) return storedName;
      return '別搞QQ';
    },

    validateNickname(name: string | null): boolean {
      if (!name) return false; // 空字串或null都不合法
      if (name.length > 20) return false;
      return true;
    },

    isValidUUID(id: string | null): boolean {
      if (!id) return false;
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
      return uuidRegex.test(id);
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