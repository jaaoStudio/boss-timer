import axios, { type AxiosError } from 'axios'
import router, { canAccess } from '@/router/index'
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
export const handleError = (error: AxiosError): Promise<never> => {
  // 呼叫端自己取消的請求（例如換篩選條件中斷載入）不是錯誤
  if (!axios.isCancel(error)) {
    const handled = error.response?.status === 401 ? handleUnauthorized() : handleGlobally(error)
    if (handled) handledErrors.set(error, handled)
  }
  return Promise.reject(error)
}

const handleGlobally = (error: AxiosError): 'navigated' | 'notified' | undefined => {
  if (!error.response) {
    console.error('Network Error:', error)
    return goTo('Maintenance')
  }
  const { status } = error.response
  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail
  // 429 一律提示「操作太頻繁」（含 Cloudflare / nginx 回的）；只有回饋的每日提交上限帶 code，由回饋頁提示
  const code = typeof detail === 'object' && detail !== null ? (detail as { code?: unknown }).code : undefined
  if (status === 429 && code !== 'feedback_daily_limit') {
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

/**
 * 使用中途遇到 401：需要登入的 API 在 access token 過期時會自己換發，401 代表伺服器已判斷登入失效（ADR-0009），不再確認。
 * 原本顯示為登入時照登出的順序改為匿名、提示並退回首頁（CONTEXT.md「登入失效」）；需要登入的頁面由 App.vue 跳頁。
 * 不是登入失效的 401（已經是匿名、其他分頁剛登入 / 登出而正在重新查詢）不處理，由呼叫端提示失敗
 */
const handleUnauthorized = (): 'navigated' | undefined => {
  if (!useUserStore().handleLoginLost()) return undefined
  showMessage.warning(i18n.global.t('globalErrors.sessionExpired'))
  const current = router.currentRoute.value
  // 需要登入的頁面由 App.vue 跳頁；已在維護頁、錯誤頁（同時送出的其他請求已跳過去）時不蓋掉
  const stay = ['RoomSelection', 'Maintenance', 'Error']
  if (!globalNavigation && canAccess(current) && !stay.includes(current.name as string)) router.push({ name: 'RoomSelection' })
  return 'navigated'
}

// 進行中的全域跳頁（維護頁、錯誤頁）：router.currentRoute 要等跳完才會改變，之後的 401 不可蓋掉它
let globalNavigation: Promise<unknown> | undefined

const goTo = (name: 'Maintenance' | 'Error'): 'navigated' => {
  if (router.currentRoute.value.name !== name) {
    const navigation = router.push({ name })
    globalNavigation = navigation
    // 失敗也要清掉（例如斷線時維護頁的程式碼載不下來），用 then 的兩個參數，不留下沒處理的 rejection
    const clear = () => {
      if (globalNavigation === navigation) globalNavigation = undefined
    }
    void navigation.then(clear, clear)
  }
  return 'navigated'
}
