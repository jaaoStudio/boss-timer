import { defineStore } from "pinia";

export const useAppInfoStore = defineStore("AppInfo", {
  state: () => ({
    isServerError: false,
    surveyCreatorCurrentJson: {},
    haveSurveyCreatorCurrentJson: false,
  }),
  getters: {
    appTitle() {
      return import.meta.env.VITE_APP_TITLE;
    },
  },
  actions: {
    setSurveyCreatorCurrentJson(json) {
      this.surveyCreatorCurrentJson = this.moveElementsToLast(json);
    },
    moveElementsToLast(obj) {
      // 如果是陣列，遞迴處理每個元素
      if (Array.isArray(obj)) {
        return obj.map((item) => this.moveElementsToLast(item));
      }

      // 如果不是物件或是 null，直接返回
      if (typeof obj !== "object" || obj === null) {
        return obj;
      }

      // 創建新物件來存放結果
      const result = {};
      let elementsValue = null;
      let hasElements = false;

      // 遍歷物件的所有鍵值對
      for (const [key, value] of Object.entries(obj)) {
        if (key === "elements") {
          // 如果是 elements 鍵，先暫時儲存起來
          elementsValue = value;
          hasElements = true;
        } else {
          // 遞迴處理其他屬性的值
          result[key] = this.moveElementsToLast(value);
        }
      }

      // 如果有 elements 鍵，將它放在最後
      if (hasElements) {
        result.elements = this.moveElementsToLast(elementsValue);
      }

      return result;
    },
  },
});
