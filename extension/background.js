/**
 * background.js
 * 
 * Service Worker for the AI Interview Copilot.
 * Responsibilities:
 * - Communicate with the FastAPI backend over REST/WebSockets.
 * - Manage robust WebSocket reconnects.
 * - Push real-time insights to popup.html.
 */

const API_BASE_URL = "http://localhost:8000";
const WS_BASE_URL = "ws://localhost:8000";

let socket = null;
let currentSessionId = null;
let isConnecting = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

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

    socket.onopen = () => {
        console.log("[Copilot] WebSocket connected.");
        isConnecting = false;
        reconnectAttempts = 0;
        notifyPopup({ type: "ws_status", connected: true });
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
        console.log(`[Copilot] WebSocket closed. Code: ${event.code}, Reason: ${event.reason}`);
        notifyPopup({ type: "ws_status", connected: false });

        if (currentSessionId && event.code !== 1000) {
            handleReconnect();
        }
    };

    socket.onerror = (error) => {
        console.error("[Copilot] WebSocket error:", error);
    };
}

function handleReconnect() {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000); // Exponential backoff max 10s
        console.log(`[Copilot] Reconnecting in ${delay}ms... (Attempt ${reconnectAttempts})`);
        setTimeout(connectWebSocket, delay);
    } else {
        console.error("[Copilot] Max explicit reconnect attempts reached. Stream offline.");
    }
}

function sendAudioToWebSocket(audioBuffer) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        // For the current prototype, treat the payload as a text transcript chunk.
        // In a future iteration this can be upgraded to send raw audio bytes to a
        // dedicated STT endpoint, which in turn feeds transcript text into the
        // StreamingPipeline on the backend.
        if (typeof audioBuffer === "string") {
            socket.send(audioBuffer);
        }
    }
}

function notifyPopup(data) {
    chrome.runtime.sendMessage(data).catch(() => {
        // Ignore errors when popup is closed
    });
}
