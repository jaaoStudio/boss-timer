---
status: accepted
---

# 登入狀態由伺服器唯一判斷

前端開頁時原本自己判斷登入狀態：先打 `/auth/session` 取得匿名身分，再打 `/auth/validate`；`valid:false` 且 localStorage 有 `user_info` 時呼叫 `/auth/refresh` 換發，再驗證一次，並依各步驟的失敗類型（401、429、網路錯誤、5xx）決定保留登入、改為匿名或清掉舊 cookie。登入狀態因此有四個來源——`user_info`、validate、refresh、WebSocket 握手時伺服器依 cookie 的判斷——每多處理一種失敗，就多一個與伺服器判斷不一致的可能。PR #58 連續三輪審查都在這段找到新問題（#59）。

我們決定**登入狀態只由伺服器判斷**：開頁只呼叫一次 `POST /auth/session`，它直接回答「你是誰」，前端照結果設定，不再自己換發或重新驗證。

- 登入有效 → `{ status: "authenticated", user }`。access token 過期、refresh token 有效時，伺服器順便換發 access token cookie。
- 有登入 cookie 但登入已失效（refresh token 無效、被撤銷，或使用者已刪除）→ 伺服器清掉舊的登入 cookie，改以匿名回應 `{ status: "anonymous", anonymous_user_id }`（沿用或發放匿名身分）。撞到匿名身分發放上限時不回 429，回 `anonymous_user_id: null`（暫時沒有身分），舊登入照樣清掉，畫面才與伺服器一致。
- 有登入 cookie 就照「登入已失效」處理，不先檢查 token 能否解開：編造的 cookie 在撞到發放上限時拿到 `anonymous_user_id: null` 而不是 429，但沒有身分、仍以 IP 限流，繞過也得不到任何額度。若只認能解開的 token，解不開的 cookie 撞到上限時回 429、前端沿用上次的登入顯示，畫面就與伺服器不一致。
- 登入者的判斷（access token 且使用者存在 → refresh token 查資料庫確認未撤銷）與 WebSocket 握手共用 `resolve_login()`，兩邊不會判斷出不同結果。
- 呼叫失敗（網路錯誤、5xx、429）不代表登入狀態改變：前端沿用上次的顯示（`user_info` 只當顯示快取），什麼都不清除。
- **跨分頁通知的時機只有三種**：在某個分頁登入 → 廣播 `LOGIN`；在某個分頁登出 → 廣播 `LOGOUT`；開頁時原本顯示登入、被判定為匿名（登入已失效，例如在其他裝置登入或過期，使用者沒按登出）→ 伺服器清掉的是所有分頁共用的登入 cookie，當作登出廣播 `LOGOUT`。
- **跨分頁同步也問伺服器**（照 NextAuth 的做法）：收到其他分頁的 `LOGIN` / `LOGOUT` 時不採用通知裡的狀態，而是重新呼叫 `/auth/session`、照結果設定並重連 WebSocket。所有分頁共用同一組 cookie，且可能有好幾個請求同時在改它，通知裡的狀態可能已過時；以伺服器對當下 cookie 的判斷為準，各分頁才會一致。送出 `/auth/session` 後登入 cookie 改變過（本分頁或其他分頁登入 / 登出），回應（含失敗）就是改變前的結果，再問一次。重新判斷是背景請求，失敗時不跳轉頁面、不提示，沿用目前的顯示。
- 額度：`/auth/session` 的個人額度依序以 access token 的使用者、refresh token 裡的使用者計算，不退回 IP，同 IP 的人不會互相擋到（ADR-0007）。

## Considered Options

- **跨分頁通知直接套用狀態，初始化期間收到時沿用通知、不套用回應**：曾在 PR #64 實作，但瀏覽器仍會套用過時回應的 Set-Cookie（例如 A 開頁換發 access token 的回應晚於 B 登出才到，又把 cookie 放回去），所有分頁顯示匿名、伺服器卻認為登入；補一個時序特例又冒出下一個，改為一律重新問伺服器。
- **前端自己判斷，逐一處理失敗類型（修改前的做法）**：每種失敗都要決定保留或登出，且結果要與 WebSocket 握手（伺服器依 cookie）一致；refresh token 仍有效時畫面顯示匿名、握手卻認出登入者，或反過來。補一種情況又冒出下一種，PR #58 因此無法收斂。
- **`/auth/validate` 改成也接受 refresh token**：判斷集中到伺服器，但開頁仍要先打 `/auth/session` 再打 validate，換發與清 cookie 的副作用要放進一個「查詢」端點，還要維持「永遠回 200」的契約；不如讓本來就在開頁呼叫、會設 cookie 的 `/auth/session` 一次做完。

## Consequences

- `/auth/session` 不再只是「發匿名身分」，會換發 access token、清掉失效的登入 cookie。勿把換發或清 cookie 的判斷搬回前端。
- `/auth/validate` 只供部署切換期間的舊版前端，新前端不呼叫，日後刪除（#63）。`/auth/refresh` 保留給使用中途遇到 401 的自動換發（interceptor，#60）。
- 前端開頁只有一次請求，判斷失敗時以 `user_info` 顯示上次的狀態：這段期間畫面可能與伺服器不一致，直到下次開頁；WebSocket 仍依 cookie 由伺服器判斷，回報記錄者不受影響。
- 每次登入 / 登出，其他每個分頁各多呼叫一次 `/auth/session`（個人額度 60/min，足夠）。
- **兩個分頁的請求同時在改共用的 cookie 時，瀏覽器照最晚到的回應設定，前端無法阻止；我們接受這類時序，只保證各分頁最後顯示的狀態與 cookie 一致**（常見的登入套件如 NextAuth 也是如此）。勿為此加跨分頁上鎖或「期間收到通知就不廣播」等特例（後者曾在 PR #64 加入，反而讓下面「失效判斷 vs 登入」時剛登入的分頁一直顯示登入）。
  - 失效判斷與登入幾乎同時發生時（A 開頁確認一個已失效的舊登入，使用者同時在 C 登入），A 的回應晚到會刪掉 C 剛拿到的登入 cookie；A 照常廣播 `LOGOUT`，所有分頁顯示未登入，使用者重新登入即可。
  - 換發與登出幾乎同時發生時（例如 A 的 `/auth/session` 正以 refresh token 換發 access token，B 同時登出），伺服器本身可能在登出之後把 access token cookie 設回去：重新判斷時各分頁會照它顯示登入，登出的那個分頁顯示匿名。這是伺服器端的先後順序，極少發生，最晚在該 access token 30 分鐘到期、或下次開頁時修正，我們接受。
- 初始化進行中收到通知時，等初始化的判斷重新問過才連線 WebSocket，不會連續握手兩次。
