import type { BossRecord } from '@/stores/bossStore'

export function calculateCurrentStatus(record: BossRecord, now: Date = new Date()): string {
  if (record.status !== 'killed') return record.status

  const respawnMinTime = record.respawn_min_time ? new Date(record.respawn_min_time) : null
  const respawnMaxTime = record.respawn_max_time ? new Date(record.respawn_max_time) : null

  if (respawnMaxTime && now >= respawnMaxTime) return 'alive'
  if (respawnMinTime && now >= respawnMinTime) return 'may_respawn'
  return 'respawning'
}