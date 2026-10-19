import { ref, watch, type Ref } from 'vue'

export function useLocalStorage<T>(
  key: string,
  defaultValue: T,
  deserialize: (raw: string) => T = JSON.parse,
): Ref<T> {
  function load(): T {
    try {
      const raw = localStorage.getItem(key)
      if (raw !== null) return deserialize(raw)
    } catch { /* ignore */ }
    const val = defaultValue
    if (typeof val !== 'object' || val === null) return val
    return (Array.isArray(val) ? [...(val as unknown[])] : { ...val }) as T
  }

  const state = ref<T>(load()) as Ref<T>
  // 剛從其他分頁套用的內容：寫入前比對，相同就不寫回（否則其他分頁刪掉的 key 會被重新寫回，
  // 正規化後的值還會再觸發其他分頁一輪）。只在真的賦值時記下，watch 一定會跑一次並清掉，不會殘留
  let fromOtherTab: string | undefined

  // 預設的 flush：同一輪的修改只寫一次（例如重設設定一次改好幾個欄位）
  watch(state, (val) => {
    const json = JSON.stringify(val)
    const skip = json === fromOtherTab
    fromOtherTab = undefined
    if (!skip) localStorage.setItem(key, json)
  }, { deep: true })

  // 其他分頁改了同一個 key 就跟著更新（storage 事件只送到其他分頁）：同一台裝置的分頁之間，
  // 舊分頁才不會拿舊的整份值存檔、蓋掉其他分頁剛存的（#67）。key 為 null 代表其他分頁清空了 localStorage。
  // shortcut: 監聽不會移除，只能在模組層級呼叫（現有呼叫端都是）；要在元件裡用時改成 scope 結束時移除
  window.addEventListener('storage', (event) => {
    if (event.storageArea !== localStorage || (event.key !== key && event.key !== null)) return
    const next = load()
    const json = JSON.stringify(next)
    if (json === JSON.stringify(state.value)) return
    fromOtherTab = json
    state.value = next
  })

  return state
}
