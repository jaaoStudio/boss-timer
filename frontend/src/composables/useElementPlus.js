import { ElMessage, ElMessageBox } from "element-plus";
import { WarnTriangleFilled } from "@element-plus/icons-vue";
import {markRaw} from "vue";

const iconMapping = {
  error: markRaw(WarnTriangleFilled),
};

class ShowMessage {
  constructor() {
    this.ElMessage = ElMessage;
  }

  success(message) {
    this.show("success", message);
  }

  warning(message) {
    this.show("warning", message);
  }

  info(message) {
    this.show("info", message);
  }

  error(message) {
    this.show("error", message);
  }

  show(type, message) {
    // 秀 message 之前先關閉所有的 message (一次只有一則)
    // 也可以將 grouping 設定為 true，讓相同的訊息群組起來，grouping 的樣式為 badge，已處理好樣式
    this.ElMessage.closeAll();

    this.ElMessage({
      // 訊息內容
      message,
      // 關閉週期
      duration: 2000,
      // 顯示模式: success / info / warning / error
      type,
      // 訊息 icon
      icon: iconMapping[type] || undefined,
      // 群組，會將內容相同的訊息群組起來
      grouping: false,
    });
  }
}

class ShowMessageBox {
  constructor() {
    this.ElMessageBox = ElMessageBox;
  }

  alert(message, title, options) {
    this.ElMessageBox.alert(message, title, {
      confirmButtonText: "確定",
      callback: (/* action */) => {
        // showMessage.success(`已 ${action}`);
      },
      ...options,
    });
  }

  confirm(message, title, options) {
    this.ElMessageBox.confirm(message, title, {
      confirmButtonText: "確定",
      cancelButtonText: "取消",
      type: "warning",
      ...options,
    })
      .then(() => showMessage.success("已確認"))
      .catch(() => showMessage.info("已取消"));
  }

  prompt(message = "請輸入...", title = "請至少輸入六位數字", options) {
    this.ElMessageBox.prompt(message, title, {
      confirmButtonText: "確定",
      cancelButtonText: "取消",
      inputPattern: /\d{6}/,
      inputErrorMessage: "請至少輸入六位數字",
      ...options,
    })
      .then(({ value }) => showMessage.success(`輸入的值為: ${value}`))
      .catch(() => showMessage.info("已取消"));
  }
}

export const showMessage = new ShowMessage();
export const showMessageBox = new ShowMessageBox();
