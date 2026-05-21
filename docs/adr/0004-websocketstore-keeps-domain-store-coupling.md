# websocketStore 保持 domain store 樞紐角色，不引入 pub/sub

`websocketStore` 直接 import 四個 domain store（`bossStore`、`roomStore`、`recordHistoryStore`、`appInfoStore`），並在各 message handler 內直接呼叫它們的 actions。

## 考慮過的選項

**pub/sub（如 mitt）**：websocketStore 只 emit 事件，各 domain store 自行訂閱關心的訊息類型。傳輸層與 domain 完全解耦，符合「websocketStore 不該知道 domain 邏輯」的原則。

**保持現狀（採用）**：dispatch table + 具名 handler 函式（`onBossUpdate`、`onRecordDeleted` 等）讓多 store 副作用可見，在不改變耦合架構的前提下解決隱性問題。

## 決定理由

pub/sub 帶來的代價在這個 codebase 不值得：
- 需要新增 event emitter 依賴（如 `mitt`）
- 各 store 的訂閱需要在特定時機建立與清除（生命週期管理）
- Store 數量固定，訊息類型有限，耦合不會持續擴大

多 store 副作用的可見性問題已透過具名 handler 解決（見 `onBossUpdate`、`onRecordDeleted`）。
