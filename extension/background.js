/**
 * background.js
 * 
 * Service Worker for the AI Interview Copilot.
 * Responsibilities:
 * - Communicate with the FastAPI backend over REST/WebSockets.
 * - Manage robust WebSocket reconnects.
 * - Push real-time insights to popup.html.
 */

const API_BASE_URL = "http://127.0.0.1:8001";
const WS_BASE_URL = "ws://127.0.0.1:8001";

let socket = null;
let currentSessionId = null;
let isConnecting = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 15;
let audioQueue = [];

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "start_session") {
        startSession(request.candidateId)
            .then(sessionData => sendResponse({ success: true, session: sessionData }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true; // Keep channel open for async response
    }

    if (request.action === "end_session") {
        endSession()
            .then(() => sendResponse({ success: true }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
    }

    if (request.action === "audio_data") {
        sendAudioToWebSocket(request.data);
    }

    if (request.action === "get_status") {
        sendResponse({
            isActive: currentSessionId !== null,
            sessionId: currentSessionId,
            socketReady: socket && socket.readyState === WebSocket.OPEN
        });
    }
});

async function startSession(candidateId) {
    console.log(`[Copilot] Starting session for candidate ${candidateId}`);
    try {
        const response = await fetch(`${API_BASE_URL}/interviews/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ candidate_id: candidateId })
        });

        if (!response.ok) throw new Error("Failed to start session on backend");

        const data = await response.json();
        currentSessionId = data.id;

        // Init WebSocket
        connectWebSocket();
        return data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

async function endSession() {
    if (!currentSessionId) return;
    try {
        await fetch(`${API_BASE_URL}/interviews/${currentSessionId}/end`, { method: 'POST' });
        currentSessionId = null;
        if (socket) {
            socket.close(1000, "Session ended by user");
        }
    } catch (e) {
        console.error("Error ending session", e);
    }
}

function connectWebSocket() {
    if (!currentSessionId || isConnecting) return;

    isConnecting = true;
    console.log(`[Copilot] Connecting WebSocket for session ${currentSessionId}...`);

    socket = new WebSocket(`${WS_BASE_URL}/ws/interviewStream/${currentSessionId}`);
    socket.binaryType = "arraybuffer";

    socket.onopen = () => {
        console.log("[Copilot] WebSocket connected.");
        isConnecting = false;
        reconnectAttempts = 0;
        notifyPopup({ type: "ws_status", connected: true });

        // Flush any queued audio data
        while (audioQueue.length > 0) {
            let queued = audioQueue.shift();
            sendRawToSocket(queued);
        }
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            notifyPopup(data); // Forward insights/heartbeats to UI
        } catch (e) {
            console.error("Cannot parse WS message:", event.data);
        }
    };

    socket.onclose = (event) => {
        isConnecting = false;
        console.log(`[Copilot] WebSocket closed. Code: ${event.code}, Reason: ${event.reason || "Server unavailable"}`);
        notifyPopup({ type: "ws_status", connected: false });

        if (currentSessionId && event.code !== 1000) {
            handleReconnect();
        } else {
            // Clean close or session ended intentionally
            socket = null;
        }
    };

    socket.onerror = (error) => {
        isConnecting = false;
        console.warn("[Copilot] WebSocket connection issue. Retrying in background if active...");
    };
}

function handleReconnect() {
    // Prevent overlapping reconnect timers
    if (isConnecting) return;

    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000); // Exponential backoff max 10s
        console.log(`[Copilot] Reconnecting in ${delay}ms... (Attempt ${reconnectAttempts})`);
        setTimeout(connectWebSocket, delay);
    } else {
        console.warn("[Copilot] Max explicit reconnect attempts reached. Stream offline.");
        notifyPopup({ type: "ws_status", connected: false, error: "Connection lost." });
    }
}

/**
 * Converts an audio data payload to an ArrayBuffer and sends it over the WebSocket.
 * 
 * audio_capture.js sends Int16Array data serialized as a plain JS Array (because 
 * chrome.runtime.sendMessage cannot transfer typed arrays directly). We reconstruct
 * the Int16Array and send the underlying ArrayBuffer as a binary WebSocket frame.
 * 
 * Plain string data (e.g. from the manual claim input) is sent as a text frame.
 */
function sendAudioToWebSocket(audioData) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        sendRawToSocket(audioData);
    } else {
        // Queue data if the connection is dropped to prevent data loss
        audioQueue.push(audioData);
    }
}

function sendRawToSocket(data) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;

    if (typeof data === "string") {
        // Text data (manual claims or transcript text)
        socket.send(data);
    } else if (Array.isArray(data)) {
        // Int16Array data from audio_capture.js, serialized as plain Array
        const int16 = new Int16Array(data);
        socket.send(int16.buffer);
    }
}

function notifyPopup(data) {
    chrome.runtime.sendMessage(data).catch(() => {
        // Ignore errors when popup is closed
    });
}
