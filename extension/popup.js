/**
 * popup.js 
 * Handles UI interactions for the extension popup window in Dual-Mode.
 */

document.addEventListener("DOMContentLoaded", () => {
    // ==============================================
    // 1. DUAL-MODE TAB SWITCHING LOGIC
    // ==============================================
    const appModePrepTab = document.getElementById("app-mode-prep");
    const appModeLiveTab = document.getElementById("app-mode-live");
    const appViewPrep = document.getElementById("app-view-prep");
    const appViewLive = document.getElementById("app-view-live");

    appModePrepTab.addEventListener("click", () => {
        appModePrepTab.classList.add("active");
        appModeLiveTab.classList.remove("active");
        appViewPrep.classList.add("active");
        appViewLive.classList.remove("active");
    });

    appModeLiveTab.addEventListener("click", () => {
        appModeLiveTab.classList.add("active");
        appModePrepTab.classList.remove("active");
        appViewLive.classList.add("active");
        appViewPrep.classList.remove("active");
    });


    // ==============================================
    // 2. PREP MODE LOGIC (Original generator)
    // ==============================================
    const setupContainer = document.getElementById("setup-container");
    const interviewView = document.getElementById("interview-view");

    // Sub-Tabs
    const tabAirtable = document.getElementById("tab-airtable");
    const tabManual = document.getElementById("tab-manual");
    const viewAirtable = document.getElementById("view-airtable");
    const viewManual = document.getElementById("view-manual");

    // Elements
    const airtableSelect = document.getElementById("airtable-select");
    const btnGenAirtable = document.getElementById("generate-btn-airtable");
    const errAirtable = document.getElementById("error-msg-airtable");

    const btnGenManual = document.getElementById("generate-btn-manual");
    const errManual = document.getElementById("error-msg-manual");

    const nextBtnPrep = document.getElementById("next-btn");
    const followupBtnPrep = document.getElementById("followup-btn");
    const resetBtnPrep = document.getElementById("reset-btn");
    const followupStackEl = document.getElementById("followup-stack");

    let questionsQueue = [];
    let currentIndex = 0;
    let followUpContextPrep = [];

    // Mock Airtable Data
    const mockAirtableData = [
        { id: "rec1", name: "Alice Johnson", role: "Senior Frontend Engineer", years_experience: 6, linkedin_url: "https://linkedin.com/in/alicej", github_username: "alicejs", resume_text: "Expert in React, TypeScript, and Webpack. Performance optimization and accessibility advocate." },
        { id: "rec2", name: "Bob Builder", role: "DevOps Engineer", years_experience: 4, linkedin_url: "https://linkedin.com/in/bobops", github_username: "bobinfra", resume_text: "Built CI/CD pipelines using GitHub Actions, deployed workloads on AWS EKS and automated via Terraform." }
    ];

    mockAirtableData.forEach((candidate, index) => {
        const option = document.createElement("option");
        option.value = index;
        option.text = `${candidate.name} - ${candidate.role}`;
        airtableSelect.appendChild(option);
    });

    chrome.storage.local.get(["interviewQuestions", "currentIndex"], (res) => {
        if (res.interviewQuestions && res.interviewQuestions.length > 0) {
            questionsQueue = res.interviewQuestions;
            currentIndex = res.currentIndex || 0;
            showInterviewView();
        }
    });

    tabAirtable.addEventListener("click", () => {
        tabAirtable.classList.add("active");
        tabManual.classList.remove("active");
        viewAirtable.classList.add("active");
        viewManual.classList.remove("active");
    });

    tabManual.addEventListener("click", () => {
        tabManual.classList.add("active");
        tabAirtable.classList.remove("active");
        viewManual.classList.add("active");
        viewAirtable.classList.remove("active");
    });

    btnGenAirtable.addEventListener("click", () => {
        const payload = mockAirtableData[airtableSelect.value];
        btnGenAirtable.disabled = true;
        btnGenAirtable.innerText = "Analyzing CRM Data...";
        errAirtable.style.display = 'none';
        makeQuestionsRequest(payload, btnGenAirtable, errAirtable, "Generate Questions from CRM");
    });

    btnGenManual.addEventListener("click", () => {
        const name = document.getElementById("candidate-name").value.trim();
        const role = document.getElementById("candidate-role").value.trim();
        const exp = parseInt(document.getElementById("candidate-exp").value) || 0;
        const linkedin = document.getElementById("candidate-linkedin").value.trim();
        const github = document.getElementById("candidate-github").value.trim();
        const resume = document.getElementById("candidate-resume").value.trim();

        if (!name || !role) return showError(errManual, "Name and Role are required.");

        btnGenManual.disabled = true;
        btnGenManual.innerText = "Analyzing Candidate...";
        errManual.style.display = 'none';

        makeQuestionsRequest({
            name, role, years_experience: exp,
            resume_text: resume || "No resume provided.",
            linkedin_url: linkedin || null,
            github_username: github || null
        }, btnGenManual, errManual, "Generate Question Set");
    });

    function makeQuestionsRequest(payload, btnElement, errElement, originalBtnText) {
        chrome.runtime.sendMessage({ action: "generate_questions", payload }, (res) => {
            if (res && res.success) {
                questionsQueue = flattenQuestions(res.data.questions);
                currentIndex = 0;
                chrome.storage.local.set({ interviewQuestions: questionsQueue, currentIndex });
                showInterviewView();
                btnElement.disabled = false;
                btnElement.innerText = originalBtnText;
            } else {
                showError(errElement, "Failed to generate questions: " + (res ? res.error : "Backend unavailable. Is uvicorn running?"));
                btnElement.disabled = false;
                btnElement.innerText = originalBtnText;
            }
        });
    }

    nextBtnPrep.addEventListener("click", () => {
        if (currentIndex < questionsQueue.length - 1) {
            currentIndex++;
            followUpContextPrep = [];
            clearFollowUpStack();
            chrome.storage.local.set({ currentIndex });
            renderCurrentQuestion();
        } else {
            nextBtnPrep.disabled = true;
            nextBtnPrep.innerText = "No More Questions";
        }
    });

    followupBtnPrep.addEventListener("click", () => {
        if (!questionsQueue.length || currentIndex >= questionsQueue.length) return;
        const q = questionsQueue[currentIndex];
        followupBtnPrep.disabled = true;
        followupBtnPrep.innerText = "Generating...";
        chrome.runtime.sendMessage({
            action: "generate_followup",
            current_question: q.question,
            candidate_context: followUpContextPrep.join(" ")
        }, (res) => {
            followupBtnPrep.disabled = false;
            followupBtnPrep.innerText = "Generate Follow-up Question";
            if (res && res.success && res.follow_up_question) {
                followUpContextPrep.push(res.follow_up_question);
                appendFollowUpToStack(res.follow_up_question);
            } else {
                appendFollowUpToStack("Error: " + (res && res.error ? res.error : "Failed."), true);
            }
        });
    });

    resetBtnPrep.addEventListener("click", () => {
        chrome.storage.local.remove(["interviewQuestions", "currentIndex"]);
        questionsQueue = [];
        currentIndex = 0;
        followUpContextPrep = [];
        clearFollowUpStack();
        nextBtnPrep.disabled = false;
        nextBtnPrep.innerText = "Next Question";
        setupContainer.style.display = "block";
        interviewView.style.display = "none";
    });

    function showInterviewView() {
        setupContainer.style.display = "none";
        interviewView.style.display = "block";
        renderCurrentQuestion();
    }

    function renderCurrentQuestion() {
        if (!questionsQueue.length) return;
        const q = questionsQueue[currentIndex];
        document.getElementById("q-counter").innerText = `Question ${currentIndex + 1} of ${questionsQueue.length}`;
        document.getElementById("q-category").innerText = q.category.replace("_", " ");
        document.getElementById("q-text").innerText = q.question;
        document.getElementById("q-reasoning").innerText = q.reasoning;
        if (currentIndex >= questionsQueue.length - 1) {
            nextBtnPrep.disabled = true;
            nextBtnPrep.innerText = "End of Questions";
        }
    }

    function clearFollowUpStack() { if (followupStackEl) followupStackEl.innerHTML = ""; }

    function appendFollowUpToStack(text, isError) {
        if (!followupStackEl) return;
        const div = document.createElement("div");
        div.className = "followup-item";
        div.innerHTML = (isError ? "" : "<strong>Follow-up</strong><br>") + text;
        followupStackEl.appendChild(div);
    }

    function flattenQuestions(questionsObj) {
        let flat = [];
        for (const [category, arr] of Object.entries(questionsObj)) {
            arr.forEach(q => flat.push({ category, question: q.question, reasoning: q.reasoning }));
        }
        return flat;
    }

    function showError(errElement, msg) {
        errElement.innerText = msg;
        errElement.style.display = "block";
    }


    // ==============================================
    // 3. LIVE COPILOT LOGIC
    // ==============================================
    const setupViewLive = document.getElementById("setup-view"); // Re-using ID inside app-view-live
    const activeViewLive = document.getElementById("active-view"); // Re-using ID inside app-view-live
    const startBtnLive = document.getElementById("start-btn");
    const endBtnLive = document.getElementById("end-btn");
    const captureMicBtn = document.getElementById("capture-mic-btn");
    const wsStatusDot = document.getElementById("ws-status");
    const manualClaimInput = document.getElementById("manual-claim-input");
    const sendClaimBtn = document.getElementById("send-claim-btn");

    let isMicCapturing = false;

    chrome.runtime.sendMessage({ action: "get_status" }, (res) => {
        if (res && res.isActive) {
            setupViewLive.style.display = "none";
            activeViewLive.style.display = "block";
            document.getElementById("session-id-display").innerText = res.sessionId;
            updateWsDot(res.socketReady);
        }
    });

    startBtnLive.addEventListener("click", () => {
        const candidateId = document.getElementById("candidate-id-input").value.trim();
        if (!candidateId) return alert("Please enter Candidate ID");

        startBtnLive.disabled = true;
        startBtnLive.innerText = "Starting...";

        chrome.runtime.sendMessage({ action: "start_session", candidateId }, (res) => {
            if (res && res.success) {
                setupViewLive.style.display = "none";
                activeViewLive.style.display = "block";
                document.getElementById("candidate-id-display").innerText = candidateId;
                document.getElementById("session-id-display").innerText = res.session.id;
            } else {
                alert("Failed to start: " + (res.error || "Unknown"));
                startBtnLive.disabled = false;
                startBtnLive.innerText = "Start Interview";
            }
        });
    });

    endBtnLive.addEventListener("click", () => {
        stopAudioCapture();
        chrome.runtime.sendMessage({ action: "end_session" }, (res) => {
            setupViewLive.style.display = "block";
            activeViewLive.style.display = "none";
            startBtnLive.disabled = false;
            startBtnLive.innerText = "Start Interview";
            updateWsDot(false);
        });
    });

    captureMicBtn.addEventListener("click", async () => {
        if (isMicCapturing) {
            stopAudioCapture();
            return;
        }

        try {
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
        chrome.tabs.query({ url: 'chrome-extension://' + chrome.runtime.id + '/audio_capture.html' }, function (tabs) {
            tabs.forEach(tab => {
                chrome.tabs.sendMessage(tab.id, { action: "stop_capture" }).catch(() => { });
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

        chrome.runtime.sendMessage({ action: "audio_data", data: claimText, isAudio: false });
        document.getElementById("ai-insights").innerText = "Sent: " + claimText + "\nWaiting for backend...";
        manualClaimInput.value = "";
    });

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
