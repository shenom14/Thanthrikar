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
    const manualClaimInput = document.getElementById("manual-claim-input");
    const sendClaimBtn = document.getElementById("send-claim-btn");

    let isMicCapturing = false;

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
            // Open a dedicated tab that requests mic permission and streams real audio.
            // audio_capture.js in that tab captures 16kHz PCM audio via AudioWorklet
            // and sends Int16Array chunks back via chrome.runtime.sendMessage.
            chrome.tabs.create({
                url: 'chrome-extension://' + chrome.runtime.id + '/audio_capture.html',
                active: false
            }, function (tab) {
                isMicCapturing = true;
                captureMicBtn.innerText = "⏹ Stop Mic Capture";
                document.getElementById("mic-status").innerText = "🎙️ Microphone is live — capturing audio...";
            });
        } catch (e) {
            console.error("Mic error", e);
            document.getElementById("mic-status").innerText = "Error accessing mic: " + e.message;
        }
    });

    function stopAudioCapture() {
        // Tell the audio capture tab to release the mic stream before closing
        chrome.tabs.query({
            url: 'chrome-extension://' + chrome.runtime.id + '/audio_capture.html'
        }, function (tabs) {
            tabs.forEach(tab => {
                chrome.tabs.sendMessage(tab.id, { action: "stop_capture" }).catch(() => { });
                // Give it a moment to release, then close
                setTimeout(() => chrome.tabs.remove(tab.id), 200);
            });
        });

        isMicCapturing = false;
        captureMicBtn.innerText = "🎤 Capture Mic Audio";
        document.getElementById("mic-status").innerText = "Stopped.";
    }

    sendClaimBtn.addEventListener("click", () => {
        const claimText = manualClaimInput.value.trim();
        if (!claimText) return alert("Please enter a claim to test");

        // Send the text exactly as the audio transcript chunks would be sent
        chrome.runtime.sendMessage({ action: "audio_data", data: claimText, isAudio: false });

        // Show feedback in UI
        document.getElementById("ai-insights").innerText = "Sent: " + claimText + "\nWaiting for backend...";
        manualClaimInput.value = "";
    });

    // Listen for messages from background (WS events) and audio_capture tab (status)
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.type === "ws_status") {
            updateWsDot(request.connected);
        } else if (request.type === "transcript") {
            const tBox = document.getElementById("live-transcript");
            if (tBox.innerText.includes("Start speaking...")) tBox.innerText = "";
            tBox.innerText += " " + request.text;
        } else if (request.type === "insight") {
            document.getElementById("ai-insights").innerText = request.message || "Insight received.";
            document.getElementById("follow-up-question").innerText = request.follow_up || "None";
        } else if (request.type === "heartbeat") {
            const insightBox = document.getElementById("ai-insights");
            if (insightBox.innerText.includes("Waiting for backend...")) {
                insightBox.innerText = insightBox.innerText.replace("Waiting for backend...", "Processed (No actionable claims detected).");
            }
        } else if (request.type === "mic_status") {
            // Status updates from audio_capture.js
            document.getElementById("mic-status").innerText = request.message || "";
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
