import { defineStore, storeToRefs } from 'pinia';
import { ref } from 'vue';
import apiService from '@/services/apiService';
import { useAppInfoStore } from './appInfo';
import { useBossStore } from './bossStore';
import { useRoomStore } from './roomStore';

export const useWebSocketStore = defineStore('websocket', () => {
    const socket = ref(null);

    const isManualDisconnect = ref(false);
    const reconnectAttempts = ref(0);
    const maxReconnectAttempts = 5;
    let reconnectTimeout = null;

    // Get other stores
    const appInfoStore = useAppInfoStore();
    const bossStore = useBossStore();
    const roomStore = useRoomStore();
    const { isConnected } = storeToRefs(roomStore);

    function connect() {
        if (socket.value && socket.value.readyState === WebSocket.OPEN) {
            console.log("WebSocket already connected.");
            return;
        }

        try {
            socket.value = apiService.createWebSocket(); // This now creates a global WebSocket

            socket.value.onopen = () => {
                console.log("WebSocket connected.");
                isConnected.value = true;
                reconnectAttempts.value = 0;
                isManualDisconnect.value = false;
            };

            socket.value.onmessage = (event) => {
                const message = JSON.parse(event.data);
                handleMessage(message);
            };

            socket.value.onclose = () => {
                console.log("WebSocket disconnected.");
                isConnected.value = false;
                if (!isManualDisconnect.value) {
                    attemptReconnect();
                }
            };

            socket.value.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

        } catch (error) {
            console.error("Failed to create WebSocket:", error);
        }
    }

    function disconnect() {
        if (socket.value) {
            isManualDisconnect.value = true;
            socket.value.close();
            socket.value = null;
        }
    }

    function sendMessage(message) {
        if (socket.value && socket.value.readyState === WebSocket.OPEN) {
            socket.value.send(JSON.stringify(message));
        } else {
            console.error('WebSocket is not connected.');
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
                bossStore.setBossRecords(message.boss_records);
                break;
            case 'boss_update':
                bossStore.updateBossRecord(message.data);
                break;
            case 'user_count_update':
                roomStore.setUserCount(message.count);
                break;
            case 'error':
                console.error('Received error from server:', message.message);
                // Optionally, show a message to the user
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
                console.log(`WebSocket reconnecting... attempt ${reconnectAttempts.value}`);
                connect();
            }, 2000 * reconnectAttempts.value);
        } else {
            console.error('WebSocket max reconnect attempts reached.');
        }
    }

    // Heartbeat
    setInterval(() => {
        if (isConnected.value) {
            sendMessage({ type: 'ping' });
        }
    }, 30000);

    return {
        socket,
        isConnected,
        connect,
        disconnect,
        sendMessage
    };
});
