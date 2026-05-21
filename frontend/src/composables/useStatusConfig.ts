import { useI18n } from 'vue-i18n'

export interface StatusConfig {
  text: string
  bgClass: string
}

// Hex colors used by ECharts (ChannelTimeline)
export const STATUS_COLORS: Record<string, string> = {
  may_respawn: '#eab308',
  respawning:  '#3b82f6',
  alive:       '#16a34a',
  killed:      '#b91c1c',
  not_found:   '#9ca3af',
  expired:     '#d1d5db',
  unknown:     '#d1d5db',
}

// Sort order used by ChannelOverview and ChannelTimeline
export const STATUS_ORDER: Record<string, number> = {
  may_respawn: 0,
  respawning:  1,
  alive:       2,
  not_found:   3,
  unknown:     4,
}

type ExpiredCheckable = {
  current_status: string
  respawn_min_time?: string | null
  respawn_max_time?: string | null
} | null | undefined

export function isExpiredRecord(record: ExpiredCheckable): boolean {
  if (!record) return false
  if (record.current_status !== 'alive') return false
  if (!record.respawn_min_time || !record.respawn_max_time) return false
  const window = new Date(record.respawn_max_time).getTime() - new Date(record.respawn_min_time).getTime()
  return Date.now() - new Date(record.respawn_max_time).getTime() > window
}

export function useStatusConfig() {
  const { t } = useI18n()

  function getStatusConfig(status: string, expired = false): StatusConfig {
    if (expired) {
      return { text: t('status.expired'), bgClass: 'bg-green-700 text-white' }
    }
    const map: Record<string, StatusConfig> = {
      alive:       { text: t('status.alive'),      bgClass: 'bg-green-700 text-white' },
      killed:      { text: t('status.killed'),      bgClass: 'bg-red-700 text-white' },
      may_respawn: { text: t('status.mayRespawn'),  bgClass: 'bg-yellow-700 text-white' },
      respawning:  { text: t('status.respawning'),  bgClass: 'bg-blue-700 text-white' },
      not_found:   { text: t('status.notFound'),    bgClass: 'bg-gray-400 dark:bg-gray-700 text-white' },
      unknown:     { text: t('status.unknown'),     bgClass: 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300' },
    }
    return map[status] ?? map.unknown
  }

  return { getStatusConfig }
}
