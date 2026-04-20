import { ElMessage, ElMessageBox } from 'element-plus'
import type { MessageOptions, ElMessageBoxOptions } from 'element-plus'
import { WarnTriangleFilled } from '@element-plus/icons-vue'
import { markRaw, type Component } from 'vue'

type MessageType = 'success' | 'warning' | 'info' | 'error'

const iconMapping: Partial<Record<MessageType, Component>> = {
  error: markRaw(WarnTriangleFilled),
}

class ShowMessage {
  private ElMessage = ElMessage

  success(message: string) {
    this.show('success', message)
  }

  warning(message: string) {
    this.show('warning', message)
  }

  info(message: string) {
    this.show('info', message)
  }

  error(message: string) {
    this.show('error', message)
  }

  show(type: MessageType, message: string) {
    this.ElMessage.closeAll()

    this.ElMessage({
      message,
      duration: 2000,
      type,
      icon: iconMapping[type],
      grouping: false,
    } as MessageOptions)
  }
}

class ShowMessageBox {
  private ElMessageBox = ElMessageBox

  alert(message: string, title: string, options?: ElMessageBoxOptions) {
    this.ElMessageBox.alert(message, title, {
      confirmButtonText: '確定',
      callback: () => {},
      ...options,
    })
  }

  confirm(message: string, title: string, options?: ElMessageBoxOptions) {
    this.ElMessageBox.confirm(message, title, {
      confirmButtonText: '確定',
      cancelButtonText: '取消',
      type: 'warning',
      ...options,
    })
      .then(() => showMessage.success('已確認'))
      .catch(() => showMessage.info('已取消'))
  }

  prompt(message = '請輸入...', title = '請至少輸入六位數字', options?: ElMessageBoxOptions) {
    this.ElMessageBox.prompt(message, title, {
      confirmButtonText: '確定',
      cancelButtonText: '取消',
      inputPattern: /\d{6}/,
      inputErrorMessage: '請至少輸入六位數字',
      ...options,
    })
      .then(({ value }) => showMessage.success(`輸入的值為: ${value}`))
      .catch(() => showMessage.info('已取消'))
  }
}

export const showMessage = new ShowMessage()
export const showMessageBox = new ShowMessageBox()