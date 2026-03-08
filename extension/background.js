/**
 * background.js
 * 
 * Service Worker for the AI Interview Copilot (Manifest V3).
 * Responsibilities:
 * - Manage tab audio capture via chrome.tabCapture + Offscreen Document
 * - Communicate with the FastAPI backend over REST/WebSockets
 * - Push real-time insights and transcripts to popup.html
 */

const API_BASE_URL = "http://127.0.0.1:8002";
const WS_BASE_URL = "ws://127.0.0.1:8002";

let socket = null;
let currentSessionId = null;
let isConnecting = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 15;
let textQueue = [];

// Track offscreen document state
let offscreenCreated = false;

// ====================================================================
//  Message Router
// ====================================================================
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
        return true;
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
        return true;
    }

    if (request.action === "end_session") {
        endSession()
            .then(() => sendResponse({ success: true }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
    }

    if (request.action === "meet_transcript") {
        const text = request.payload.text;
        const speaker = request.payload.speaker || "Candidate";
        notifyPopup({ type: "transcript", text: `${speaker}: ${text}` });
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(text);
        } else {
            textQueue.push(text);
        }
        return true;
    }

    if (request.action === "get_status") {
        sendResponse({
            isActive: currentSessionId !== null,
            sessionId: currentSessionId,
            socketReady: socket && socket.readyState === WebSocket.OPEN
        });
    }

    // --- TAB AUDIO CAPTURE ---
    if (request.action === "start_tab_capture") {
        startTabCapture()
            .then(() => sendResponse({ success: true }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
    }

    if (request.action === "stop_tab_capture") {
        stopTabCapture()
            .then(() => sendResponse({ success: true }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
    }

    // --- FORWARDED MESSAGES FROM OFFSCREEN (transcript/insight) ---
    if (request.type === "transcript" || request.type === "insight" || request.type === "heartbeat") {
        // The offscreen document forwards backend WebSocket messages here.
        // Relay them to the popup UI.
        notifyPopup(request);
    }
});

// ====================================================================
//  Tab Audio Capture (Offscreen Document Architecture)
// ====================================================================

async function startTabCapture() {
    console.log("[Copilot] Starting tab audio capture...");

    // 0. Clean up any stale offscreen document from a previous failed attempt
    if (offscreenCreated) {
        try {
            await chrome.offscreen.closeDocument();
            console.log("[Copilot] Closed stale offscreen document.");
        } catch (e) {
            // Ignore — may not exist
        }
        offscreenCreated = false;
    }

    // 1. Get the active tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
        throw new Error("No active tab found. Please open a meeting tab first.");
    }
    console.log(`[Copilot] Active tab: ${tab.id} — ${tab.title}`);

    // 2. Get a media stream ID for the tab
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id });
    console.log("[Copilot] Got stream ID:", streamId);

    // 3. Create the offscreen document
    try {
        await chrome.offscreen.createDocument({
            url: "offscreen.html",
            reasons: ["USER_MEDIA"],
            justification: "Tab audio capture for interview transcription"
        });
        offscreenCreated = true;
        console.log("[Copilot] Offscreen document created.");
    } catch (e) {
        if (e.message && e.message.includes("Only a single offscreen")) {
            offscreenCreated = true;
            console.log("[Copilot] Offscreen document already exists.");
        } else {
            throw e;
        }
    }

    // 4. Wait for offscreen to be ready, then send the stream ID
    await new Promise(resolve => setTimeout(resolve, 500));

    try {
        const response = await chrome.runtime.sendMessage({
            target: "offscreen",
            action: "start_offscreen_capture",
            streamId: streamId,
            sessionId: currentSessionId
        });
        if (response && !response.success) {
            throw new Error(response.error || "Offscreen capture failed");
        }
    } catch (err) {
        console.error("[Copilot] Error sending to offscreen:", err);
        // Still might work — offscreen may have received it
    }

    console.log("[Copilot] Tab capture started successfully.");
}

async function stopTabCapture() {
    console.log("[Copilot] Stopping tab audio capture...");

    // 1. Tell offscreen to stop recording
    try {
        await chrome.runtime.sendMessage({
            target: "offscreen",
            action: "stop_offscreen_capture"
        });
    } catch (e) {
        console.warn("[Copilot] Could not reach offscreen to stop:", e);
    }

    // 2. Wait briefly for cleanup
    await new Promise(resolve => setTimeout(resolve, 300));

    // 3. Close the offscreen document
    if (offscreenCreated) {
        try {
            await chrome.offscreen.closeDocument();
            offscreenCreated = false;
            console.log("[Copilot] Offscreen document closed.");
        } catch (e) {
            console.warn("[Copilot] Error closing offscreen:", e);
            offscreenCreated = false;
        }
    }

    console.log("[Copilot] Tab capture stopped.");
}

// ====================================================================
//  Session Management
// ====================================================================

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

        connectWebSocket();
        return data;
    } catch (e) {
        console.error(e);
        throw e;
    }
}

async function endSession() {
    if (!currentSessionId) return;
    
    // Stop tab capture if running
    await stopTabCapture().catch(() => {});

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

// ====================================================================
//  Interview WebSocket (receives insights from backend pipeline)
// ====================================================================

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

        while (textQueue.length > 0) {
            let text = textQueue.shift();
            socket.send(text);
        }
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            notifyPopup(data);
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
            socket = null;
        }
    };

    socket.onerror = (error) => {
        isConnecting = false;
        console.warn("[Copilot] WebSocket connection issue. Retrying in background if active...");
    };
}

function handleReconnect() {
    if (isConnecting) return;

    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
        console.log(`[Copilot] Reconnecting in ${delay}ms... (Attempt ${reconnectAttempts})`);
        setTimeout(connectWebSocket, delay);
    } else {
        console.warn("[Copilot] Max explicit reconnect attempts reached. Stream offline.");
        notifyPopup({ type: "ws_status", connected: false, error: "Connection lost." });
    }
}

// ====================================================================
//  Utilities
// ====================================================================

function notifyPopup(data) {
    chrome.runtime.sendMessage(data).catch(() => {
        // Ignore errors when popup is closed
    });
}
