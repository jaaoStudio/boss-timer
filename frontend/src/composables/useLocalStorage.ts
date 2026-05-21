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

  return state
}