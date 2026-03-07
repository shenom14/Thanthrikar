let mediaStream = null;
let mediaRecorder = null;

async function startCapture() {
    try {
        chrome.runtime.sendMessage({ type: "mic_status", message: "Requesting microphone access..." }).catch(() => { });

        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Use modern MediaRecorder for highly efficient compressed audio (webm)
        mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' });

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                // Convert the compressed Blob context to a Base64 string to send to the background
                const reader = new FileReader();
                reader.onloadend = () => {
                    // Extract just the base64 payload part: "data:audio/webm;base64,....." -> "....."
                    const base64Data = reader.result.split(',')[1];
                    chrome.runtime.sendMessage({ action: "audio_data", data: base64Data });
                };
                reader.readAsDataURL(event.data);
            }
        };

        // Capture chunks every 4000 milliseconds (4 seconds)
        // This gives Groq Whisper a solid sentence to transcribe at a time.
        mediaRecorder.start(4000);

        document.getElementById("status").innerText = "Microphone is captured and streaming to Groq Whisper...";
        chrome.runtime.sendMessage({ type: "mic_status", message: "Microphone active - streaming audio to backend..." }).catch(() => { });

    } catch (e) {
        console.error("Mic error", e);
        const errorMsg = "Error accessing mic: " + e.message;
        document.getElementById("status").innerText = errorMsg;
        chrome.runtime.sendMessage({ type: "mic_status", message: errorMsg }).catch(() => { });
    }
}

function stopCapture() {
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
