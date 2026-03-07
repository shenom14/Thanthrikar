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
    // --- PREP MODE HANDLERS ---
    if (request.action === "generate_questions") {
        fetch(`${API_BASE_URL}/api/v1/generate-questions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request.payload)
        })
            .then(res => {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(data => sendResponse({ success: true, data }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true; // Keep channel open
    }

    if (request.action === "generate_followup") {
        fetch(`${API_BASE_URL}/api/v1/generate-followup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                current_question: request.current_question,
                candidate_context: request.candidate_context
            })
        })
            .then(res => {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(data => sendResponse({ success: true, follow_up_question: data.follow_up_question }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
    }

    // --- LIVE MODE HANDLERS ---
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
        sendAudioToWebSocket(request.data, request.isAudio !== false);
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
            sendRawToSocket(queued.data, queued.isAudio);
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
 * audio_capture.js sends compressed webm audio as a Base64 string.
 * We decode the Base64 string into an ArrayBuffer and send it as a binary WebSocket frame.
 * 
 * Plain string data (e.g. from the manual claim input) is sent as a text frame.
 */
function sendAudioToWebSocket(data, isAudio = true) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        sendRawToSocket(data, isAudio);
    } else {
        // Queue data if the connection is dropped to prevent data loss
        audioQueue.push({ data, isAudio });
    }
}

function base64ToArrayBuffer(base64) {
    const binaryString = atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
}

function sendRawToSocket(data, isAudio = true) {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;

    if (isAudio && typeof data === "string") {
        try {
            // Compressed webm audio blob as base64 string
            const buffer = base64ToArrayBuffer(data);
            socket.send(buffer);
        } catch (e) {
            console.error("Failed to decode base64 audio", e);
        }
    } else if (typeof data === "string") {
        // Text data (manual claims)
        socket.send(data);
    }
}

function notifyPopup(data) {
    chrome.runtime.sendMessage(data).catch(() => {
        // Ignore errors when popup is closed
    });
}
