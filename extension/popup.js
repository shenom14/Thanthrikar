/**
 * popup.js 
 * Handles UI interactions for the extension popup window.
 */

document.addEventListener("DOMContentLoaded", () => {
    const setupView = document.getElementById("setup-view");
    const activeView = document.getElementById("active-view");
    const startBtn = document.getElementById("start-btn");
    const endBtn = document.getElementById("end-btn");
    const captureMicBtn = document.getElementById("capture-mic-btn");
    const wsStatusDot = document.getElementById("ws-status");

    let isMicCapturing = false;
    let audioContext = null;
    let mediaStream = null;

    // Check current state from background script on load
    chrome.runtime.sendMessage({ action: "get_status" }, (res) => {
        if (res && res.isActive) {
            setupView.style.display = "none";
            activeView.style.display = "block";
            document.getElementById("session-id-display").innerText = res.sessionId;
            updateWsDot(res.socketReady);
        }
    });

    startBtn.addEventListener("click", () => {
        const candidateId = document.getElementById("candidate-id-input").value.trim();
        if (!candidateId) return alert("Please enter Candidate ID");

        startBtn.disabled = true;
        startBtn.innerText = "Starting...";

        chrome.runtime.sendMessage({ action: "start_session", candidateId }, (res) => {
            if (res && res.success) {
                setupView.style.display = "none";
                activeView.style.display = "block";
                document.getElementById("candidate-id-display").innerText = candidateId;
                document.getElementById("session-id-display").innerText = res.session.id;
            } else {
                alert("Failed to start: " + (res.error || "Unknown"));
                startBtn.disabled = false;
                startBtn.innerText = "Start Interview";
            }
        });
    });

    endBtn.addEventListener("click", () => {
        stopAudioCapture();
        chrome.runtime.sendMessage({ action: "end_session" }, (res) => {
            setupView.style.display = "block";
            activeView.style.display = "none";
            startBtn.disabled = false;
            startBtn.innerText = "Start Interview";
            updateWsDot(false);
        });
    });

    captureMicBtn.addEventListener("click", async () => {
        if (isMicCapturing) {
            stopAudioCapture();
            return;
        }

        try {
            // Note: getUserMedia requires permission in the manifest and might be blocked in popup contexts 
            // depending on exact Chrome security settings. Often best injected via content script,
            // but placed here as MVP audio capture logic.
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioContext = new AudioContext();
            const source = audioContext.createMediaStreamSource(mediaStream);
            const processor = audioContext.createScriptProcessor(4096, 1, 1);

            source.connect(processor);
            processor.connect(audioContext.destination);

            processor.onaudioprocess = (e) => {
                const inputData = e.inputBuffer.getChannelData(0);
                // In production, buffer float32s and send via WebSockets to backend transcriber
                chrome.runtime.sendMessage({ action: "audio_data", data: "AUDIO_BUFFER_STANDIN" });
            };

            isMicCapturing = true;
            captureMicBtn.innerText = "Stop Mic Capture";
            document.getElementById("mic-status").innerText = "Capturing and streaming...";

        } catch (e) {
            console.error("Mic error", e);
            document.getElementById("mic-status").innerText = "Error accessing mic: " + e.message;
        }
    });

    function stopAudioCapture() {
        if (audioContext) audioContext.close();
        if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
        isMicCapturing = false;
        captureMicBtn.innerText = "Capture Mic Audio";
        document.getElementById("mic-status").innerText = "Stopped.";
    }

    // Listen for WebSocket events from background
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.type === "ws_status") {
            updateWsDot(request.connected);
        } else if (request.type === "insight") {
            document.getElementById("ai-insights").innerText = request.message || "Insight received.";
            document.getElementById("follow-up-question").innerText = request.follow_up || "None";
        } else if (request.type === "heartbeat") {
            // Optional: flash UI or show activity indicator
        }
    });

    function updateWsDot(isConnected) {
        if (isConnected) {
            wsStatusDot.classList.add("active");
            wsStatusDot.title = "Connected";
        } else {
            wsStatusDot.classList.remove("active");
            wsStatusDot.title = "Disconnected";
        }
    }
});
