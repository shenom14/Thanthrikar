/**
 * popup.js — AI Interview Copilot (JD-Driven Engine)
 *
 * Workflow:
 *   Step 1 → Role + Candidate info input
 *   Step 2 → JD auto-generated → Interviewer sets skill weights + difficulty
 *   Step 3 → Weighted questions displayed, Next / Follow-up interactive navigation
 */

/** Extract just the GitHub username from a full URL or plain username */
function parseGitHubUsername(input) {
    if (!input) return "";
    const match = input.match(/github\.com\/([^/?#]+)/i);
    return match ? match[1].trim() : input.trim();
}

/** Normalize a LinkedIn URL — accepts full URL or just a slug */
function parseLinkedInUrl(input) {
    if (!input) return "";
    input = input.trim();
    if (!input.startsWith("http") && !input.startsWith("linkedin")) {
        return "https://www.linkedin.com/in/" + input;
    }
    return input.split("?")[0]; // Strip query params
}


const API_BASE = "http://127.0.0.1:8001";

document.addEventListener("DOMContentLoaded", () => {

    // ============================================================
    //  TOP-LEVEL MODE TABS (Prep vs Live)
    // ============================================================
    document.getElementById("app-mode-prep").addEventListener("click", () => {
        document.getElementById("app-mode-prep").classList.add("active");
        document.getElementById("app-mode-live").classList.remove("active");
        document.getElementById("app-view-prep").classList.add("active");
        document.getElementById("app-view-live").classList.remove("active");
    });
    document.getElementById("app-mode-live").addEventListener("click", () => {
        document.getElementById("app-mode-live").classList.add("active");
        document.getElementById("app-mode-prep").classList.remove("active");
        document.getElementById("app-view-live").classList.add("active");
        document.getElementById("app-view-prep").classList.remove("active");
    });

    // ============================================================
    //  PREP MODE — JD-DRIVEN MULTI-STEP WIZARD
    // ============================================================

    // State
    let currentStep = 1;
    let jdData = null;         // JD returned from backend (skills, role, etc.)
    let skillWeights = {};     // { "Python": 40, "Docker": 30, ... }
    let selectedDifficulty = "mid";
    let questionsQueue = [];   // flat array of question objects
    let currentQIndex = 0;
    let followUpHistory = [];  // [{question, response}]
    let candidateSession = {}; // Stores name, role, github_repos, jd_skills

    // Helper: show a step and update dot indicators
    function goToStep(step) {
        document.querySelectorAll(".step").forEach(el => el.classList.remove("active"));
        document.getElementById(`prep-step-${step}`).classList.add("active");
        for (let i = 1; i <= 4; i++) {
            const dot = document.getElementById(`dot-${i}`);
            if (!dot) continue;
            dot.classList.remove("active", "done");
            if (i < step) dot.classList.add("done");
            if (i === step) dot.classList.add("active");
        }
        currentStep = step;
    }

    function showMsg(id, msg, isError = false) {
        const el = document.getElementById(id);
        el.textContent = msg;
        el.style.display = "block";
    }
    function hideMsg(id) {
        const el = document.getElementById(id);
        if (el) { el.textContent = ""; el.style.display = "none"; }
    }

    // ==== STEP 1: Generate JD from role ====
    document.getElementById("jd-step1-next").addEventListener("click", async () => {
        const role = document.getElementById("jd-role-select").value.trim();
        const name = document.getElementById("jd-cand-name").value.trim();
        const exp = document.getElementById("jd-cand-exp").value.trim();

        if (!role) return showMsg("jd-step1-error", "Please select a job role.", true);
        if (!name) return showMsg("jd-step1-error", "Candidate name is required.", true);
        hideMsg("jd-step1-error");

        const btn = document.getElementById("jd-step1-next");
        btn.disabled = true;
        btn.textContent = "Generating Job Description...";
        showMsg("jd-step1-status", "Contacting AI to auto-generate Job Description...");

        try {
            const res = await fetch(`${API_BASE}/api/v1/jd/generate-jd`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ role })
            });
            if (!res.ok) throw new Error(`Server error ${res.status}`);
            jdData = await res.json();

            // Store candidate session data for later
            candidateSession = {
                role,
                name,
                years_experience: exp || "3",
                linkedin_url: parseLinkedInUrl(document.getElementById("jd-cand-linkedin").value) || null,
                github_username: parseGitHubUsername(document.getElementById("jd-cand-github").value) || null,
                resume_text: document.getElementById("jd-cand-resume").value.trim() || ""
            };

            hideMsg("jd-step1-status");
            buildSkillWeightPanel(jdData.required_skills || []);
            goToStep(2);

        } catch (e) {
            showMsg("jd-step1-error", "Failed to generate JD: " + e.message, true);
            hideMsg("jd-step1-status");
        } finally {
            btn.disabled = false;
            btn.textContent = "Generate Job Description →";
        }
    });

    // Build the skill weight sliders from the parsed JD
    function buildSkillWeightPanel(skills) {
        const container = document.getElementById("jd-skills-list");
        container.innerHTML = "";
        skillWeights = {};

        if (!skills.length) {
            container.innerHTML = `<div style="color:#64748b;font-size:0.85rem;">No skills extracted. You can proceed with default weights.</div>`;
            return;
        }

        const defaultWeight = Math.floor(100 / skills.length);

        skills.forEach((skill, i) => {
            const weight = defaultWeight + (i === 0 ? 100 - defaultWeight * skills.length : 0);
            skillWeights[skill] = weight;

            const row = document.createElement("div");
            row.className = "skill-weight-row";
            row.innerHTML = `
                <span class="skill-label">${skill}</span>
                <input type="range" min="0" max="100" value="${weight}" data-skill="${skill}" />
                <span class="skill-weight-val" id="val-${i}">${weight}%</span>`;
            container.appendChild(row);

            row.querySelector("input[type=range]").addEventListener("input", (e) => {
                const s = e.target.dataset.skill;
                const v = parseInt(e.target.value);
                skillWeights[s] = v;
                document.getElementById(`val-${i}`).textContent = `${v}%`;
            });
        });
    }

    // Difficulty selection
    document.querySelectorAll(".diff-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".diff-btn").forEach(b => b.classList.remove("selected"));
            btn.classList.add("selected");
            selectedDifficulty = btn.dataset.diff;
        });
    });

    // Back button from step 2
    document.getElementById("jd-step2-back").addEventListener("click", () => goToStep(1));

    // ==== STEP 2: Accept weights, call generate-questions ====
    document.getElementById("jd-step2-next").addEventListener("click", async () => {
        const totalQ = parseInt(document.getElementById("jd-q-count").value) || 15;
        hideMsg("jd-step2-error");

        const btn = document.getElementById("jd-step2-next");
        btn.disabled = true;
        btn.textContent = "Analyzing Candidate & Generating Questions...";
        showMsg("jd-step2-status", "This may take 5–15 seconds. Building your personalized question set...");

        const payload = {
            ...candidateSession,
            skill_weights: skillWeights,
            difficulty: selectedDifficulty,
            total_questions: totalQ
        };

        try {
            const res = await fetch(`${API_BASE}/api/v1/jd/generate-questions`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error(`Server error ${res.status}`);
            const data = await res.json();

            questionsQueue = data.questions || [];
            if (!questionsQueue.length) throw new Error("No questions were generated.");

            // Store session objects for follow-up calls
            candidateSession.github_repositories = data.github_repositories || [];
            candidateSession.jd_skills = jdData.required_skills || [];

            currentQIndex = 0;
            followUpHistory = [];

            hideMsg("jd-step2-status");
            goToStep(3);
            renderCurrentQuestion();

        } catch (e) {
            showMsg("jd-step2-error", "Failed to generate questions: " + e.message, true);
            hideMsg("jd-step2-status");
        } finally {
            btn.disabled = false;
            btn.textContent = "Generate Interview Questions →";
        }
    });

    // ==== STEP 3: Flashcard nav ====

    function renderCurrentQuestion() {
        if (!questionsQueue.length) return;
        const q = questionsQueue[currentQIndex];

        document.getElementById("q-counter").textContent = `Q ${currentQIndex + 1} / ${questionsQueue.length}`;
        document.getElementById("q-category").textContent = (q.category || "general").replace(/_/g, " ").toUpperCase();
        document.getElementById("q-jd-skill").textContent = q.jd_skill ? `# ${q.jd_skill}` : "";
        document.getElementById("q-difficulty").textContent = (q.difficulty || selectedDifficulty).toUpperCase();
        document.getElementById("q-text").textContent = q.question || "No question text.";
        document.getElementById("q-reasoning").textContent = "Goal: " + (q.reasoning || "Probe candidate's depth of knowledge.");

        // Reset follow-up UI
        document.getElementById("followup-stack").innerHTML = "";
        followUpHistory = [];

        const nextBtn = document.getElementById("next-btn");
        if (currentQIndex >= questionsQueue.length - 1) {
            nextBtn.textContent = "End of Questions";
            nextBtn.disabled = true;
            nextBtn.classList.add("btn-secondary");
        } else {
            nextBtn.textContent = "Next Question →";
            nextBtn.disabled = false;
            nextBtn.classList.remove("btn-secondary");
        }
    }

    // Next Question
    document.getElementById("next-btn").addEventListener("click", () => {
        if (currentQIndex < questionsQueue.length - 1) {
            currentQIndex++;
            renderCurrentQuestion();
        }
    });

    // Follow-Up Question — sends last response text (or empty string as placeholder)
    document.getElementById("followup-btn").addEventListener("click", async () => {
        const q = questionsQueue[currentQIndex];
        if (!q) return;

        const btn = document.getElementById("followup-btn");
        btn.disabled = true;
        btn.textContent = "Generating Follow-up...";

        const payload = {
            candidate_response: "(Interviewer requesting a follow-up probe)",
            base_question: q.question,
            skill_weights: skillWeights,
            github_repositories: candidateSession.github_repositories || [],
            experience_years: candidateSession.years_experience || "3",
            role: candidateSession.role,
            jd_skills: candidateSession.jd_skills || [],
            follow_up_history: followUpHistory
        };

        try {
            const res = await fetch(`${API_BASE}/api/v1/jd/generate-followup`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            if (!res.ok) throw new Error(`Server error ${res.status}`);
            const data = await res.json();
            const fq = data.follow_up_question || "No follow-up generated.";

            // Record history
            followUpHistory.push({
                question: fq,
                response: "(Candidate response not yet given)"
            });

            // Append to stack
            const stack = document.getElementById("followup-stack");
            const item = document.createElement("div");
            item.className = "followup-item";
            item.innerHTML = `<div class="followup-label">Follow-Up ${followUpHistory.length}</div>${fq}`;
            stack.appendChild(item);
            item.scrollIntoView({ behavior: "smooth" });

            document.getElementById("jd-step3-error").style.display = "none";
        } catch (e) {
            const errEl = document.getElementById("jd-step3-error");
            errEl.textContent = "Failed to generate follow-up: " + e.message;
            errEl.style.display = "block";
        } finally {
            btn.disabled = false;
            btn.textContent = "Generate Follow-Up Question";
        }
    });

    // Reset / New Interview
    document.getElementById("reset-btn").addEventListener("click", () => {
        questionsQueue = [];
        currentQIndex = 0;
        followUpHistory = [];
        jdData = null;
        skillWeights = {};
        candidateSession = {};

        // Clear form fields
        document.getElementById("jd-role-select").value = "";
        document.getElementById("jd-cand-name").value = "";
        document.getElementById("jd-cand-exp").value = "";
        document.getElementById("jd-cand-linkedin").value = "";
        document.getElementById("jd-cand-github").value = "";
        document.getElementById("jd-cand-resume").value = "";
        document.getElementById("jd-skills-list").innerHTML = "";

        goToStep(1);
    });

    // ============================================================
    //  LIVE COPILOT MODE
    // ============================================================
    let isMicCapturing = false;

    chrome.runtime.sendMessage({ action: "get_status" }, (res) => {
        if (res && res.isActive) {
            document.getElementById("setup-view").style.display = "none";
            document.getElementById("active-view").style.display = "block";
            document.getElementById("session-id-display").textContent = res.sessionId;
            updateWsDot(res.socketReady);
        }
    });

    document.getElementById("start-btn").addEventListener("click", () => {
        const candidateId = document.getElementById("candidate-id-input").value.trim();
        if (!candidateId) return alert("Please enter a Candidate ID");
        const btn = document.getElementById("start-btn");
        btn.disabled = true; btn.textContent = "Starting...";
        chrome.runtime.sendMessage({ action: "start_session", candidateId }, (res) => {
            if (res && res.success) {
                document.getElementById("setup-view").style.display = "none";
                document.getElementById("active-view").style.display = "block";
                document.getElementById("candidate-id-display").textContent = candidateId;
                document.getElementById("session-id-display").textContent = res.session.id;
            } else {
                alert("Failed to start: " + (res && res.error ? res.error : "Unknown error"));
                btn.disabled = false; btn.textContent = "Start Session";
            }
        });
    });

    document.getElementById("end-btn").addEventListener("click", () => {
        stopAudioCapture();
        chrome.runtime.sendMessage({ action: "end_session" }, () => {
            document.getElementById("setup-view").style.display = "block";
            document.getElementById("active-view").style.display = "none";
            const btn = document.getElementById("start-btn");
            btn.disabled = false; btn.textContent = "Start Session";
            updateWsDot(false);
        });
    });

    document.getElementById("capture-mic-btn").addEventListener("click", () => {
        if (isMicCapturing) { stopAudioCapture(); return; }
        chrome.tabs.create({
            url: "chrome-extension://" + chrome.runtime.id + "/audio_capture.html",
            active: false
        }, () => {
            isMicCapturing = true;
            document.getElementById("capture-mic-btn").textContent = "Stop Mic Capture";
            document.getElementById("mic-status").textContent = "Microphone is live — capturing audio...";
        });
    });

    function stopAudioCapture() {
        chrome.tabs.query({ url: "chrome-extension://" + chrome.runtime.id + "/audio_capture.html" }, (tabs) => {
            tabs.forEach(tab => {
                chrome.tabs.sendMessage(tab.id, { action: "stop_capture" }).catch(() => {});
                setTimeout(() => chrome.tabs.remove(tab.id), 200);
            });
        });
        isMicCapturing = false;
        document.getElementById("capture-mic-btn").textContent = "Capture Mic Audio";
        document.getElementById("mic-status").textContent = "Stopped.";
    }

    document.getElementById("send-claim-btn").addEventListener("click", () => {
        const claimText = document.getElementById("manual-claim-input").value.trim();
        if (!claimText) return alert("Please enter a claim to test");
        chrome.runtime.sendMessage({ action: "audio_data", data: claimText, isAudio: false });
        document.getElementById("ai-insights").textContent = "Sent: " + claimText + "\nWaiting for backend...";
        document.getElementById("manual-claim-input").value = "";
    });

    chrome.runtime.onMessage.addListener((request) => {
        if (request.type === "ws_status") updateWsDot(request.connected);
        else if (request.type === "transcript") {
            const tBox = document.getElementById("live-transcript");
            if (tBox.querySelector("em")) tBox.textContent = "";
            tBox.textContent += " " + request.text;
        } else if (request.type === "insight") {
            document.getElementById("ai-insights").textContent = request.message || "Insight received.";
            document.getElementById("follow-up-question").textContent = request.follow_up || "None";
        } else if (request.type === "heartbeat") {
            const b = document.getElementById("ai-insights");
            if (b.textContent.includes("Waiting for backend...")) {
                b.textContent = b.textContent.replace("Waiting for backend...", "Processed (No actionable claims detected).");
            }
        } else if (request.type === "mic_status") {
            document.getElementById("mic-status").textContent = request.message || "";
        }
    });

    function updateWsDot(connected) {
        const dot = document.getElementById("ws-status");
        if (connected) { dot.classList.add("active"); dot.title = "Connected"; }
        else { dot.classList.remove("active"); dot.title = "Disconnected"; }
    }
});
