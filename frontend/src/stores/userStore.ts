import { defineStore } from 'pinia';
import apiService, { type InitSessionResponse } from '@/services/apiService';
import { useWebSocketStore } from '@/stores/websocketStore';
import { generateRandomName } from '@/utils/anonymousName';
import { QueryObserver } from '@tanstack/vue-query';
import { queryClient } from '@/queryClient';

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
  // 帳號偏好套用到本地的次數（App.vue 據此同步各項偏好）
  preferencesVersion: number;
  _channel?: BroadcastChannel;
  _initialized: boolean;
  _initPromise?: Promise<void>;
  _resolveInit?: () => void;
  // 上次把帳號偏好套用到本地的登入者：換人時才再套用（跨裝置同步，ADR-0009）
  _preferencesUserId?: number;
  // WebSocket 握手時的身分（伺服器回答的 user:{id} / anon:{id} / none）；不確定時為 undefined
  _wsIdentity?: string;
  // 上次查詢完成後，本分頁或其他分頁登入 / 登出過（共用的登入 cookie 改變過）
  _cookieChanged: boolean;
  _logoutPromise?: Promise<void>;
}

const SESSION_QUERY_KEY = ['auth', 'session'] as const;

// 讀取共用的登入顯示快取 user_info；沒有或格式損壞時回傳 null
function readCachedUser(): User | null {
  const cached = localStorage.getItem('user_info');
  if (!cached) return null;
  try {
    return JSON.parse(cached) as User;
  } catch {
    return null;
  }
}

function identityOf(session: InitSessionResponse): string {
  if (session.status === 'authenticated') return `user:${session.user.id}`;
  return session.anonymous_user_id ? `anon:${session.anonymous_user_id}` : 'none';
}

