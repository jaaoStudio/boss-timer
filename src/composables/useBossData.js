import { ref } from 'vue'

export function useBossData() {
  const bosses = ref([
    {
      id: 'crimson_balrog',
      name: '深紅炎魔',
      level: 120,
      hp: 8500000,
      map: '深海峽谷',
      respawnTime: '45分鐘 - 1小時',
      respawnMin: 45,
      respawnMax: 60
    },
    {
      id: 'zakum',
      name: '薩卡姆',
      level: 110,
      hp: 12000000,
      map: '死之礦山',
      respawnTime: '2小時 - 2.5小時',
      respawnMin: 120,
      respawnMax: 150
    },
    {
      id: 'horntail',
      name: '暗黑龍王',
      level: 130,
      hp: 25000000,
      map: '龍之巢穴',
      respawnTime: '3小時 - 4小時',
      respawnMin: 180,
      respawnMax: 240
    },
    {
      id: 'papulatus',
      name: '跳跳炸彈',
      level: 125,
      hp: 18000000,
      map: '時空裂縫',
      respawnTime: '1.5小時 - 2小時',
      respawnMin: 90,
      respawnMax: 120
    },
    {
      id: 'pianus',
      name: '魚王',
      level: 100,
      hp: 6000000,
      map: '海底洞穴',
      respawnTime: '30分鐘 - 45分鐘',
      respawnMin: 30,
      respawnMax: 45
    }
  ])

  return {
    bosses
  }
}