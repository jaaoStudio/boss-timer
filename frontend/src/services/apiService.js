import { bossService } from '@/axios';

const WS_URL = `wss://boss-timer.jaao.tw/api`;

class ApiService {
  // 獲取 BOSS 類型
  getBossTypes() {
    return bossService.get('/boss-types').then(res => res.data);
  }

  // 記錄 BOSS 狀態
  recordBoss(data) {
    return bossService.post('/record-boss', data).then(res => res.data);
  }

  // 獲取房間歷史
  getRoomHistory(roomId, bossName = null, limit = 50) {
    const params = { limit };
    if (bossName) params.boss_name = bossName;
    return bossService.get(`/room/${roomId}/history`, { params }).then(res => res.data);
  }

  // 建立房間
  createRoom(roomId) {
    return bossService.post('/room', { room_id: roomId }).then(res => res.data);
  }

  checkRoomExists(roomId) {
    return bossService.get(`/room/${room_id}/exists`).then(res => res.data);
  }

  // WebSocket 連接
  createWebSocket(roomId) {
    return new WebSocket(`${WS_URL}/ws/${roomId}`);
  }
}

export default new ApiService();
