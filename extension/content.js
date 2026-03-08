/**
 * content.js
 * 
 * Injected into the active web page.
 * Responsibilities:
 * - Request microphone permissions (`getUserMedia`)
 * - Record audio continuously in chunks (`MediaRecorder`)
 * - Stream raw audio bytes to the FastAPI backend via WebSocket
 */

console.log("[AI Copilot] Audio capture content script loaded.");

let mediaRecorder = null;
let audioStream = null;
let audioSocket = null;
let isRecording = false;

async function startAudioCapture(sendResponse) {
    if (isRecording) {
        sendResponse({ success: true, message: "Already recording" });
        return;
    }

    try {
        console.log("[AI Copilot] Requesting microphone access...");
        // Request microphone access. Since content.js runs in the context of the webpage,
        // the browser will show a permission prompt to the user on this domain (e.g. meet.google.com).
        audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        console.log("[AI Copilot] Microphone access granted!");

        // Start recording audio chunks in webm
        mediaRecorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm;codecs=opus' });
        
        mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0) {
                // Convert blob to base64
                const buffer = await event.data.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                let binary = '';
                for (let i = 0; i < bytes.byteLength; i++) {
                    binary += String.fromCharCode(bytes[i]);
                }
                const base64Chunk = btoa(binary);
                
                // Route through background.js to avoid Mixed Content (HTTPS -> WS)
                chrome.runtime.sendMessage({
                    action: "audio_chunk",
                    data: base64Chunk
                });
            }
        };
        
        // Tells background.js to open backend WebSocket
        chrome.runtime.sendMessage({ action: "start_audio_socket" });
        
        // Record in 500ms chunks (Ultra-low latency for UI)
        mediaRecorder.start(500); 
        isRecording = true;
        
        sendResponse({ success: true });

    } catch (err) {
        console.error("[AI Copilot] Microphone access denied or not available:", err);
        sendResponse({ success: false, error: err.message });
    }
}

function stopAudioCapture() {
    if (!isRecording) return;
    
    console.log("[AI Copilot] Stopping audio capture...");
    
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
    }
    
    if (audioSocket && audioSocket.readyState === WebSocket.OPEN) {
        // graceful shutdown hint
        audioSocket.send(JSON.stringify({ action: "stop" }));
        audioSocket.close();
    }
    
    mediaRecorder = null;
    audioStream = null;
    audioSocket = null;
    isRecording = false;
}

// Listen for commands from the Popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "ping") {
        sendResponse({ status: "alive", isRecording });
        return true;
    } else if (request.action === "start_audio_capture") {
        startAudioCapture(sendResponse);
        return true; // Keep the message channel open for async response
    } else if (request.action === "stop_audio_capture") {
        stopAudioCapture();
        sendResponse({ success: true });
        return true;
    }
});
