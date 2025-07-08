import { bossService } from '@/axios';
import {showMessage} from "@/composables/useElementPlus";

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
        // The backend will set the cookie on its own.
        // We just need to call this endpoint once if we suspect the user is new.
        await this.getToken();
        // console.log('Auth token refresh/initialization attempted.');
    } catch (error) {
        // console.error('Failed to initialize auth token:', error);
      showMessage.error('登入失敗');
    }
  }

  getToken() {
    return bossService.post('/token').then(res => res.data);
  }

  // 獲取 BOSS 類型
  getBossTypes() {
    return bossService.get('/boss-types').then(res => res.data);
  }

  // 記錄 BOSS 狀態
  recordBoss(data: string) {
    return bossService.post('/record-boss', data).then(res => res.data);
  }

  // 建立房間
  createRoom(roomId: string) {
    return bossService.post('/room', { room_id: roomId }).then(res => res.data);
  }

  checkRoomExists(roomId: string) {
    return bossService.get(`/room/${roomId}/exists`).then(res => res.data);
  }

  // WebSocket 連接
  createWebSocket(roomId: string) {
    return new WebSocket(`${WS_URL}/ws/${roomId}`);
  }
}

export default new ApiService();
