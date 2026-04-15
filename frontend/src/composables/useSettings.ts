import { ref, watch } from 'vue'

export interface BossTimerSettings {
  notificationEnabled: boolean
  soundEnabled: boolean
  soundVolume: number
  alertOnMinRespawn: boolean
  alertOnMaxRespawn: boolean
  minRespawnSound: string  // 'default' | 'gentle' | 'urgent' | 'custom'
  maxRespawnSound: string  // 'default' | 'gentle' | 'urgent' | 'custom'
}

const STORAGE_KEY = 'boss-timer-settings'

const DEFAULT_SETTINGS: BossTimerSettings = {
  notificationEnabled: false,
  soundEnabled: false,
  soundVolume: 70,
  alertOnMinRespawn: true,
  alertOnMaxRespawn: false,
  minRespawnSound: 'default',
  maxRespawnSound: 'urgent',
}

function loadSettings(): BossTimerSettings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) }
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_SETTINGS }
}

// Singleton refs so all components share the same state
const settings = ref<BossTimerSettings>(loadSettings())

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings.value))
}

// Auto-persist on any change
watch(settings, persist, { deep: true })

export function useSettings() {
  return {
    settings,
    resetToDefaults() {
      Object.assign(settings.value, DEFAULT_SETTINGS)
    },
  }
}
