import axios, {
  type AxiosInstance as AxiosClient,
  type AxiosRequestConfig,
  type AxiosResponse,
  type AxiosError,
  type CreateAxiosDefaults,
} from 'axios'
import { handleError } from './handlingErrors'

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

  patch<T = unknown>(url: string, config: AxiosRequestConfig = {}) {
    return this.axiosInstance.patch<T>(url, config)
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
      handleError(axiosInstance, error)
      return Promise.reject(error)
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