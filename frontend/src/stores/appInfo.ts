import { defineStore } from "pinia";
import apiService from "@/services/apiService";

interface MaintenanceInfo {
  is_maintenance: boolean;
  is_ready_for_maintenance: boolean;
  title: string;
  message: string;
}

export const useAppInfoStore = defineStore("AppInfo", {
  state: () => ({
    isServerError: false,
    maintenanceInfo: {
      is_maintenance: false,
      is_ready_for_maintenance: false,
      title: "",
      message: "",
    } as MaintenanceInfo,
  }),
  getters: {
    appTitle(): string {
      return import.meta.env.VITE_APP_TITLE || "Boss Timing";
    },
    isMaintenanceActive(): boolean {
      // 當 is_maintenance 或 is_ready_for_maintenance 為 true 時顯示橫幅
      return this.maintenanceInfo.is_maintenance || this.maintenanceInfo.is_ready_for_maintenance;
    },
  },
  actions: {
    async checkMaintenanceStatus() {
      try {
        const maintenanceInfo = await apiService.getMaintenanceStatus();
        if (maintenanceInfo) {
          this.maintenanceInfo = maintenanceInfo;
        }
      } catch (error) {
        console.error("Failed to fetch maintenance info:", error);
        // 如果API請求失敗，確保我們不會意外地顯示維護橫幅
        this.maintenanceInfo.is_maintenance = false;
        this.maintenanceInfo.is_ready_for_maintenance = false;
      }
    },
    setMaintenanceInfo(newInfo: MaintenanceInfo) {
      this.maintenanceInfo = newInfo;
    },
  },
});
