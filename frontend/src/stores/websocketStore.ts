import { defineStore, storeToRefs } from 'pinia';
import { ref } from 'vue';
import apiService from '@/services/apiService';
import { useAppInfoStore } from './appInfo';
import { useBossStore } from './bossStore';
import { useRoomStore } from './roomStore';

export const useWebSocketStore = defineStore('websocket', () => {
    const socket = ref(null);
    const messageQueue = ref([]); // A queue for messages sent before connection is open

    const isManualDisconnect = ref(false);
    const reconnectAttempts = ref(0);
    const maxReconnectAttempts = 5;
    let reconnectTimeout = null;

    // Get other stores
    const appInfoStore = useAppInfoStore();
    const bossStore = useBossStore();
    const roomStore = useRoomStore();
    const { isConnected } = storeToRefs(roomStore);

    // This function sends all queued messages.
    // It should only be called when the connection is confirmed to be open.
    function processMessageQueue() {
        while (messageQueue.value.length > 0) {
            const message = messageQueue.value.shift();
            // console.log("Sending queued message:", message);
            socket.value.send(JSON.stringify(message));
        }
    }

    function connect() {
        // Prevent multiple connection attempts
        if (socket.value && socket.value.readyState === WebSocket.OPEN) {
            console.log("WebSocket already connected.");
            return;
        }
        if (socket.value && socket.value.readyState === WebSocket.CONNECTING) {
            console.log("WebSocket connection already in progress.");
            return;
        }

        try {
            socket.value = apiService.createWebSocket();

            socket.value.onopen = () => {
                console.log("WebSocket connected.");
                isConnected.value = true;
                reconnectAttempts.value = 0;
                isManualDisconnect.value = false;
                processMessageQueue();
                // 重連後自動重新加入房間
                const currentRoomId = roomStore.roomId;
                if (currentRoomId) {
                    socket.value.send(JSON.stringify({
                        type: 'join_room',
                        payload: { room_id: currentRoomId },
                    }));
                }
            };

            socket.value.onmessage = (event) => {
                const message = JSON.parse(event.data);
                handleMessage(message);
            };

            socket.value.onclose = () => {
                console.log("WebSocket disconnected.");
                isConnected.value = false;
                socket.value = null; // Clear the socket ref on close
                if (!isManualDisconnect.value) {
                    attemptReconnect();
                }
            };

            socket.value.onerror = (error) => {
                console.error('WebSocket error:', error);
                // Errors will likely be followed by an onclose event, which will trigger reconnect logic.
            };

        } catch (error) {
            console.error("Failed to create WebSocket:", error);
        }
    }

    function disconnect() {
        if (socket.value) {
            isManualDisconnect.value = true;
            socket.value.close();
        }
    }

    function sendMessage(message) {
        // If the socket is open, send immediately.
        if (socket.value && socket.value.readyState === WebSocket.OPEN) {
            socket.value.send(JSON.stringify(message));
        } else {
            // Otherwise, queue the message.
            console.log('WebSocket not open. Queuing message.');
            messageQueue.value.push(message);
            // And if we're not already connecting, start the connection process.
            if (!socket.value || socket.value.readyState === WebSocket.CLOSED) {
                connect();
            }
        }
    }

    function handleMessage(message) {
        switch (message.type) {
            case 'pong':
                // Heartbeat response
                break;
            case 'maintenance_status_update':
                appInfoStore.setMaintenanceInfo(message.data);
                break;
            case 'room_state':
                if (message.boss_types) {
                    bossStore.setBossTypes(message.boss_types);
                }
                bossStore.setBossRecords(message.boss_records);
                roomStore.setUserCount(message.user_count);
                break;
            case 'boss_update':
                bossStore.updateBossRecord(message.data).then();
                break;
            case 'record_deleted':
                bossStore.deleteBossRecord(message.data.record_id);
                break;
            case 'user_count_update':
                roomStore.setUserCount(message.count);
                break;
            case 'error':
                console.error('Received error from server:', message.message);
                if (message.message === "Rate limit exceeded. Please slow down.") {
                    import('@/i18n').then(({ default: i18n }) => {
                        import('@/composables/useElementPlus').then(({ showMessage }) => {
                            showMessage.warning(i18n.global.t('globalErrors.rateLimitExceeded'));
                        });
                    });
                }
                break;
            default:
                console.warn('Received unknown message type:', message.type);
        }
    }

    function attemptReconnect() {
        if (reconnectAttempts.value < maxReconnectAttempts) {
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
            reconnectTimeout = setTimeout(() => {
                reconnectAttempts.value++;
                // console.log(`WebSocket reconnecting... attempt ${reconnectAttempts.value}`);
                connect();
            }, 2000 * (reconnectAttempts.value + 1)); // increase delay
        } else {
            console.error('WebSocket max reconnect attempts reached.');
        }
    }

    // Heartbeat
    setInterval(() => {
        if (isConnected.value) {
            // Use a raw ping message that doesn't get queued.
            // This avoids filling the queue with pings if connection is temporarily lost.
            if (socket.value && socket.value.readyState === WebSocket.OPEN) {
                sendMessage({ type: 'ping' });
            }
        }
    }, 30000);

    return {
        isConnected,
        connect,
        disconnect,
        sendMessage
    };
});
