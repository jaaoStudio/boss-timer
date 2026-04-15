export function useNotification() {

  function isSupported(): boolean {
    return 'Notification' in window
  }

  function getPermission(): NotificationPermission | 'unsupported' {
    if (!isSupported()) return 'unsupported'
    return Notification.permission
  }

  async function requestPermission(): Promise<NotificationPermission | 'unsupported'> {
    if (!isSupported()) return 'unsupported'
    if (Notification.permission === 'granted') return 'granted'
    if (Notification.permission === 'denied') return 'denied'
    return await Notification.requestPermission()
  }

  function sendNotification(title: string, body: string) {
    if (!isSupported() || Notification.permission !== 'granted') return

    try {
      new Notification(title, {
        body,
        icon: '/leaf64px.png',
        badge: '/leaf24px.png',
        tag: `boss-timer-${Date.now()}`, // unique tag to allow multiple notifications
        requireInteraction: false,
      })
    } catch (e) {
      console.warn('Failed to send notification:', e)
    }
  }

  return { isSupported, getPermission, requestPermission, sendNotification }
}
