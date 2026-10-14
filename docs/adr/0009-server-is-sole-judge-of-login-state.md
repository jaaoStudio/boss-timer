---
status: accepted
---

# 登入狀態由伺服器唯一判斷

前端開頁時原本自己判斷登入狀態：先打 `/auth/session` 取得匿名身分，再打 `/auth/validate`；`valid:false` 且 localStorage 有 `user_info` 時呼叫 `/auth/refresh` 換發，再驗證一次，並依各步驟的失敗類型（401、429、網路錯誤、5xx）決定保留登入、改為匿名或清掉舊 cookie。登入狀態因此有四個來源——`user_info`、validate、refresh、WebSocket 握手時伺服器依 cookie 的判斷——每多處理一種失敗，就多一個與伺服器判斷不一致的可能。PR #58 連續三輪審查都在這段找到新問題（#59）。

我們決定**登入狀態只由伺服器判斷**：開頁只呼叫一次 `POST /auth/session`，它直接回答「你是誰」，前端照結果設定，不再自己換發或重新驗證。

- 登入有效 → `{ status: "authenticated", user }`。access token 過期、refresh token 有效時，伺服器順便換發 access token cookie。
- 有登入 cookie 但登入已失效（refresh token 無效、被撤銷，或使用者已刪除）→ 伺服器清掉舊的登入 cookie，改以匿名回應 `{ status: "anonymous", anonymous_user_id }`（沿用或發放匿名身分）。撞到匿名身分發放上限時不回 429，回 `anonymous_user_id: null`（暫時沒有身分），舊登入照樣清掉，畫面才與伺服器一致。
- 登入者的判斷（access token 且使用者存在 → refresh token 查資料庫確認未撤銷）與 WebSocket 握手共用 `resolve_login()`，兩邊不會判斷出不同結果。
- 呼叫失敗（網路錯誤、5xx、429）不代表登入狀態改變：前端沿用上次的顯示（`user_info` 只當顯示快取），什麼都不清除。
- 原本顯示已登入、被判定為匿名時，前端廣播 `LOGOUT`：伺服器清掉的是所有分頁共用的登入 cookie。
- 額度：`/auth/session` 的個人額度依序以 access token 的使用者、refresh token 裡的使用者計算，不退回 IP，同 IP 的人不會互相擋到（ADR-0007）。

## Considered Options

- **前端自己判斷，逐一處理失敗類型（修改前的做法）**：每種失敗都要決定保留或登出，且結果要與 WebSocket 握手（伺服器依 cookie）一致；refresh token 仍有效時畫面顯示匿名、握手卻認出登入者，或反過來。補一種情況又冒出下一種，PR #58 因此無法收斂。
- **`/auth/validate` 改成也接受 refresh token**：判斷集中到伺服器，但開頁仍要先打 `/auth/session` 再打 validate，換發與清 cookie 的副作用要放進一個「查詢」端點，還要維持「永遠回 200」的契約；不如讓本來就在開頁呼叫、會設 cookie 的 `/auth/session` 一次做完。

## Consequences

- `/auth/session` 不再只是「發匿名身分」，會換發 access token、清掉失效的登入 cookie。勿把換發或清 cookie 的判斷搬回前端。
- `/auth/validate` 只供部署切換期間的舊版前端，新前端不呼叫，日後刪除（#63）。`/auth/refresh` 保留給使用中途遇到 401 的自動換發（interceptor，#60）。
- 前端開頁只有一次請求，判斷失敗時以 `user_info` 顯示上次的狀態：這段期間畫面可能與伺服器不一致，直到下次開頁；WebSocket 仍依 cookie 由伺服器判斷，回報記錄者不受影響。
- 初始化進行中收到其他分頁的 `LOGOUT`、而本頁的 `/auth/session` 已先判斷為登入時，畫面會顯示登入直到下次開頁（極少發生，我們接受）；WebSocket 在初始化結束時才以當時的 cookie 連線，身分正確。
