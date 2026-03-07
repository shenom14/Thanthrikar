let recognition = null;
let isStopped = false;

function startCapture() {
    chrome.runtime.sendMessage({ type: "mic_status", message: "Requesting microphone access..." }).catch(() => { });

    if (!('webkitSpeechRecognition' in window)) {
        const errorMsg = "Speech recognition not supported in this browser.";
        document.getElementById("status").innerText = errorMsg;
        chrome.runtime.sendMessage({ type: "mic_status", message: errorMsg }).catch(() => { });
        return;
    }

    // Use Chrome's built-in Web Speech API. This is much more reliable
    // than streaming raw PCM arrays to a Python backend, and it's free/fast!
    recognition = new webkitSpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false; // We only want completed sentences
    recognition.lang = 'en-US';

    recognition.onstart = function () {
        isStopped = false;
        document.getElementById("status").innerText = "Microphone is captured and transcribing (Web Speech API)...";
        chrome.runtime.sendMessage({ type: "mic_status", message: "🎙️ Transcribing audio locally..." }).catch(() => { });
    };

    recognition.onresult = function (event) {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                transcript += event.results[i][0].transcript;
            }
        }

        let finalStr = transcript.trim();
        if (finalStr.length > 0) {
            console.log("Transcribed locally:", finalStr);
            // Send the transcribed text as a simple string! 
            // The backend websocket already handles string chunks perfectly.
            chrome.runtime.sendMessage({ action: "audio_data", data: finalStr });
        }
    };

    recognition.onerror = function (event) {
        console.error("Speech recognition error", event.error);
        if (event.error === 'no-speech' || event.error === 'network') {
            // Ignore minor errors, allow it to restart onend
            return;
        }
        const errorMsg = "Recognition error: " + event.error;
        document.getElementById("status").innerText = errorMsg;
        chrome.runtime.sendMessage({ type: "mic_status", message: "⚠️ " + errorMsg }).catch(() => { });
    };

    recognition.onend = function () {
        if (!isStopped) {
            // Chrome speech recognition sometimes stops automatically after a period of silence.
            // We need to continuously restart it if the user hasn't hit stop.
            try { recognition.start(); } catch (e) { }
        } else {
            document.getElementById("status").innerText = "Stopped.";
            chrome.runtime.sendMessage({ type: "mic_status", message: "Microphone stopped." }).catch(() => { });
        }
    };

    try {
        recognition.start();
    } catch (e) {
        console.error(e);
    }
}

function stopCapture() {
    isStopped = true;
    if (recognition) {
        recognition.stop();
        recognition = null;
    }
}

window.addEventListener('load', startCapture);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "stop_capture") {
        stopCapture();
        sendResponse({ stopped: true });
    }
});
