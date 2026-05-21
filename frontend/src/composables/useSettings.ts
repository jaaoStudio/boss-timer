import { useLocalStorage } from '@/composables/useLocalStorage'

export interface BossTimerSettings {
  notificationEnabled: boolean
  soundEnabled: boolean
  soundVolume: number
  alertOnMinRespawn: boolean
  alertOnMaxRespawn: boolean
  minRespawnSound: string  // 'default' | 'gentle' | 'urgent' | 'custom'
  maxRespawnSound: string  // 'default' | 'gentle' | 'urgent' | 'custom'
}

const DEFAULT_SETTINGS: BossTimerSettings = {
  notificationEnabled: false,
  soundEnabled: false,
  soundVolume: 70,
  alertOnMinRespawn: true,
  alertOnMaxRespawn: false,
  minRespawnSound: 'default',
  maxRespawnSound: 'urgent',
}

const settings = useLocalStorage<BossTimerSettings>(
  'boss-timer-settings',
  DEFAULT_SETTINGS,
  (raw) => ({ ...DEFAULT_SETTINGS, ...JSON.parse(raw) }),
)

export function useSettings() {
  return {
    settings,
    resetToDefaults() {
      Object.assign(settings.value, DEFAULT_SETTINGS)
    },
  }
}
