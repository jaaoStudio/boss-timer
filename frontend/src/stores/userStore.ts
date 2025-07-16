import {defineStore} from 'pinia';
import apiService from '@/services/apiService';

interface User {
  id: number;
  display_name: string | null;
  avatar_url: string | null;
  preferences: Record<string, any>;
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

  actions: {
    // 初始化 Broadcast Channel
    initBroadcastChannel() {
      if (typeof window !== 'undefined' && window.BroadcastChannel && !this._channel) {
        this._channel = new BroadcastChannel('user-auth');

        // 監聽來自其他分頁的訊息
        this._channel.onmessage = (event) => {
          if (event.data.type === 'LOGOUT') {
            // 當收到登出訊息時，清除當前分頁的狀態
            this.clearAuth();
          } else if (event.data.type === 'LOGIN') {
            // 當收到登入訊息時，更新當前分頁的狀態
            this.user = event.data.user;
            this.token = event.data.token;
            this.isLoggedIn = true;
            // 設定 API 請求的預設 header
            if (event.data.token) {
              apiService.setAuthToken(event.data.token);
            }
          }
        };
      }
    },

    // 通知其他分頁登入狀態
    notifyLogin() {
      if (this._channel) {
        this._channel.postMessage({
          type: 'LOGIN',
          user:  JSON.parse(JSON.stringify(this.user)),
          token:  JSON.parse(JSON.stringify(this.user))
        });
      }
    },

    // 通知其他分頁登出狀態
    notifyLogout() {
      if (this._channel) {
        this._channel.postMessage({
          type: 'LOGOUT'
        });
      }
    },

    // 初始化：從 localStorage 載入用戶狀態
    async initializeAuth() {
      // 確保 Broadcast Channel 已初始化
      this.initBroadcastChannel();

      this.isLoading = true;
      try {
        const storedToken = localStorage.getItem('auth_token');
        const storedUser = localStorage.getItem('user_info');

        if (storedToken && storedUser) {
          // 驗證 token 是否仍然有效
          const res = await this.validateToken(storedToken);

          if (res.valid) {
            this.token = storedToken;
            this.user = res.user;
            this.isLoggedIn = true;
            console.log("456", storedToken, storedUser);

            // 設定 API 請求的預設 header
            apiService.setAuthToken(storedToken);
          } else {
            // Token 無效，清除儲存
            console.log("123", storedToken, storedUser);
            this.logout();
          }
        }
        this.loadAnonymousUser();
      } catch (error) {
        alert('Auth initialization failed:' + error);
        this.logout();
      } finally {
        this.isLoading = false;
      }
    },

    // 驗證 token 有效性
    async validateToken(token: string) {
      try {
        // 向後端發送驗證請求
        const response = await apiService.validateToken(token);
        console.log(response);
        return response;
      } catch (error) {
        return { valid: false };
      }
    },

    async loginWithGoogle(credential: string) {
      try {
        const response = await apiService.loginWithGoogle(credential);
        this.token = response.access_token;
        this.user = response.user;
        this.isLoggedIn = true;

        // 持久化儲存
        this.saveAuthToStorage();

        // 設定 API 請求的預設 header
        apiService.setAuthToken(response.token);

        // 通知其他分頁
        this.notifyLogin();
        // this.clearAnonymousUser();

        console.log('Login successful', this.user);
      } catch (error) {
        console.error('Google login failed:', error);
        this.logout();
        throw error;
      }
    },

    // 儲存認證資訊到 localStorage
    saveAuthToStorage() {
      if (this.token && this.user) {
        localStorage.setItem('auth_token', this.token);
        localStorage.setItem('user_info', JSON.stringify(this.user));
      }
    },

    async fetchUser() {
      try {
        const userData = await apiService.getMe();
        this.user = userData;
        console.log('Fetched user data', this.user);
      } catch (error) {
        // This is expected if the user is not logged in
        this.user = null;
      }
    },

    async updatePreferences(preferences: Record<string, any>) {
      if (!this.user) return;
      try {
        const updatedUser = await apiService.updateMyPreferences(preferences);
        this.user["preferences"] = updatedUser;
        console.log('Preferences updated');
      } catch (error) {
        console.error('Failed to update preferences:', error);
      }
    },

    // 檢查身份驗證狀態一致性
    checkAuthConsistency() {
      if (typeof window !== 'undefined') {
        const token = localStorage.getItem('auth_token');
        const savedUser = localStorage.getItem('user_info');

        // 如果 store 顯示已登入，但實際上沒有有效的 token 或 user data
        if (this.isLoggedIn && (!token || !savedUser)) {
          console.log('Auth state inconsistent, logging out...');
          this.logout();
          return false;
        }

        return true;
      }
      return false;
    },

    // 清除認證資訊
    clearAuth() {
      this.user = null;
      this.token = null;
      this.isLoggedIn = false;

      // 清除 localStorage
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_info');

      // 清除 API 的 auth header
      apiService.removeAuthToken();
    },

    logout() {
      try {
        this.clearAuth();
        apiService.logout();

        // 通知其他分頁
        this.notifyLogout();
        this.loadAnonymousUser();

        console.log('User logged out');
      } catch (error) {
        console.error('Logout error:', error);
      }
    },

    loadAnonymousUser(){
      if (this.isLoggedIn){
        // this.clearAnonymousUser();
        return;
      }

      let storedId = localStorage.getItem('anonymous_id');
      if(!storedId){
        storedId = crypto.randomUUID();
        localStorage.setItem('anonymous_id', storedId);
      }
      this.anonymousId = storedId;

      const storedName = localStorage.getItem('anonymous_name');
      if(storedName){
        this.anonymousName = storedName;
      }
    },

    setAnonymousName(name){
      this.anonymousName = name;
      localStorage.setItem('anonymous_name', name);
    },

    clearAnonymousUser(){
      this.anonymousId = null;
      this.anonymousName = null;
      localStorage.removeItem('anonymous_id');
      localStorage.removeItem('anonymous_name');
    }

  },
});