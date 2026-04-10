// --- IndexedDB for custom sounds ---
const DB_NAME = 'boss-timer-sounds'
const DB_VERSION = 1
const STORE_NAME = 'custom-sounds'

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME)
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function saveCustomSound(key: string, file: File): Promise<void> {
  const arrayBuffer = await file.arrayBuffer()
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    store.put({ data: arrayBuffer, name: file.name, type: file.type }, key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

async function getCustomSound(key: string): Promise<{ data: ArrayBuffer; name: string; type: string } | null> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const request = store.get(key)
    request.onsuccess = () => resolve(request.result || null)
    request.onerror = () => reject(request.error)
  })
}

async function deleteCustomSound(key: string): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    store.delete(key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

async function hasCustomSound(key: string): Promise<boolean> {
  const sound = await getCustomSound(key)
  return sound !== null
}

// --- Web Audio API built-in sounds ---
let audioContext: AudioContext | null = null

function getAudioContext(): AudioContext {
  if (!audioContext) {
    audioContext = new AudioContext()
  }
  if (audioContext.state === 'suspended') {
    audioContext.resume()
  }
  return audioContext
}

function playTone(frequency: number, duration: number, volume: number, startTime: number, type: OscillatorType = 'sine') {
  const ctx = getAudioContext()
  const oscillator = ctx.createOscillator()
  const gainNode = ctx.createGain()

  oscillator.connect(gainNode)
  gainNode.connect(ctx.destination)

  oscillator.frequency.value = frequency
  oscillator.type = type
  gainNode.gain.value = volume

  gainNode.gain.setValueAtTime(volume, startTime)
  gainNode.gain.exponentialRampToValueAtTime(0.001, startTime + duration)

  oscillator.start(startTime)
  oscillator.stop(startTime + duration)
}

function playDefaultSound(volume: number) {
  const ctx = getAudioContext()
  const now = ctx.currentTime
  const vol = volume / 100
  playTone(800, 0.15, vol, now, 'sine')
  playTone(1050, 0.2, vol, now + 0.2, 'sine')
}

function playGentleSound(volume: number) {
  const ctx = getAudioContext()
  const now = ctx.currentTime
  const vol = (volume / 100) * 0.7
  playTone(523, 0.15, vol, now, 'sine')
  playTone(659, 0.15, vol, now + 0.18, 'sine')
  playTone(784, 0.25, vol, now + 0.36, 'sine')
}

function playUrgentSound(volume: number) {
  const ctx = getAudioContext()
  const now = ctx.currentTime
  const vol = volume / 100
  playTone(1000, 0.1, vol, now, 'square')
  playTone(1000, 0.1, vol, now + 0.15, 'square')
  playTone(1200, 0.15, vol, now + 0.3, 'square')
}

async function playCustomFromDB(key: string, volume: number) {
  const sound = await getCustomSound(key)
  if (!sound) {
    // Fallback to default if custom sound not found
    playDefaultSound(volume)
    return
  }

  const ctx = getAudioContext()
  const audioBuffer = await ctx.decodeAudioData(sound.data.slice(0)) // slice to avoid detach
  const source = ctx.createBufferSource()
  const gainNode = ctx.createGain()

  source.buffer = audioBuffer
  source.connect(gainNode)
  gainNode.connect(ctx.destination)
  gainNode.gain.value = volume / 100

  source.start(0)
}

export function useSound() {
  async function playSound(soundType: string, volume: number) {
    try {
      switch (soundType) {
        case 'gentle':
          playGentleSound(volume)
          break
        case 'urgent':
          playUrgentSound(volume)
          break
        case 'custom':
          await playCustomFromDB(soundType, volume)
          break
        case 'default':
        default:
          playDefaultSound(volume)
          break
      }
    } catch (e) {
      console.warn('Failed to play sound:', e)
    }
  }

  async function playSoundForAlert(soundType: string, alertKey: string, volume: number) {
    try {
      if (soundType === 'custom') {
        await playCustomFromDB(alertKey, volume)
      } else {
        await playSound(soundType, volume)
      }
    } catch (e) {
      console.warn('Failed to play sound:', e)
    }
  }

  function previewSound(soundType: string, alertKey: string, volume: number) {
    playSoundForAlert(soundType, alertKey, volume)
  }

  return {
    playSound,
    playSoundForAlert,
    previewSound,
    saveCustomSound,
    getCustomSound,
    deleteCustomSound,
    hasCustomSound,
  }
}
