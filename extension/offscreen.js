/**
 * offscreen.js
 *
 * Runs inside the Offscreen Document (DOM context).
 * Receives a tab capture stream ID from background.js,
 * creates a MediaRecorder, and streams audio chunks
 * over a WebSocket to the backend for Whisper transcription.
 */

const BACKEND_WS = "ws://127.0.0.1:8002/audio/tab-stream";

let mediaRecorder = null;
let mediaStream = null;
let ws = null;
let sessionId = null;

// Listen for messages from the background service worker
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.target !== "offscreen") return;  // Ignore messages not for us

    if (message.action === "start_offscreen_capture") {
        startCapture(message.streamId, message.sessionId)
            .then(() => sendResponse({ success: true }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true; // Keep channel open for async
    }

    if (message.action === "stop_offscreen_capture") {
        stopCapture();
        sendResponse({ success: true });
        return true;
    }
});

async function startCapture(streamId, sid) {
    sessionId = sid;
    console.log("[Offscreen] Starting capture. StreamId:", streamId, "SessionId:", sessionId);

    // 1. First, get the MediaStream from the stream ID
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                mandatory: {
                    chromeMediaSource: "tab",
                    chromeMediaSourceId: streamId
                }
            }
        });
    } catch (err) {
        console.error("[Offscreen] Failed to get MediaStream:", err);
        throw new Error("Failed to capture tab audio: " + err.message);
    }

    const trackCount = mediaStream.getAudioTracks().length;
    console.log("[Offscreen] MediaStream obtained. Audio tracks:", trackCount);

    if (trackCount === 0) {
        throw new Error("No audio tracks in the captured stream.");
    }

    // 2. Now open the WebSocket to the backend
    const wsUrl = sessionId ? `${BACKEND_WS}?session_id=${sessionId}` : BACKEND_WS;

    return new Promise((resolve, reject) => {
        try {
            ws = new WebSocket(wsUrl);
            ws.binaryType = "arraybuffer";
        } catch (err) {
            console.error("[Offscreen] WebSocket constructor failed:", err);
            reject(new Error("WebSocket creation failed: " + err.message));
            return;
        }

        const connectTimeout = setTimeout(() => {
            console.error("[Offscreen] WebSocket connection timed out.");
            reject(new Error("WebSocket connection timed out"));
        }, 5000);

        ws.onopen = () => {
            clearTimeout(connectTimeout);
            console.log("[Offscreen] WebSocket connected to backend.");
            startRecording();
            resolve();
        };

        ws.onmessage = (event) => {
            // Backend sends transcript and insight messages back
            try {
                const data = JSON.parse(event.data);
                // Forward to background.js which relays to popup
                chrome.runtime.sendMessage(data).catch(() => {});
            } catch (e) {
                // Ignore non-JSON messages
            }
        };

        ws.onerror = (err) => {
            clearTimeout(connectTimeout);
            console.error("[Offscreen] WebSocket connection error. Is the backend running on port 8002?");
            reject(new Error("WebSocket connection failed. Check that backend is running."));
        };

        ws.onclose = (event) => {
            console.log("[Offscreen] WebSocket closed. Code:", event.code, "Reason:", event.reason);
            ws = null;
        };
    });
}

function startRecording() {
    if (!mediaStream) {
        console.error("[Offscreen] No MediaStream available for recording.");
        return;
    }

    // Use webm/opus — widely supported, good compression
    let mimeType = "audio/webm;codecs=opus";
    if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = "audio/webm";
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            console.error("[Offscreen] No supported audio MIME type found.");
            return;
        }
    }

    mediaRecorder = new MediaRecorder(mediaStream, { mimeType });

    mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
            event.data.arrayBuffer().then(buffer => {
                ws.send(buffer);
                console.log(`[Offscreen] Sent audio chunk: ${buffer.byteLength} bytes`);
            });
        }
    };

    mediaRecorder.onstop = () => {
        console.log("[Offscreen] MediaRecorder stopped.");
    };

    mediaRecorder.onerror = (event) => {
        console.error("[Offscreen] MediaRecorder error:", event.error);
    };

    // Start with 2-second chunks
    mediaRecorder.start(2000);
    console.log("[Offscreen] MediaRecorder started (2s chunks, " + mimeType + ")");
}

function stopCapture() {
    console.log("[Offscreen] Stopping capture...");

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        try { mediaRecorder.stop(); } catch (e) {}
        mediaRecorder = null;
    }

    if (mediaStream) {
        mediaStream.getTracks().forEach(track => {
            try { track.stop(); } catch (e) {}
        });
        mediaStream = null;
    }

    if (ws) {
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
            try { ws.close(); } catch (e) {}
        }
        ws = null;
    }

    console.log("[Offscreen] Capture fully stopped.");
}
