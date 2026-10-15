import axios, { type AxiosError, type AxiosInstance } from 'axios'
import router from '@/router/index'
import { useUserStore } from '@/stores/userStore'
import { showMessage } from '@/composables/useElementPlus'
import i18n from '@/i18n'

// 已由全域處理（跳維護 / 錯誤頁，或已提示）的錯誤
const handledErrors = new WeakSet<object>()

/**
 * 這個錯誤是否已由全域處理。呼叫端在 catch 裡先問它，已處理過就不再顯示自己的失敗提示，
 * 避免同一個錯誤出現兩個提示（或提示出現在維護頁上）
 */
export const isHandledGlobally = (error: unknown): boolean =>
  typeof error === 'object' && error !== null && handledErrors.has(error)

/**
 * 全域錯誤處理：回傳重送成功的回應（401 且仍是登入時），否則丟出原本的錯誤。
 * 只處理呼叫端處理不了、或需要全站一致的結果；其他錯誤交給呼叫端
 */
export const handleError = async (axiosInstance: AxiosInstance, error: AxiosError): Promise<unknown> => {
  // 呼叫端自己取消的請求（例如換篩選條件中斷載入）不是錯誤
  if (axios.isCancel(error)) throw error
  if (error.response?.status === 401 && error.config && !error.config._retriedAfterUnauthorized) {
    return handleUnauthorized(axiosInstance, error)
  }
  if (handleGlobally(error)) handledErrors.add(error)
  throw error
}

const handleGlobally = (error: AxiosError): boolean => {
  if (!error.response) {
    console.error('Network Error:', error)
    goTo('Maintenance')
    return true
  }
  const { status, data } = error.response
  // 只處理限流器的 429（後端 rate_limit_exceeded_handler 的格式）；其他 429（例如回饋的每日提交上限）由呼叫端提示
  if (status === 429 && (data as { detail?: string } | undefined)?.detail?.startsWith('Rate limit exceeded')) {
    showMessage.warning(i18n.global.t('globalErrors.rateLimitExceeded'))
    return true
  }
  if (status === 503) {
    goTo('Maintenance')
    return true
  }
  if (status >= 500) {
    goTo('Error')
    return true
  }
  if (status === 404 && (data as { detail?: string } | undefined)?.detail === 'Record not found') {
    showMessage.warning(i18n.global.t('globalErrors.recordNotFound'))
    return true
  }
  return false
}

/**
 * 使用中途遇到 401：不在前端自己換發或判斷，問 /auth/session（ADR-0009）。
 * 仍是登入（伺服器已順便換發）→ 重送一次並交還結果；登入失效 → userStore 已改為匿名、通知其他分頁，
 * 這個分頁原本顯示為登入時提示；查詢失敗 → 沿用目前的顯示。後兩者原本的請求照樣失敗
 */
const handleUnauthorized = async (axiosInstance: AxiosInstance, error: AxiosError): Promise<unknown> => {
  const userStore = useUserStore()
  const wasLoggedIn = userStore.isLoggedIn
  const session = await userStore.revalidateSession()
  if (session?.status === 'authenticated') {
    return axiosInstance.request({ ...error.config, _retriedAfterUnauthorized: true })
  }
  if (session?.status === 'anonymous' && wasLoggedIn) {
    showMessage.warning(i18n.global.t('globalErrors.sessionExpired'))
    handledErrors.add(error)
  }
  throw error
}

const goTo = (name: 'Maintenance' | 'Error') => {
  if (router.currentRoute.value.name !== name) router.push({ name })
}
