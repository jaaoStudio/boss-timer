import { getCurrentScope, onScopeDispose, ref, watch, type Ref } from 'vue'

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
  // 正在套用其他分頁的值：不寫回（否則其他分頁刪掉的 key 會被重新寫回，正規化後的值還會再觸發其他分頁一輪）
  let applyingOtherTab = false

  // flush: 'sync'：在賦值當下就執行，才能以上面的旗標判斷這次改變是不是來自其他分頁
  const stopWatch = watch(state, (val) => {
    if (!applyingOtherTab) localStorage.setItem(key, JSON.stringify(val))
  }, { deep: true, flush: 'sync' })

  // 其他分頁改了同一個 key 就跟著更新（storage 事件只送到其他分頁）：同一台裝置的分頁之間，
  // 舊分頁才不會拿舊的整份值存檔、蓋掉其他分頁剛存的（#67）。key 為 null 代表其他分頁清空了 localStorage
  const onStorage = (event: StorageEvent) => {
    if (event.storageArea !== localStorage || (event.key !== key && event.key !== null)) return
    applyingOtherTab = true
    try {
      state.value = load()
    } finally {
      applyingOtherTab = false
    }
  }
  window.addEventListener('storage', onStorage)

  // 在元件或 effect scope 裡呼叫時，結束就移除監聽；現有的呼叫端都在模組層級，跟著頁面存在
  if (getCurrentScope()) {
    onScopeDispose(() => {
      window.removeEventListener('storage', onStorage)
      stopWatch()
    })
  }

  return state
}
