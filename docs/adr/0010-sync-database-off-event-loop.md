---
status: accepted
---

# 同步的資料庫一律不在 event loop 上執行

後端用同步的 SQLAlchemy（psycopg2），但需要資料庫的 HTTP 端點全部宣告成 `async def`，並在函式裡直接查詢；WebSocket 的訊息處理也直接在 async 函式裡開 `SessionLocal()`。只有 `/auth/session` 與 WebSocket 握手特別以 `run_in_threadpool` 包起來（#59、#61）。結果是任何一個查詢變慢，整個 worker 的 event loop 都停住：所有 WebSocket 的心跳、廣播與其他 API 一起卡住，卡久了前端判定心跳逾時、所有房間一起重連。PR #78（#76）的審查發現 Google 登入也在 event loop 上呼叫沒有逾時的 `requests.post`。

我們決定**資料庫維持同步，但一律不在 event loop 上執行**（FastAPI 對同步函式庫的建議做法）：

- 不需要 `await` 的端點宣告成一般的 `def`，FastAPI 會放到 threadpool 執行。
- 需要 `await` 的端點（例如要廣播 WebSocket）與 WebSocket 的訊息處理，資料庫那段以 `run_in_threadpool` 執行。
- 呼叫外部服務（Google）的同步請求一律設逾時。
- 資料庫連線設 `connect_timeout` 與 TCP keepalive / `tcp_user_timeout`（#76），連不上或網路中斷時，執行緒最多卡幾秒，不會卡好幾分鐘。

## Considered Options

- **改用 async 的 SQLAlchemy + asyncpg**：從頭到尾都是 async，沒有 threadpool 的上限，取消與逾時比較自然。但所有 service 與端點都要改寫成 `AsyncSession` 加 `await`；async 模式不能延遲載入關聯（`record.recorder`、`record.boss_type` 這類用法漏改一處，就要等特定資料出現時才在執行期出錯，測試不一定測得到）；Celery worker 是同步的，要同時維持兩套資料庫設定與查詢寫法；測試的假 session 也要全部改。這個專案的規模（同時開著幾百個分頁、查詢都很短）用 threadpool（40 條執行緒）與連線池（30 條連線）綽綽有餘，不值得這個代價。

## Consequences

- event loop 不再被資料庫卡住；同時要等資料庫的請求數受 threadpool 與連線池限制，在目前規模不是瓶頸。
- 新增需要資料庫的端點時：不需要 `await` 就用 `def`；需要 `await` 就把資料庫那段放進 `run_in_threadpool`。勿在 `async def` 裡直接查詢。
- 連線池用盡時的等候逾時（`pool_timeout` 預設 30 秒）是整個後端共用的設定，不為個別端點調整。
- **何時重新考慮 async SQLAlchemy**：同時連線數成長到 threadpool 或連線池成為瓶頸，或後端要大幅改寫時。屆時資料庫操作已經集中在 threadpool 的呼叫點，比較容易換。
