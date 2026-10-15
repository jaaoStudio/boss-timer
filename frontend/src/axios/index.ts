import axios, {
  type AxiosInstance as AxiosClient,
  type AxiosRequestConfig,
  type AxiosResponse,
  type AxiosError,
  type CreateAxiosDefaults,
} from 'axios'
import { handleError } from './handlingErrors'

declare module 'axios' {
  interface AxiosRequestConfig {
    // 失敗由呼叫端處理：不跳轉頁面、不顯示提示
    skipGlobalErrorHandler?: boolean
    // 遇到 401 後重送的請求：再遇到 401 就不再處理，避免一直重送
    _retriedAfterUnauthorized?: boolean
  }
}

class AxiosInstance {
  private axiosInstance: AxiosClient

  constructor(options: CreateAxiosDefaults) {
    this.axiosInstance = axios.create(options)
    setAxiosInterceptor(this.axiosInstance)
  }

  get<T = unknown>(url: string, config: AxiosRequestConfig = {}) {
    return this.axiosInstance.get<T>(url, config)
  }

  post<T = unknown>(url: string, data: unknown = {}, config: AxiosRequestConfig = {}) {
    return this.axiosInstance.post<T>(url, data, config)
  }

  put<T = unknown>(url: string, data: unknown = {}, config: AxiosRequestConfig = {}) {
    return this.axiosInstance.put<T>(url, data, config)
  }

  delete<T = unknown>(url: string, config: AxiosRequestConfig = {}) {
    return this.axiosInstance.delete<T>(url, config)
  }

  patch<T = unknown>(url: string, data: unknown = {}, config: AxiosRequestConfig = {}) {
    return this.axiosInstance.patch<T>(url, data, config)
  }
}

const setAxiosInterceptor = (axiosInstance: AxiosClient) => {
  axiosInstance.interceptors.request.use(
    (config) => config,
    (error: AxiosError) => Promise.reject(error),
  )
  axiosInstance.interceptors.response.use(
    (response: AxiosResponse) => response,
    (error: AxiosError) => {
      if (error.config?.skipGlobalErrorHandler) return Promise.reject(error)
      // 401 且重送成功時，呼叫端拿到重送的回應
      return handleError(axiosInstance, error)
    },
  )
}

const bossService = new AxiosInstance({
  baseURL: `${import.meta.env.VITE_APP_BASE_URL}`,
  headers: {
    'Content-Type': 'application/json',
  },
})

export { bossService }