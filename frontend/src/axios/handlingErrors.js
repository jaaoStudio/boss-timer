import router from "@/router/index.js";
import { useAppInfoStore } from "@/stores/appInfo.js";
import {storeToRefs} from "pinia";

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
  // const originalRequestConfig = error.config;
  // if (
  //   error.response.status === 401 &&
  //   error.response.data.error === "MissingToken" &&
  //   originalRequestConfig.url !== "/whoami"
  // ) {
  //   store.commit("updateUserInfo", null);
  //   router.push({ name: "Login" });
  //   showMessage.error("連線過期, 請重新登入！");
  // }
  // if (
  //   error.response.status === 401 &&
  //   error.response.data.error === "ExpiredAccessError" &&
  //   originalRequestConfig.url !== "/refresh"
  // ) {
  //   return callRefreshToken(axiosInstance, originalRequestConfig);
  // }
};

const callRefreshToken = async (axiosInstance, originalRequestConfig) => {
  // const result = await refreshToken();
  // if (result.status === 401) {
  //   store.commit("updateUserInfo", null);
  //   router.push({ name: "Login" });
  //   showMessage.warning("連線過期, 請重新登入！");
  //   return;
  // }
  // return axiosInstance.request(originalRequestConfig);
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