export const useUserStore = defineStore('user', {
  state: (): UserState => ({
    user: null,
    isLoggedIn: false,
    isLoading: false,
    anonymousName: null,
    preferencesVersion: 0,
    _channel: undefined,
    _initialized: false,
    _initPromise: undefined,
    _resolveInit: undefined,
    _preferencesUserId: undefined,
    _wsIdentity: undefined,
    _cookieChanged: false,
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
          if (event.data.type !== 'LOGIN' && event.data.type !== 'LOGOUT') return;
          // 其他分頁改了共用的 cookie：不採用通知裡的狀態（可能已過時），重新問伺服器（ADR-0009）
          this._cookieChanged = true;
          void this._refetchSession();
        };
      }
    },

    notifyLogin() {
      if (this._channel) {
        // 收到的分頁會重新問伺服器、不讀 user；保留給部署切換期間仍直接套用 user 的舊版前端
        this._channel.postMessage({ type: 'LOGIN', user: JSON.parse(JSON.stringify(this.user)) });
      }
    },

    notifyLogout() {
      if (this._channel) {
        this._channel.postMessage({ type: 'LOGOUT' });
      }
    },

    // 開頁開始查詢登入狀態（ADR-0009，照 NextAuth 前端的模型）：每個分頁只有一個查詢、同時只有一個請求，
    // 開頁、切回分頁（Vue Query 的 refetchOnWindowFocus）、登入 / 登出 / 收到其他分頁通知時查詢。
    // 第一次判斷完成才連線 WebSocket，之後換頁不呼叫 connect()：斷線一律交給 websocketStore 的退避重連
    initializeAuth(): Promise<void> {
      // App.vue onMounted 與 router beforeEach 會在首次載入時同時呼叫，共用同一次初始化
      if (!this._initPromise) {
        this._initPromise = new Promise((resolve) => {
          this._resolveInit = resolve;
        });
        this.initBroadcastChannel();
        this.isLoading = true;
        const observer = new QueryObserver(queryClient, {
          queryKey: SESSION_QUERY_KEY,
          queryFn: ({ signal }) => this._fetchSession(signal),
          // 失敗時不自動重試，等下次觸發再問；離線時照樣送出（失敗就沿用目前的顯示），不要暫停到恢復連線
          retry: false,
          networkMode: 'always',
          refetchOnReconnect: false,
        });
        // 訂閱後才開始查詢，也才會在切回分頁時重新查詢
        observer.subscribe(() => {});
      }
      return this._initPromise;
    },

    // 登入 cookie 改變後重新查詢：進行中的請求是改變前送出的，取消後再問。
    // 不只用 invalidateQueries：Vue Query 在還沒有任何結果時（開頁的查詢進行中）不會取消進行中的請求
    async _refetchSession() {
      await queryClient.cancelQueries({ queryKey: SESSION_QUERY_KEY });
      await queryClient.refetchQueries({ queryKey: SESSION_QUERY_KEY });
    },

    // 每次查詢在這裡套用結果。被取消的請求（之後登入 cookie 改變過）不套用
    async _fetchSession(signal: AbortSignal): Promise<InitSessionResponse> {
      let session: InitSessionResponse;
      try {
        session = await apiService.initSession(signal);
        // 回滾到舊版後端時 authenticated 不帶 user：當作判斷失敗，沿用目前的顯示
        if (session.status === 'authenticated' && !session.user) throw new Error('Session response without user');
      } catch (error) {
        if (!signal.aborted) {
          console.error('Failed to resolve auth state:', error);
          this._applySessionFailure();
        }
        throw error;
      }
      // 在請求的錯誤處理之外套用：套用時出錯（例如 localStorage 寫不進去）不是判斷失敗，不走失敗的處理
      this._applySession(session);
      return session;
    },

    // 照伺服器的判斷設定（登入過期時伺服器會順便換發，登入失效時會清掉舊 cookie、改發匿名身分）
    _applySession(session: InitSessionResponse) {
      if (session.status === 'authenticated') {
        this._applyServerUser(session.user);
      } else {
        this.becomeAnonymous();
      }
      this._syncWebSocket(identityOf(session));
    },

    // 照伺服器回答的登入者（查詢成功或登入回應）設定。帳號偏好只在換人時（開頁、登入、換成另一個人）套用到本地：
    // 跨裝置同步是重新開頁才載入，同一個人的回答只更新帳號資料、保留這台裝置目前的偏好，
    // 不會蓋掉存檔中或還沒存的修改。查詢失敗、改用快取時不呼叫
    _applyServerUser(user: User) {
      if (this.user && user.id === this._preferencesUserId) {
        this.setLoggedInUser({ ...user, preferences: this.user.preferences });
        return;
      }
      this.setLoggedInUser(user);
      // 套用成功才記下：寫入失敗時下一次回答會再套用
      this._preferencesUserId = user.id;
      this.preferencesVersion++;
    },

    // 判斷失敗（網路錯誤、5xx、被限流）不代表登入狀態改變：沿用目前的顯示，什麼都不清除。
    // 開頁時還沒有顯示，以 user_info（顯示快取）恢復上次的狀態
    _applySessionFailure() {
      if (!this._initialized && !this.restoreUserFromStorage()) {
        this.anonymousName = this.getAnonymousName();
      }
      this._syncWebSocket(undefined);
    },

    // WebSocket 的身分在握手時依 cookie 固定。查詢成功時，伺服器回答的身分和連線用的不同才重連；
    // 查詢失敗時不知道現在的身分，期間登入 / 登出過才照目前的 cookie 重連
    _syncWebSocket(identity: string | undefined) {
      const websocketStore = useWebSocketStore();
      const cookieChanged = this._cookieChanged;
      this._cookieChanged = false;
      if (!this._initialized) {
        // 第一次判斷完成才連線：身分在握手時以 cookie 決定，必須等 /auth/session 發好匿名 cookie
        this._initialized = true;
        this.isLoading = false;
        this._wsIdentity = identity;
        websocketStore.connect();
        this._resolveInit?.();
        return;
      }
      if (identity === undefined ? cookieChanged : identity !== this._wsIdentity) {
        this._wsIdentity = identity;
        websocketStore.reconnect();
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
      await apiService.logout();
      // 伺服器已撤銷登入。先只清掉本分頁的畫面，共用的 user_info 等取得匿名身分（cookie）後才清（同時通知其他分頁）：
      // 其他分頁重新查詢時沿用這個匿名身分，原本沒有匿名 cookie 時也不會各自申請一個
      this._cookieChanged = true;
      this.user = null;
      this.isLoggedIn = false;
      if (this.anonymousName === null) this.anonymousName = this.getAnonymousName();
      await this._refetchSession();
      // 查詢成功時已照伺服器的回答設定：匿名就已清掉 user_info 並通知；仍是登入（換發與登出同時發生，ADR-0009 接受的時序）
      // 就照它顯示，與 cookie 一致。查詢失敗時照樣清掉並通知，WebSocket 已因期間登出過而照目前的 cookie 重連
      if (!this.isLoggedIn) this.becomeAnonymous();
    },

    async loginWithGoogle(payload: string | { credential?: string; code?: string }) {
      try {
        const requestPayload = typeof payload === 'string' ? { credential: payload } : payload;
        const response = await apiService.loginWithGoogle(requestPayload);
        // 登入回應已設好 cookie：先照它顯示、套用帳號偏好並通知其他分頁，再重新查詢（WebSocket 依結果換成登入身分）。
        // 偏好不等查詢：查詢失敗時本地會留著匿名時的偏好，之後存檔會蓋掉帳號的設定
        this._cookieChanged = true;
        this._applyServerUser(response.user);
        void this._refetchSession();
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
      // 先寫進這台裝置目前的偏好再存檔（各元件也是先改本地）：本地永遠是使用者最後的意思，回應先後顛倒也不會改回舊值。
      // user_info 的偏好也是這台裝置目前的偏好（同各元件存在 localStorage 的收藏、版面），一改就寫入，不等存檔結果。
      // 只在快取仍是同一個登入者時寫入：其他分頁已登出就不寫回；這不是登入者改變，不經 _writeUserInfo、不通知其他分頁
      this.user = { ...this.user, preferences: { ...this.user.preferences, ...preferences } };
      if (readCachedUser()?.id === this.user.id) localStorage.setItem('user_info', JSON.stringify(this.user));
      try {
        await apiService.updateMyPreferences(preferences);
      } catch (error) {
        console.error('Failed to update preferences:', error);
      }
    },

    setLoggedInUser(user: User) {
      this.user = user;
      this.isLoggedIn = true;
      this._writeUserInfo(user);
    },

    becomeAnonymous() {
      this.clearAuth();
      // 已經是匿名時不重新讀取：切回分頁的查詢不會把暱稱欄裡正在輸入的名字改回存的舊值
      if (this.anonymousName === null) this.anonymousName = this.getAnonymousName();
    },

    clearAuth() {
      this.user = null;
      this.isLoggedIn = false;
      this._preferencesUserId = undefined;   // 再登入時一定套用帳號的偏好
      this._writeUserInfo(null);
    },

    // user_info 是所有分頁共用的登入顯示快取。由改變顯示中的登入者的分頁通知其他分頁（ADR-0009）：
    // 變成沒有登入通知登出，變成另一個登入者（含從沒有變有）通知登入。其他分頁收到後重新查詢，
    // 套用時快取已是新的狀態，不會再通知；多個分頁同時發現登入失效（例如瀏覽器一次還原很多分頁）也只由第一個通知
    _writeUserInfo(user: User | null) {
      const cached = localStorage.getItem('user_info');
      if (user) {
        const cachedId = readCachedUser()?.id;
        localStorage.setItem('user_info', JSON.stringify(user));
        if (cachedId !== user.id) this.notifyLogin();
      } else {
        localStorage.removeItem('user_info');
        if (cached !== null) this.notifyLogout();
      }
    },

    // 以 localStorage 的 user_info 恢復登入狀態；沒有或格式損壞時回傳 false
    restoreUserFromStorage(): boolean {
      const cached = readCachedUser();
      if (!cached) return false;
      this.user = cached;
      this.isLoggedIn = true;
      return true;
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