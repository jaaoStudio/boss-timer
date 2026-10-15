import axios, { type AxiosError } from 'axios'
import router from '@/router/index'
import { useUserStore } from '@/stores/userStore'
import { showMessage } from '@/composables/useElementPlus'
import i18n from '@/i18n'

// 已由全域處理的錯誤：navigated = 已跳到其他頁（維護頁、錯誤頁、登入失效回首頁），notified = 已提示
const handledErrors = new WeakMap<object, 'navigated' | 'notified'>()

/** 這個錯誤是否已由全域處理（跳頁或已提示） */
export const isHandledGlobally = (error: unknown): boolean =>
  typeof error === 'object' && error !== null && handledErrors.has(error)

/** 全域處理是否已跳到其他頁：呼叫端不要再導頁，否則會蓋掉這次跳轉 */
export const isNavigatedGlobally = (error: unknown): boolean =>
  typeof error === 'object' && error !== null && handledErrors.get(error) === 'navigated'

/**
 * 呼叫端的失敗提示一律經這裡：全域已處理過（跳頁或已提示）就不再顯示，同一個錯誤不會有兩個提示，
 * 也不會把提示顯示在維護頁上
 */
export const showFailure = (error: unknown, message: string): void => {
  if (!isHandledGlobally(error)) showMessage.error(message)
}

/**
 * 全域錯誤處理（ADR-0009「使用中途遇到 401」）：只處理呼叫端處理不了、或需要全站一致的結果，
 * 處理過的記在 handledErrors，之後一律丟出原本的錯誤
 */
export const handleError = async (error: AxiosError): Promise<never> => {
  // 呼叫端自己取消的請求（例如換篩選條件中斷載入）不是錯誤
  if (!axios.isCancel(error)) {
    const handled = error.response?.status === 401 && !error.config?.skipUnauthorizedCheck
      ? await handleUnauthorized()
      : handleGlobally(error)
    if (handled) handledErrors.set(error, handled)
  }
  throw error
}

const handleGlobally = (error: AxiosError): 'navigated' | 'notified' | undefined => {
  if (!error.response) {
    console.error('Network Error:', error)
    return goTo('Maintenance')
  }
  const { status } = error.response
  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail
  // 只處理限流器的 429（後端 rate_limit_exceeded_handler 的格式）；其他 429（例如回饋的每日提交上限）由呼叫端提示
  if (status === 429 && typeof detail === 'string' && detail.startsWith('Rate limit exceeded')) {
    showMessage.warning(i18n.global.t('globalErrors.rateLimitExceeded'))
    return 'notified'
  }
  if (status === 503) return goTo('Maintenance')
  if (status >= 500) return goTo('Error')
  if (status === 404 && detail === 'Record not found') {
    showMessage.warning(i18n.global.t('globalErrors.recordNotFound'))
    return 'notified'
  }
  return undefined
}

// 同一時間的多個 401 共用同一次確認：只問一次、只提示一次、只退回一次
let unauthorizedCheck: Promise<'navigated' | undefined> | undefined

/**
 * 使用中途遇到 401：分頁在前景時會定期換發 access token，正常使用時不會遇到，一律當成異常、不重送。
 * 重新問伺服器：回答登入失效、而這個分頁原本顯示為登入時，提示並退回首頁（CONTEXT.md「登入失效」）；
 * 其他情況（仍是登入、查詢失敗、原本就是匿名）不處理，由呼叫端提示失敗
 */
const handleUnauthorized = async (): Promise<'navigated' | undefined> => {
  // 已經顯示為匿名（例如剛發現登入失效之後才回來的 401）：結果不可能是登入失效，不再確認，由呼叫端提示失敗
  if (!useUserStore().isLoggedIn) return undefined
  unauthorizedCheck ??= checkLoginAfterUnauthorized().finally(() => {
    unauthorizedCheck = undefined
  })
  return unauthorizedCheck
}

const checkLoginAfterUnauthorized = async (): Promise<'navigated' | undefined> => {
  const userStore = useUserStore()
  const wasLoggedIn = userStore.isLoggedIn
  await userStore.recheckSession()
  if (!wasLoggedIn || userStore.isLoggedIn) return undefined
  showMessage.warning(i18n.global.t('globalErrors.sessionExpired'))
  if (router.currentRoute.value.name !== 'RoomSelection') router.push({ name: 'RoomSelection' })
  return 'navigated'
}

const goTo = (name: 'Maintenance' | 'Error'): 'navigated' => {
  if (router.currentRoute.value.name !== name) router.push({ name })
  return 'navigated'
}
