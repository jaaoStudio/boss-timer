import type { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios'
import router from '@/router/index'
import { useUserStore } from '@/stores/userStore'
import { showMessage } from '@/composables/useElementPlus'
import apiService from '@/services/apiService'
import i18n from '@/i18n'

export const handleError = (axiosInstance: AxiosInstance, error: AxiosError): void | Promise<unknown> => {
  if (!error.response) {
    console.error('Network Error:', error)
    if (router.currentRoute.value.name !== 'Maintenance') {
      router.push({ name: 'Maintenance' })
    }
    return
  }

  switch (error.response.status) {
    case 401:
      return handleUnauthorized(axiosInstance, error)
    case 404:
      if (
        error.response.data &&
        (error.response.data as { detail?: string }).detail === 'Record not found'
      ) {
        showMessage.warning(i18n.global.t('globalErrors.recordNotFound'))
      }
      break
    case 429:
      showMessage.warning(i18n.global.t('globalErrors.rateLimitExceeded'))
      break
    case 503:
      handleServiceUnavailable()
      break
    default:
      if (error.response.status >= 500) handleServerError()
      break
  }
}

const handleUnauthorized = (axiosInstance: AxiosInstance, error: AxiosError): Promise<unknown> | void => {
  const originalRequestConfig = error.config as AxiosRequestConfig | undefined
  if (
    error.response?.status === 401 &&
    originalRequestConfig?.url !== 'auth/refresh'
  ) {
    console.log('error', error)
    return callRefreshToken(axiosInstance, originalRequestConfig!)
  } else {
    router.push({ name: 'RoomSelection' })
    showMessage.error('請先登入')
  }
}

const callRefreshToken = async (axiosInstance: AxiosInstance, originalRequestConfig: AxiosRequestConfig) => {
  const userStore = useUserStore()
  const result = await apiService.refresh_token()
  if (result.status === 401) {
    userStore.clearAuth()
    await router.push({ name: 'RoomSelection' })
    showMessage.warning('連線過期, 請重新登入！')
    return
  }
  return axiosInstance.request(originalRequestConfig)
}

const handleServiceUnavailable = () => {
  if (router.currentRoute.value.name !== 'Maintenance') {
    router.push({ name: 'Maintenance' })
  }
}

const handleServerError = () => {
  if (router.currentRoute.value.name !== 'Error') {
    router.push({ name: 'Error' })
  }
}