import { watch, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import { useSettings } from './useSettings'
import { useNotification } from './useNotification'
import { useSound } from './useSound'
import { useI18n } from 'vue-i18n'

export function useBossAlerts() {
  const bossStore = useBossStore()
  const { bossRecords, bossTypes } = storeToRefs(bossStore)
  const { settings } = useSettings()
  const { sendNotification } = useNotification()
  const { playSoundForAlert } = useSound()
  const { t, locale } = useI18n()

  const activeTimeouts = new Map<string, ReturnType<typeof setTimeout>>()
  const firedAlerts = new Set<string>()

  function getBossName(bossTypeId: number): string {
    const bossType = bossTypes.value.find((bt: any) => bt.id === bossTypeId)
    if (!bossType) return 'Unknown Boss'
    return locale.value === 'zh' ? bossType.name_zh : bossType.name_en
  }

  function triggerAlert(record: any, type: 'min' | 'max') {
    const bossName = getBossName(record.boss_type_id)
    const channel = record.channel

    if (settings.value.notificationEnabled) {
      const title = type === 'min'
        ? t('notification.mayRespawn')
        : t('notification.definitelyRespawned')
      const body = `${bossName} - CH ${channel}`
      sendNotification(title, body)
    }

    if (settings.value.soundEnabled) {
      const soundType = type === 'min'
        ? settings.value.minRespawnSound
        : settings.value.maxRespawnSound
      const alertKey = type === 'min' ? 'custom-min' : 'custom-max'
      playSoundForAlert(soundType, alertKey, settings.value.soundVolume)
    }
  }

  function scheduleAlerts() {
    // Clear existing timeouts
    activeTimeouts.forEach(timeout => clearTimeout(timeout))
    activeTimeouts.clear()

    const now = Date.now()

    for (const record of bossRecords.value) {
      // Min respawn alert
      if (settings.value.alertOnMinRespawn && record.respawn_min_time) {
        const minTime = new Date(record.respawn_min_time).getTime()
        const delay = minTime - now
        const key = `${record.id}_min`

        if (delay > 0 && !firedAlerts.has(key)) {
          const timeout = setTimeout(() => {
            triggerAlert(record, 'min')
            firedAlerts.add(key)
            activeTimeouts.delete(key)
          }, delay)
          activeTimeouts.set(key, timeout)
        }
      }

      // Max respawn alert
      if (settings.value.alertOnMaxRespawn && record.respawn_max_time) {
        const maxTime = new Date(record.respawn_max_time).getTime()
        const delay = maxTime - now
        const key = `${record.id}_max`

        if (delay > 0 && !firedAlerts.has(key)) {
          const timeout = setTimeout(() => {
            triggerAlert(record, 'max')
            firedAlerts.add(key)
            activeTimeouts.delete(key)
          }, delay)
          activeTimeouts.set(key, timeout)
        }
      }
    }
  }

  // Re-schedule whenever records or relevant settings change
  watch(
    [bossRecords, () => settings.value.alertOnMinRespawn, () => settings.value.alertOnMaxRespawn],
    () => { scheduleAlerts() },
    { deep: true, immediate: true }
  )

  onUnmounted(() => {
    activeTimeouts.forEach(timeout => clearTimeout(timeout))
    activeTimeouts.clear()
  })

  return { scheduleAlerts }
}
