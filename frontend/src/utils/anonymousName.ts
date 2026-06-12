type LocalePair = [string, string] // [zh, en]

const ADJECTIVES: LocalePair[] = [
  ['可疑的', 'Suspicious'],
  ['陌生的', 'Strange'],
  ['愛坐牢的', 'Jailed'],
  ['特殊的', 'Rare'],
  ['史詩的', 'Epic'],
  ['罕見的', 'Unique'],
  ['傳說的', 'Legendary'],
  ['附加的', 'Additional'],
  ['神秘的', 'Arcane'],
  ['漆黑的', 'Pitch-Black'],
  ['永恆的', 'Eternal'],
  ['創世的', 'Genesis'],
  ['苦痛的', 'Painful'],
  ['瘋狂的', 'Mad'],
  ['巨大的', 'Colossal'],
  ['燃燒的', 'Burning'],
  ['極限的', 'Hyper'],
  ['完美的', 'Perfect'],
  ['輪迴的', 'Frenzy'],
  ['頂級的', 'Superior'],
  ['絕版的', 'Legacy'],
  ['很肝的', 'Grindy'],
  ['課金的', 'Pay-to-Win'],
  ['划水的', 'Leeching'],
  ['單機的', 'Solo'],
  ['被砍的', 'Nerfed'],
  ['起飛的', 'Buffed'],
  ['歐洲的', 'RNG-Blessed'],
  ['非洲的', 'RNG-Cursed'],
  ['暴力的', 'Overpowered'],
]

const JOB_NAMES: LocalePair[] = [
  ['英雄', 'Hero'],
  ['聖騎士', 'Paladin'],
  ['黑騎士', 'Dark Knight'],
  ['大魔導士(火/毒)', 'Arch Mage (F/P)'],
  ['大魔導士(冰/雷)', 'Arch Mage (I/L)'],
  ['主教', 'Bishop'],
  ['箭神', 'Bowmaster'],
  ['神射手', 'Marksman'],
  ['開拓者', 'Pathfinder'],
  ['夜使者', 'Night Lord'],
  ['暗影神偷', 'Shadower'],
  ['影武者', 'Dual Blade'],
  ['拳霸', 'Buccaneer'],
  ['槍神', 'Corsair'],
  ['重砲指揮官', 'Cannoneer'],
  ['米哈逸', 'Mihile'],
  ['聖魂劍士', 'Dawn Warrior'],
  ['烈焰巫師', 'Blaze Wizard'],
  ['破風使者', 'Wind Archer'],
  ['暗夜行者', 'Night Walker'],
  ['閃雷悍將', 'Thunder Breaker'],
  ['爆拳槍神', 'Blaster'],
  ['煉獄巫師', 'Battle Mage'],
  ['狂豹獵人', 'Wild Hunter'],
  ['機甲戰神', 'Mechanic'],
  ['惡魔殺手', 'Demon Slayer'],
  ['惡魔復仇者', 'Demon Avenger'],
  ['傑諾', 'Xenon'],
  ['狂狼勇士', 'Aran'],
  ['龍魔導士', 'Evan'],
  ['精靈遊俠', 'Mercedes'],
  ['幻影俠盜', 'Phantom'],
  ['夜光', 'Luminous'],
  ['隱月', 'Shade'],
  ['凱撒', 'Kaiser'],
  ['卡蒂娜', 'Cadena'],
  ['天使破壞者', 'Angelic Buster'],
  ['凱殷', 'Kain'],
  ['阿戴爾', 'Adele'],
  ['伊利恩', 'Illium'],
  ['亞克', 'Ark'],
  ['卡莉', 'Khali'],
  ['虎影', 'Hoyoung'],
  ['菈菈', 'Lara'],
  ['神之子', 'Zero'],
  ['凱內西斯', 'Kinesis'],
  ['劍豪', 'Hayato'],
  ['陰陽師', 'Kanna'],
  ['墨玄', 'Mo Xuan'],
  ['琳恩', 'Lynn'],
]

const EASTER_EGGS: LocalePair[] = [
  ['可疑的冒險家', 'Suspicious Adventurer'],
  ['陌生的冒險家', 'Strange Adventurer'],
]

export function generateRandomName(locale: string = 'zh'): string {
  if (Math.random() < 0.2) {
    const pick = EASTER_EGGS[Math.floor(Math.random() * EASTER_EGGS.length)]
    return locale === 'en' ? pick[1] : pick[0]
  }
  const adj = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)]
  const job = JOB_NAMES[Math.floor(Math.random() * JOB_NAMES.length)]
  if (locale === 'en') {
    return `${adj[1]} ${job[1]}`
  }
  return `${adj[0]}${job[0]}`
}