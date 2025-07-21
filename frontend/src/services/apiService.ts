import { bossService } from '@/axios';

const WS_URL = `wss://${import.meta.env.VITE_WS_URL}`;


class ApiService {
  constructor() {
    this.client = bossService;
  }

  // 設定認證 token
  setAuthToken(token) {
    console.log(this.client);
    this.client.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`
  }

  // 移除認證 token
  removeAuthToken() {
    delete this.client.axiosInstance.defaults.headers.common['Authorization']
  }

  // 處理 token 過期
  handleTokenExpired() {
    // 清除本地儲存
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_info')

    // 重定向到登入頁面
    window.location.href = '/'
  }

  // 驗證 token
  async validateToken(token) {
    try {
      const response = await this.client.post('/auth/validate')
      return response.data
    } catch (error) {
      return { valid: false }
    }
  }

  // --- Auth ---
  async loginWithGoogle(credential: string) {
    const response = await this.client.post('/auth/google', { credential });
    return response.data;
  }

  // 登出
  async logout() {
    const response = await this.client.post('/auth/logout')
    return response.data;
  }

  async getMe() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  async refresh_token(){
    const response = await this.client.post('auth/refresh');
    return response.data;
  }

  async updateMyPreferences(preferences: Record<string, any>) {
    const response = await this.client.put('/auth/me/preferences', preferences);
    return response.data;
  }

  // --- Boss & Room ---
  getBossTypes() {
    return this.client.get('/boss/boss-types').then(res => res.data);
  }

  recordBoss(data: any) { // Changed type to any to be more flexible
    return this.client.post('/boss/record-boss', data).then(res => res.data);
  }

  createRoom(roomId: string) {
    return this.client.post('/room/', { room_id: roomId }).then(res => res.data);
  }

  checkRoomExists(roomId: string) {
    return this.client.get(`/room/${roomId}/exists`).then(res => res.data);
  }

  // --- WebSocket ---
  createWebSocket(roomId: string) {
    // The HttpOnly cookie will be sent automatically by the browser.
    // No need to manually attach a token.
    return new WebSocket(`${WS_URL}/ws/${roomId}`);
  }

  async getMaintenanceInfo() {
    const response = await this.client.get('/system/maintenance-info');
    return response.data;
  }

  async updateMaintenanceConfig(updatedConfig: Dict<string, any>) {
    return await this.client.post('/system/maintenance-config', updatedConfig);
  }
}

export default new ApiService();
