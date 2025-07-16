import router from "@/router/index.js";
import { useAppInfoStore } from "@/stores/appInfo.js";
import { useUserStore} from "@/stores/userStore.js";
import {storeToRefs} from "pinia";
import {showMessage} from "@/composables/useElementPlus.js";
import apiService from "@/services/apiService.js";

export const handleError = (axiosInstance, error) => {
  switch (error.response.status) {
    case 401:
      handleUnauthorized(axiosInstance, error);
      break;
    default:
      if (error.response.status >= 500) handleServerError(error);
      break;
  }
};

// 401 Unauthorized
const handleUnauthorized = (axiosInstance, error) => {

  /**
   * 若專案有 refresh token 的機制，可以在此設定
   *
   * 原則上是在 response 回來後
   * 檢查是 1. Missing Token 或 2. Token Expired
   *
   * 1. 若是 Missing Token，則直接導向登入頁
   * 2. 若是 Token Expired，則發送 refresh token 的請求，
   * 並在成功後重新發送原本的請求，若仍失敗則導向登入頁
   */
  const originalRequestConfig = error.config;
  if (
    error.response.status === 401 &&
    originalRequestConfig.url !== "auth/refresh"
  ) {
      console.log("401401401", originalRequestConfig)
      console.log("error", error)
      return callRefreshToken(axiosInstance, originalRequestConfig);
  }else{
    router.push({name: "RoomSelection"})
    // window.location.href = "/"
    showMessage.error("請先登入")
  }
};

const callRefreshToken = async (axiosInstance, originalRequestConfig) => {

  const userStore = useUserStore()
  const result = await apiService.refresh_token();
  if (result.status === 401) {
    userStore.clearAuth()
    await router.push({name: "RoomSelection"});
    showMessage.warning("連線過期, 請重新登入！");
    return;
  }
  return axiosInstance.request(originalRequestConfig);
};

// 5xx Server Error
const handleServerError = () => {
  /**
   * 若專案要實做 Error View，可以在此設定
   * 若 status code >= 500，則導向 Error View
   *
   * 透過 store 設定 isServerError 為 true
   */
  const appInfoStore = useAppInfoStore();
  const { isServerError } = storeToRefs(appInfoStore);
  isServerError.value = true;
  console.log("伺服器錯誤，請稍後再試！");
  router.push({name: "ServerError"}).then(r =>{});
};
