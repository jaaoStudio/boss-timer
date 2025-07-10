import { bossService } from '@/axios';
import {showMessage} from "@/composables/useElementPlus";
import { useUserStore } from '@/stores/userStore';

const WS_URL = `wss://${import.meta.env.VITE_WS_URL}`;

class ApiService {
  // --- Auth ---
  async initAuth() {
    // We can't directly check for the HttpOnly cookie from JS.
    // Instead, we can have a lightweight endpoint to verify if the user is authenticated.
    // For now, we will assume the cookie is set if the user has visited before.
    // A robust implementation might have a /api/me endpoint.
    // Let's try to get a token, if it fails (e.g. due to CORS or other issues), we log it.
    try {
        // The app will set the cookie on its own.
        // We just need to call this endpoint once if we suspect the user is new.
        await this.getToken();
        // console.log('Auth token refresh/initialization attempted.');
    } catch (error) {
        console.error('Failed to initialize auth token:', error);
      showMessage.error('登入失敗');
    }
  }

  async getToken() {
    const userStore = useUserStore();
    try {
      const response = await bossService.post('auth/token');
      if (response.data.access_token) {
        userStore.setToken(response.data.access_token);
      }
      return response;
    } catch (error) {
      userStore.setToken(null);
      throw error;
    }
  }

  // 獲取 BOSS 類型
  getBossTypes() {
    return bossService.get('/boss/boss-types').then(res => res);
  }

  // 記錄 BOSS 狀態
  recordBoss(data: string) {
    return bossService.post('/boss/record-boss', data).then(res => res);
  }

  // 建立房間
  createRoom(roomId: string) {
    return bossService.post('/room/').then(res => res);
  }

  checkRoomExists(roomId: string) {
    return bossService.get(`/room/${roomId}/exists`).then(res => res);
  }

  // WebSocket 連接
  createWebSocket(roomId: string) {
    const userStore = useUserStore();
    const token = userStore.token;
    if (!token) {
      // console.error("WebSocket connection failed: No token available.");
      throw new Error("No token available for WebSocket connection.");
    }
    return new WebSocket(`${WS_URL}/ws/${roomId}?token=${token}`);
  }
}

export default new ApiService();
