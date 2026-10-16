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

  watch(state, (val) => {
    localStorage.setItem(key, JSON.stringify(val))
  }, { deep: true })

  // 其他分頁改了同一個 key 就跟著更新（storage 事件只送到其他分頁）：同一台裝置的分頁之間，
  // 舊分頁才不會拿舊的整份值存檔、蓋掉其他分頁剛存的（#67）。key 為 null 代表其他分頁清空了 localStorage
  window.addEventListener('storage', (event) => {
    if (event.storageArea === localStorage && (event.key === key || event.key === null)) state.value = load()
  })

  return state
}