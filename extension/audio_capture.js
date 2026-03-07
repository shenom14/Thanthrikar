let mediaStream = null;
let mediaRecorder = null;
let isCapturing = false;

async function startCapture() {
    try {
        chrome.runtime.sendMessage({ type: "mic_status", message: "Requesting microphone access..." }).catch(() => { });

        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        isCapturing = true;

        function recordCycle() {
            // Guard: if stopped externally, do not restart
            if (!isCapturing || !mediaStream) return;

            // Create a fresh MediaRecorder each cycle → each chunk is a complete WebM file
            // with its own header, so Groq Whisper can decode every single chunk.
            // (Using start(N) timeslice does NOT do this — only the first chunk has the header.)
            mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' });

            mediaRecorder.ondataavailable = (event) => {
                if (!isCapturing) return;
                if (event.data.size > 500) {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64Data = reader.result.split(',')[1];
                        chrome.runtime.sendMessage({ action: "audio_data", data: base64Data });
                    };
                    reader.readAsDataURL(event.data);
                }
            };

            mediaRecorder.start();

            // After 3 seconds, stop this recorder (fires ondataavailable) and start the next cycle
            setTimeout(() => {
                if (isCapturing && mediaRecorder && mediaRecorder.state === "recording") {
                    mediaRecorder.stop();   // triggers ondataavailable with the full WebM
                    recordCycle();          // only restarts if isCapturing is still true
                }
            }, 3000);
        }

        recordCycle();

        document.getElementById("status").innerText = "Microphone is active — streaming to Groq Whisper...";
        chrome.runtime.sendMessage({ type: "mic_status", message: "Microphone active - streaming audio to backend..." }).catch(() => { });

    } catch (e) {
        console.error("Mic error", e);
        const errorMsg = "Error accessing mic: " + e.message;
        document.getElementById("status").innerText = errorMsg;
        chrome.runtime.sendMessage({ type: "mic_status", message: errorMsg }).catch(() => { });
    }
}

function stopCapture() {
    isCapturing = false;   // Set FIRST so the recordCycle setTimeout won't restart

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        mediaRecorder = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
        mediaStream = null;
    }
    document.getElementById("status").innerText = "Stopped.";
    chrome.runtime.sendMessage({ type: "mic_status", message: "Microphone stopped." }).catch(() => { });
}

window.addEventListener('load', startCapture);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "stop_capture") {
        stopCapture();
        sendResponse({ stopped: true });
    }
});
