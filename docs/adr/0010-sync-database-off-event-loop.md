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

### 資料庫工作依序執行：一把鎖住整個請求（PR #80 第 2、3 輪）

改在 threadpool 執行後，同一個 worker 的請求會真的同時跑。程式原本隱含依賴「資料庫工作依序執行」——以前資料庫卡住 event loop，等於所有請求自動排隊——同時執行後兩輪審查陸續找到 7 個交錯：投票連點、每日上限被突破、重複建立帳號、多個 refresh token、加入房間時讀快照與訂閱之間漏掉回報、刪除紀錄撤銷不到剛排程的 Discord 預警、清理工作封存剛活躍的房間。我們決定**保留依序執行，但不在 event loop 上**：

- `app/database/database.py` 的 `db_lock()`（anyio `Lock`，每個 event loop 一把）。`get_db` 是 async 的 dependency：請求開始時拿鎖、建立 session，整個請求結束、session 關閉後才放開。FastAPI 把一個請求拆成好幾段丟進 threadpool（dependency、端點本體、回應序列化、收尾），依序執行的單位是整個請求，段與段之間不會插進別的請求。
- 等鎖的請求在 event loop 上等，不佔執行緒也不佔資料庫連線；拿著鎖的請求各段馬上有執行緒可用（threadpool 維持預設的 40 條）。WebSocket 連線、心跳、收訊息與廣播照常在 event loop 上同時進行。
- 不經 `get_db` 的資料庫工作也拿同一把鎖：WebSocket 有登入 cookie 的握手、加入房間（讀房間狀態到訂閱都在鎖裡，別人的回報要等訂閱好才寫得進去）、回報、清理工作、Google 登入的資料庫那段。匿名握手不查資料庫，不拿鎖。
- **拿著鎖時不可再等另一件也要拿鎖的事**（會互相等待而卡死），也不要在鎖裡等外部服務：`/auth/google` 因此不依賴 `get_db`，呼叫 Google 在鎖外、資料庫那段才拿鎖。從 threadpool 回到 event loop 只用來廣播（`manager.*_from_thread`，不需要鎖）。
- 維護設定檔（`maintenance.json`）不經鎖：讀與寫都在 event loop 上直接做（檔案很小），不會同時發生，讀完到比較、廣播之間也沒有 `await`。
- 第 1 輪加的防競爭寫法（撞到唯一限制改用已存在的那一筆、鎖住使用者那一列）保留，以後放寬時用得上（`tests/test_concurrency_pg.py`）。

## Considered Options

- **把 threadpool 限成一次一個**（PR #80 第 2 輪的實作）：做不到依序執行。anyio 的 `CapacityLimiter` 釋放名額時只是叫醒下一位、沒有把名額交給它，醒來前可以被別的請求搶先，兩件事同時跑；而且依序執行的單位是「一段」而不是「一個請求」，請求在段與段之間排隊時佔著資料庫連線，大量湧入時 30 條連線被排隊中的請求佔光，拿到名額的卻等不到連線，整站卡住 30 秒。

- **讓請求同時執行，逐一處理競爭**（PR #80 第 1 輪的方向）：一般 web 應用的做法、吞吐量高，但這份程式從來不是照「會同時執行」寫的。加入房間的漏接要動到前端怎麼合併資料，兩輪就找到 7 個交錯、很可能還有。吞吐量在目前規模不是問題（PR 之前本來就是一次一個），不值得。

- **改用 async 的 SQLAlchemy + asyncpg**：它也解決不了上面的交錯——每個 `await` 都是讓出點，一個請求等資料庫時 event loop 就去跑別的請求，和 threadpool 同時執行一樣會交錯。此外，從頭到尾都是 async，沒有 threadpool 的上限，取消與逾時比較自然。但所有 service 與端點都要改寫成 `AsyncSession` 加 `await`；async 模式不能延遲載入關聯（`record.recorder`、`record.boss_type` 這類用法漏改一處，就要等特定資料出現時才在執行期出錯，測試不一定測得到）；Celery worker 是同步的，要同時維持兩套資料庫設定與查詢寫法；測試的假 session 也要全部改。這個專案的規模（同時開著幾百個分頁、查詢都很短）用 threadpool（40 條執行緒）與連線池（30 條連線）綽綽有餘，不值得這個代價。

## Consequences

- event loop 不再被資料庫卡住；資料庫工作依序執行，吞吐量與 PR 之前相同（每筆只有幾毫秒），在目前規模不是瓶頸。一筆慢查詢或慢的 Redis（Discord 排程、預警撤銷，撤銷已改為一次呼叫）會讓之後的資料庫工作排隊，但不再卡住 WebSocket 的心跳與廣播。
- 新增需要資料庫的端點時：不需要 `await` 就用 `def`；需要 `await` 就把資料庫那段放進 `run_in_threadpool`。勿在 `async def` 裡直接查詢。
- 連線池用盡時的等候逾時（`pool_timeout` 預設 30 秒）是整個後端共用的設定，不為個別端點調整。
- **何時放寬**：資料庫工作的排隊時間成為瓶頸時。屆時要先補齊各處的防競爭（以 `tests/test_concurrency_pg.py` 的寫法重現），再拿掉或縮小鎖的範圍；async SQLAlchemy 同樣需要先處理這些交錯。
