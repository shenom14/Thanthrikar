let audioContext = null;
let mediaStream = null;
let scriptProcessor = null;

async function startCapture() {
    try {
        // Notify popup that we're requesting mic permission
        chrome.runtime.sendMessage({ type: "mic_status", message: "Requesting microphone access..." }).catch(() => { });

        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });

        // Vosk requires 16000Hz sampling rate
        audioContext = new AudioContext({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(mediaStream);

        // Use ScriptProcessorNode (works in extension pages without CSP issues).
        const bufferSize = 4096;
        scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);

        scriptProcessor.onaudioprocess = (event) => {
            const float32Data = event.inputBuffer.getChannelData(0);
            const int16Data = new Int16Array(float32Data.length);

            // Convert Float32 [-1.0, 1.0] to Int16 [-32768, 32767]
            for (let i = 0; i < float32Data.length; i++) {
                let s = Math.max(-1, Math.min(1, float32Data[i]));
                int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            // Serialize as plain JS Array (chrome.runtime.sendMessage can't transfer typed arrays)
            chrome.runtime.sendMessage({ action: "audio_data", data: Array.from(int16Data) });
        };

        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        document.getElementById("status").innerText = "Microphone is captured and streaming to Vosk...";
        chrome.runtime.sendMessage({ type: "mic_status", message: "Microphone active - streaming audio to backend..." }).catch(() => { });

    } catch (e) {
        console.error("Mic error", e);
        const errorMsg = "Error accessing mic: " + e.message;
        document.getElementById("status").innerText = errorMsg;
        chrome.runtime.sendMessage({ type: "mic_status", message: errorMsg }).catch(() => { });
    }
}

function stopCapture() {
    if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
    }
    if (audioContext) {
        audioContext.close().catch(() => { });
        audioContext = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop());
        mediaStream = null;
    }
    document.getElementById("status").innerText = "Stopped.";
    chrome.runtime.sendMessage({ type: "mic_status", message: "Microphone stopped." }).catch(() => { });
}

// Start capture once loaded
window.addEventListener('load', startCapture);

// Listen for stop commands from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "stop_capture") {
        stopCapture();
        sendResponse({ stopped: true });
    }
});
