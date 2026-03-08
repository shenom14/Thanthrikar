/**
 * background.js
 * 
 * Service Worker for the AI Interview Copilot.
 * Responsibilities:
 * - Communicate with the FastAPI backend over REST/WebSockets.
 * - Manage robust WebSocket reconnects.
 * - Push real-time insights to popup.html.
 */

const API_BASE_URL = "http://127.0.0.1:8002";
const WS_BASE_URL = "ws://127.0.0.1:8002";

let socket = null;
let currentSessionId = null;
let isConnecting = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 15;
let textQueue = [];
let audioSocket = null;

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

    if (request.action === "meet_transcript") {
        const text = request.payload.text;
        const speaker = request.payload.speaker || "Candidate";
        
        // 1) Immediately relay transcript to Popup UI so it shows up in the Live Transcript box
        notifyPopup({ type: "transcript", text: `${speaker}: ${text}` });
        
        // 2) Send to backend over WebSocket for AI analysis
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

    if (request.action === "start_audio_socket") {
        if (!audioSocket || audioSocket.readyState !== WebSocket.OPEN) {
            audioSocket = new WebSocket(`${WS_BASE_URL}/audio/stream`);
            audioSocket.binaryType = "arraybuffer";
            
            let sentenceBuffer = ""; // Stores partial transcript
            
            audioSocket.onopen = () => console.log("[Copilot] Audio WebSocket connected.");
            audioSocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === "transcript") {
                        // 1. Instantly display partial text in UI (Live Transcription)
                        notifyPopup({ type: "transcript", text: `Microphone: ${data.text}` });
                        
                        // 2. Accumulate for AI Processing
                        // Only send to LangChain when a complete sentence boundary is met
                        sentenceBuffer += data.text + " ";
                        if (/[.?!]\s*$/.test(data.text)) {
                            // Boundary hit! Send complete sentence
                            let finalizedSentence = sentenceBuffer.trim();
                            sentenceBuffer = ""; // Reset for next sentence
                            
                            if (socket && socket.readyState === WebSocket.OPEN) {
                                socket.send(finalizedSentence);
                            } else {
                                textQueue.push(finalizedSentence);
                            }
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            };
            audioSocket.onerror = (err) => console.error("[Copilot] Audio WebSocket Error:", err);
            audioSocket.onclose = () => {
                console.log("[Copilot] Audio WebSocket closed.");
                audioSocket = null;
            };
        }
        sendResponse({ success: true });
        return true;
    }

    if (request.action === "audio_chunk") {
        if (audioSocket && audioSocket.readyState === WebSocket.OPEN) {
            const binaryString = atob(request.data);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            audioSocket.send(bytes.buffer);
        }
        return true;
    }
    
    if (request.action === "stop_audio_socket") {
        if (audioSocket && audioSocket.readyState === WebSocket.OPEN) {
            audioSocket.close();
        }
        audioSocket = null;
        sendResponse({ success: true });
        return true;
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

        // Flush any queued text data
        while (textQueue.length > 0) {
            let text = textQueue.shift();
            socket.send(text);
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

function notifyPopup(data) {
    chrome.runtime.sendMessage(data).catch(() => {
        // Ignore errors when popup is closed
    });
}
