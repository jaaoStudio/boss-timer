import axios from "axios";
import { handleError } from "./handlingErrors";

class AxiosInstance {
  constructor(options) {
    /**
     * options 參數可參考 axios 官方文件
     * 參考：https://axios-http.com/docs/req_config
     */
    this.axiosInstance = axios.create(options);
    setAxiosInterceptor(this.axiosInstance);
  }

  /**
   * 若需求情境有需要中斷請求：
   * CRUD 有需要使用 abort controller 可以在此設定於 config 中
   * 配合存放於 store 中，並確保 abort 後刷新 abort controller
   * 參考：https://axios-http.com/docs/cancellation
   */

  get(url, config = {}) {
    return this.axiosInstance.get(url, config);
  }

  post(url, data = {}, config = {}) {
    return this.axiosInstance.post(url, data, config);
  }

  put(url, data = {}, config = {}) {
    return this.axiosInstance.put(url, data, config);
  }

  delete(url, config = {}) {
    return this.axiosInstance.delete(url, config);
  }
}

const setAxiosInterceptor = (axiosInstance) => {
  axiosInstance.interceptors.request.use(
    (config) => {
      // 若專案的 token 並非透過 cookie 方式傳遞，可以在此設定 HTTP Header
      return config;
    },
    (error) => Promise.reject(error)
  );
  axiosInstance.interceptors.response.use(
    (response) => response,
    (error) => {
      handleError(axiosInstance, error);
      return Promise.reject(error);
    }
  );
};

/**
 * 建立不同的 axios 實例
 * 透過 baseURL 的設定，可以讓不同的 axios 實例發送請求到不同的網域
 * （ local run 須配合 server.proxy ）
 *
 * 若有需要部屬到不同的網域，可以透過環境變數來設定 baseURL
 */
const bossService = new AxiosInstance({
  baseURL: `${import.meta.env.VITE_APP_BASE_URL}`,
  headers: {
    'Content-Type': 'application/json'
  }
});

export { bossService };
