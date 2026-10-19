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

// 讀取共用的登入顯示快取 user_info 的原始字串；讀不到時當作沒有
function readCachedUserRaw(): string | null {
  try {
    return localStorage.getItem('user_info');
  } catch {
    return null;
  }
}

// 解析 user_info；沒有或格式損壞時回傳 null
function parseCachedUser(raw: string | null): User | null {
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === 'object' && parsed !== null && typeof (parsed as User).id === 'number' ? parsed as User : null;
  } catch {
    return null;
  }
}

function readCachedUser(): User | null {
  return parseCachedUser(readCachedUserRaw());
}

// 寫入 user_info，回傳是否成功。它只是顯示快取，寫不進去（例如空間滿了）時忽略，不中斷登入狀態的處理
function writeCachedUser(user: User | null): boolean {
  try {
    if (user) localStorage.setItem('user_info', JSON.stringify(user));
    else localStorage.removeItem('user_info');
    return true;
  } catch (error) {
    console.error('Failed to write user_info:', error);
    return false;
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
          void this.resyncAfterCookieChange();
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
        // 同一台裝置的其他分頁改了同一個登入者的偏好（user_info 的偏好一改就寫入）：跟著更新，例如「顯示擊殺紀錄」
        // （CONTEXT.md「跨裝置同步」）。登入者改變不在這裡處理，由通知與查詢處理
        window.addEventListener('storage', (event) => {
          if (event.storageArea !== localStorage || event.key !== 'user_info' || !this.user) return;
          const cached = parseCachedUser(event.newValue);
          if (cached?.id === this.user.id) this.user = { ...this.user, preferences: cached.preferences };
        });
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

    // 登入 cookie 改變了（登入、登出、其他分頁通知）：不在前端自己判斷，重新問伺服器（ADR-0009）
    resyncAfterCookieChange(): Promise<void> {
      this._cookieChanged = true;
      return this._refetchSession();
    },

    // 使用中途遇到 401：需要登入的 API 在 access token 過期時會自己換發，401 代表伺服器已判斷登入失效（ADR-0009），
    // 不再確認，照登出的順序處理。回傳是否當成登入失效處理：同時好幾個 401 只有第一個會處理
    handleLoginLost(): boolean {
      // 其他分頁剛登入 / 登出（例如在其他分頁按了登出）、正在重新查詢：401 是預期中的結果，交給查詢結果處理
      if (this._cookieChanged) return false;
      if (!this.isLoggedIn) {
        // 顯示為匿名，卻仍帶著失效的登入 cookie（例如開頁查詢失敗）：重新查詢讓 /auth/session 清掉，之後的請求才不會一直 401
        void this._refetchSession();
        return false;
      }
      void this._clearLoginAfterResync();
      return true;
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
      // 回應到了但請求已被取消（之後登入 cookie 改變過）：不套用
      if (signal.aborted) throw new Error('Session request cancelled');
      // 在請求的錯誤處理之外套用：套用時出錯不是判斷失敗，不走失敗的處理
      this._applySession(session);
      return session;
    },

    // 照伺服器的判斷設定（登入過期時伺服器會順便換發，登入失效時會清掉舊 cookie、改發匿名身分）
    _applySession(session: InitSessionResponse) {
      try {
        if (session.status === 'authenticated') {
          this._applyServerUser(session.user);
        } else {
          this.becomeAnonymous();
        }
      } finally {
        // 套用出錯也要完成初始化、處理 WebSocket，否則路由守衛一直等 initializeAuth()、頁面空白
        this._syncWebSocket(identityOf(session));
      }
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
      try {
        if (!this._initialized && !this.restoreUserFromStorage()) {
          this.anonymousName = this.getAnonymousName();
        }
      } finally {
        this._syncWebSocket(undefined);
      }
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
      await this._clearLoginAfterResync();
    },

    // 登出成功或登入失效後：先只清掉本分頁的畫面，共用的 user_info 等取得匿名身分（cookie）後才清（同時通知其他分頁）。
    // 其他分頁重新查詢時沿用這個匿名身分，原本沒有匿名 cookie 時也不會各自申請一個
    async _clearLoginAfterResync() {
      this.user = null;
      this.isLoggedIn = false;
      this._ensureAnonymousName();
      await this.resyncAfterCookieChange();
      // 查詢成功時已照伺服器的回答設定：匿名就已清掉 user_info 並通知；仍是登入（換發與登出同時發生，ADR-0009 接受的時序）
      // 就照它顯示，與 cookie 一致。查詢失敗時照樣清掉並通知，WebSocket 已因期間登出過而照目前的 cookie 重連
      if (!this.isLoggedIn) this.becomeAnonymous();
    },

    async loginWithGoogle(payload: string | { credential?: string; code?: string }) {
      try {
        const requestPayload = typeof payload === 'string' ? { credential: payload } : payload;
        const response = await apiService.loginWithGoogle(requestPayload);
        // 登入回應已設好 cookie：先標記 cookie 改變過並開始重新查詢（套用出錯也不會遺失標記；請求在取消舊查詢後才送出），
        // 再照登入回應顯示、套用帳號偏好並通知其他分頁，WebSocket 依查詢結果換成登入身分。
        // 偏好不等查詢：查詢失敗時本地會留著匿名時的偏好，之後存檔會蓋掉帳號的設定
        const resync = this.resyncAfterCookieChange();
        this._applyServerUser(response.user);
        void resync;
      } catch (error) {
        // 登入失敗不動登入狀態（登入按鈕只在未登入時顯示），交給呼叫端提示
        console.error('Google login failed:', error);
        throw error;
      }
    },

    async updatePreferences(preferences: Record<string, unknown>) {
      if (!this.user) return;
      // 先寫進這台裝置目前的偏好再存檔（各元件也是先改本地）：本地永遠是使用者最後的意思，回應先後顛倒也不會改回舊值。
      // user_info 的偏好也是這台裝置目前的偏好（同各元件存在 localStorage 的收藏、版面），一改就寫入，不等存檔結果。
      // 只在快取仍是同一個登入者時寫入：其他分頁已登出就不寫回；這不是登入者改變，不經 _writeUserInfo、不通知其他分頁
      this.user = { ...this.user, preferences: { ...this.user.preferences, ...preferences } };
      if (readCachedUser()?.id === this.user.id) writeCachedUser(this.user);
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
      this.user = null;
      this.isLoggedIn = false;
      this._preferencesUserId = undefined;   // 再登入時一定套用帳號的偏好
      this._writeUserInfo(null);
      this._ensureAnonymousName();
    },

    // 已經是匿名時不重新讀取：切回分頁的查詢不會把暱稱欄裡正在輸入的名字改回存的舊值
    _ensureAnonymousName() {
      if (this.anonymousName === null) this.anonymousName = this.getAnonymousName();
    },

    // user_info 是所有分頁共用的登入顯示快取。由改變顯示中的登入者的分頁通知其他分頁（ADR-0009）：
    // 變成沒有登入通知登出，變成另一個登入者（含從沒有變有）通知登入。其他分頁收到後重新查詢，
    // 套用時快取已是新的狀態，不會再通知；多個分頁同時發現登入失效（例如瀏覽器一次還原很多分頁）也只由第一個通知
    _writeUserInfo(user: User | null) {
      const raw = readCachedUserRaw();
      // 寫不進去時不通知：快取沒變，其他分頁查詢後也會寫不進去而再通知，分頁之間會互相觸發。它們靠切回分頁時的查詢修正
      if (!writeCachedUser(user)) return;
      if (user) {
        if (parseCachedUser(raw)?.id !== user.id) this.notifyLogin();
      } else if (raw !== null) {
        this.notifyLogout();
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