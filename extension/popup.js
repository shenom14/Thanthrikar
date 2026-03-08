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


const API_BASE = "http://127.0.0.1:8002";

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
    let loadedCandidates = {}; // Store fetched candidates dict
    let reportLog = [];        // Store [{question, candidate_answer_summary, evaluation, color}]

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

    // ==== INIT: Fetch Candidates ====
    async function loadCandidates() {
        try {
            const res = await fetch(`${API_BASE}/api/v1/jd/candidates`);
            if (res.ok) {
                const data = await res.json();
                const select = document.getElementById("jd-cand-select");
                select.innerHTML = '<option value="">-- Select a Candidate --</option>';
                data.candidates.forEach(c => {
                    loadedCandidates[c.id] = c;
                    const opt = document.createElement("option");
                    opt.value = c.id;
                    opt.textContent = c.name + (c.role ? ` - ${c.role}` : "");
                    select.appendChild(opt);
                });
            }
        } catch (e) {
            console.error("Failed to load candidates", e);
            document.getElementById("jd-cand-select").innerHTML = '<option value="">Network Error: Cannot load candidates</option>';
        }
    }

    loadCandidates();

    document.getElementById("jd-cand-select").addEventListener("change", (e) => {
        const cid = e.target.value;
        const detailBox = document.getElementById("jd-cand-details");
        if (!cid) {
            detailBox.style.display = "none";
            return;
        }
        const c = loadedCandidates[cid];
        if (c) {
            detailBox.innerHTML = `
                <strong>${c.name}</strong><br/>
                Experience: ${c.experience || "Unknown"}<br/>
                Role: ${c.role || "Unknown"}<br/>
            `;
            detailBox.style.display = "block";

            // Auto complete role if available and not yet set
            const roleSelect = document.getElementById("jd-role-select");
            if (roleSelect.value === "" && c.role) {
                Array.from(roleSelect.options).forEach(opt => {
                    if (opt.value.toLowerCase().includes(c.role.toLowerCase())) {
                        roleSelect.value = opt.value;
                    }
                });
            }
        }
    });

    // ==== STEP 1: Generate JD from role ====
    document.getElementById("jd-step1-next").addEventListener("click", async () => {
        const role = document.getElementById("jd-role-select").value.trim();
        const cid = document.getElementById("jd-cand-select").value;

        if (!role) return showMsg("jd-step1-error", "Please select a job role.", true);
        if (!cid) return showMsg("jd-step1-error", "Please select a candidate.", true);
        hideMsg("jd-step1-error");

        const candData = loadedCandidates[cid] || {};

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
                name: candData.name || "Unknown",
                years_experience: candData.experience || "3",
                linkedin_url: null,
                github_username: null,
                resume_text: candData.resume_file || "" // Resume text ideally comes from backend passing parsed content, fallback to string path or mock
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
            reportLog = [];

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

        // Manage Answer display
        const ansBtn = document.getElementById("toggle-answer-btn");
        const ansDiv = document.getElementById("q-answer");
        ansBtn.textContent = "Show Answer ▼";
        ansDiv.style.display = "none";
        ansDiv.textContent = q.recommended_answer || "No answer provided.";

        // Manage Evaluation Display
        const evalDiv = document.getElementById("evaluation-container");
        evalDiv.style.display = "block"; // Always show during a question

        // Reset inputs
        document.getElementById("interviewer-notes").value = "";

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

    // Answer Reveal
    document.getElementById("toggle-answer-btn").addEventListener("click", () => {
        const ansDiv = document.getElementById("q-answer");
        const btn = document.getElementById("toggle-answer-btn");
        if (ansDiv.style.display === "none") {
            ansDiv.style.display = "block";
            btn.textContent = "Hide Answer ▲";
        } else {
            ansDiv.style.display = "none";
            btn.textContent = "Show Answer ▼";
        }
    });

    // Evaluation Logging
    document.querySelectorAll(".eval-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            const result = e.target.dataset.result;
            const color = e.target.dataset.color;
            const qtext = document.getElementById("q-text").textContent;

            try {
                const res = await fetch(`${API_BASE}/api/v1/jd/evaluation`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        questionText: qtext,
                        evaluationResult: result,
                        colorRating: color
                    })
                });
                if (res.ok) {
                    // Save locally for report compilation
                    const notes = document.getElementById("interviewer-notes").value.trim() || "(No summary provided)";

                    // See if we already stored an eval for this question index. Overwrite if we did.
                    const existingIdx = reportLog.findIndex(r => r.qIndex === currentQIndex);
                    const logEntry = {
                        qIndex: currentQIndex,
                        question: qtext,
                        candidate_answer_summary: notes,
                        evaluation: result,
                        color: color
                    };

                    if (existingIdx !== -1) {
                        reportLog[existingIdx] = logEntry;
                    } else {
                        reportLog.push(logEntry);
                    }

                    // Flash success
                    const originalText = e.target.textContent;
                    e.target.textContent = "✔ Saved!";
                    setTimeout(() => e.target.textContent = originalText, 1000);
                } else {
                    console.error("Failed to save evaluation");
                }
            } catch (err) {
                console.error("Network error on evaluation", err);
            }
        });
    });

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
            const recommendedAnswer = data.recommended_answer || "No answer reasoning provided.";

            // Record history (we still send only the question text to the backend context)
            followUpHistory.push({
                question: fq,
                response: "(Candidate response not yet given)"
            });
            
            const fIndex = followUpHistory.length;

            // Append to stack
            const stack = document.getElementById("followup-stack");
            const item = document.createElement("div");
            item.className = "followup-item";
            item.style.background = "#0f172a";
            item.style.borderLeft = "3px solid #6366f1";
            item.style.color = "#e2e8f0";
            item.style.padding = "12px";
            item.style.marginBottom = "10px";
            item.style.borderRadius = "6px";
            
            item.innerHTML = `
                <div class="followup-label" style="color: #818cf8; margin-bottom: 6px;">Follow-Up ${fIndex}</div>
                <div style="font-size: 0.95rem; font-weight: 600; margin-bottom: 10px;">${fq}</div>
                
                <!-- Answer Reveal toggle -->
                <button class="btn btn-outline btn-sm followup-toggle-ans" style="margin-bottom: 10px; border-color: #818cf8; color: #a5b4fc;">Show Answer ▼</button>
                <div class="followup-answer" style="display: none; background: #1e1b4b; border-left: 3px solid #818cf8; color: #c7d2fe; font-size: 0.8rem; padding: 8px 10px; border-radius: 4px; margin-bottom: 10px;">
                    ${recommendedAnswer}
                </div>

                <!-- Interviewer Answer Summary -->
                <div style="margin-top: 10px; margin-bottom: 10px; padding-top: 10px; border-top: 1px solid #334155;">
                    <label>Candidate Answer Summary (Optional):</label>
                    <textarea class="followup-notes" rows="2" placeholder="Briefly summarize what they said..."></textarea>
                </div>

                <!-- Evaluation System -->
                <div style="margin-top: 5px;">
                    <label>Candidate Answer Evaluation:</label>
                    <div style="display:flex; gap: 6px; margin-top: 5px;">
                        <button class="btn followup-eval-btn" data-color="green" data-result="correct" style="flex:1; background:#16a34a; color:#fff;">🟢 Correct</button>
                        <button class="btn followup-eval-btn" data-color="yellow" data-result="partial" style="flex:1; background:#ca8a04; color:#fff;">🟡 Partial</button>
                        <button class="btn followup-eval-btn" data-color="red" data-result="incorrect" style="flex:1; background:#dc2626; color:#fff;">🔴 Incorrect</button>
                    </div>
                </div>
            `;
            stack.appendChild(item);
            
            // Bind Answer Toggle
            const toggleBtn = item.querySelector(".followup-toggle-ans");
            const ansDiv = item.querySelector(".followup-answer");
            toggleBtn.addEventListener("click", () => {
                if (ansDiv.style.display === "none") {
                    ansDiv.style.display = "block";
                    toggleBtn.textContent = "Hide Answer ▲";
                } else {
                    ansDiv.style.display = "none";
                    toggleBtn.textContent = "Show Answer ▼";
                }
            });

            // Bind Evaluation Logging for Follow-up
            item.querySelectorAll(".followup-eval-btn").forEach(btn => {
                btn.addEventListener("click", async (e) => {
                    const result = e.target.dataset.result;
                    const color = e.target.dataset.color;
                    const notes = item.querySelector(".followup-notes").value.trim() || "(No summary provided)";

                    try {
                        const res = await fetch(`${API_BASE}/api/v1/jd/evaluation`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                questionText: fq,
                                evaluationResult: result,
                                colorRating: color
                            })
                        });
                        if (res.ok) {
                            const existingIdx = reportLog.findIndex(r => r.type === 'follow_up' && r.parentIndex === currentQIndex && r.fIndex === fIndex);
                            const logEntry = {
                                type: 'follow_up',
                                parentIndex: currentQIndex,
                                fIndex: fIndex,
                                question: fq,
                                candidate_answer_summary: notes,
                                evaluation: result,
                                color: color
                            };

                            if (existingIdx !== -1) {
                                reportLog[existingIdx] = logEntry;
                            } else {
                                reportLog.push(logEntry);
                            }

                            // Flash success
                            const originalText = e.target.textContent;
                            e.target.textContent = "✔ Saved!";
                            setTimeout(() => e.target.textContent = originalText, 1000);
                        }
                    } catch (err) {
                        console.error("Network error on evaluation", err);
                    }
                });
            });

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
        reportLog = [];
        jdData = null;
        skillWeights = {};
        candidateSession = {};

        // Clear form fields
        document.getElementById("jd-role-select").value = "";
        document.getElementById("jd-cand-select").value = "";
        document.getElementById("jd-cand-details").style.display = "none";
        document.getElementById("jd-skills-list").innerHTML = "";
        document.getElementById("interviewer-notes").value = "";
        hideMsg("report-status");

        goToStep(1);
    });

    // End Interview & Generate Report
    document.getElementById("end-interview-btn").addEventListener("click", async () => {
        const btn = document.getElementById("end-interview-btn");
        const statusEl = document.getElementById("report-status");
        statusEl.textContent = "Compiling and analyzing interview data...";
        statusEl.style.display = "block";
        btn.disabled = true;

        try {
            // Strip QIndex for backend parsing
            const cleanLog = reportLog.map(l => ({
                question: l.question,
                candidate_answer_summary: l.candidate_answer_summary,
                evaluation: l.evaluation,
                color: l.color,
                // keep tracking info for the frontend plaintext builder
                type: l.type,
                parentIndex: l.parentIndex,
                fIndex: l.fIndex,
                qIndex: l.qIndex
            }));

            const payload = {
                candidate_name: candidateSession.name,
                role: candidateSession.role,
                skills: candidateSession.jd_skills || [],
                experience: candidateSession.years_experience + " years",
                achievements: (candidateSession.github_repositories || []).map(r => r.name).join(", ") || "None",
                interview_log: cleanLog.map(l => ({  // Send clean schema to backend
                    question: l.question,
                    candidate_answer_summary: l.candidate_answer_summary,
                    evaluation: l.evaluation,
                    color: l.color
                }))
            };

            const res = await fetch(`${API_BASE}/api/v1/jd/generate-summary`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!res.ok) throw new Error("Server error during AI summary compilation");
            const summary = await res.json();

            // Build Plain Text Report
            let report = `Candidate Name: ${payload.candidate_name}\n\n`;
            report += `Skills:\n${payload.skills.join(", ")}\n\n`;
            report += `Experience:\n${payload.experience}\n\n`;
            report += `Achievements:\n${payload.achievements}\n\n`;
            report += `Interview Questions:\n\n`;

            // Group logs by parent question
            const mainQuestions = cleanLog.filter(l => l.type !== 'follow_up');
            const followUps = cleanLog.filter(l => l.type === 'follow_up');

            mainQuestions.forEach((log, i) => {
                report += `Question ${i + 1}\n${log.question}\n\n`;
                report += `Candidate Answer Summary:\n${log.candidate_answer_summary}\n\n`;
                
                const evalText = log.evaluation.charAt(0).toUpperCase() + log.evaluation.slice(1);
                report += `Evaluation:\n${evalText}\n\n`;

                // Find and interleave follow-ups for this main question
                const childFollowUps = followUps.filter(f => f.parentIndex === log.qIndex);
                childFollowUps.sort((a, b) => a.fIndex - b.fIndex); // Ensure chronological order
                
                childFollowUps.forEach(fLog => {
                    report += `Follow-Up Question ${i + 1}.${fLog.fIndex}\n${fLog.question}\n\n`;
                    report += `Candidate Answer Summary:\n${fLog.candidate_answer_summary}\n\n`;
                    const fEvalText = fLog.evaluation.charAt(0).toUpperCase() + fLog.evaluation.slice(1);
                    report += `Evaluation:\n${fEvalText}\n\n`;
                });
            });

            report += `---\n\nAI Interview Summary:\n\n`;
            report += `Strengths:\n${summary.strengths}\n\n`;
            report += `Weaknesses:\n${summary.weaknesses}\n\n`;
            report += `Recommendation:\n${summary.hiring_recommendation}\n`;

            // Trigger Download
            const blob = new Blob([report], { type: "text/plain;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            const safeName = payload.candidate_name.replace(/[^a-z0-9]/gi, '_').toLowerCase();
            a.download = `interview_report_${safeName}.txt`;
            a.click();
            URL.revokeObjectURL(url);

            statusEl.textContent = "✔ Report downloaded successfully.";
            statusEl.style.color = "#34d399";
            statusEl.style.borderColor = "#10b981";
            statusEl.style.background = "#022c22";

        } catch (e) {
            statusEl.textContent = "Error compiling report: " + e.message;
            statusEl.style.color = "#f87171";
            statusEl.style.borderColor = "#dc2626";
            statusEl.style.background = "#1c0000";
        } finally {
            btn.disabled = false;
        }
    });

    // ============================================================
    //  LIVE COPILOT MODE
    // ============================================================

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
        chrome.runtime.sendMessage({ action: "end_session" }, () => {
            document.getElementById("setup-view").style.display = "block";
            document.getElementById("active-view").style.display = "none";
            const btn = document.getElementById("start-btn");
            btn.disabled = false; btn.textContent = "Start Session";
            updateWsDot(false);
        });
    });

    let isIntelligenceActive = false;

    document.getElementById("start-intelligence-btn").addEventListener("click", async () => {
        const btn = document.getElementById("start-intelligence-btn");
        const statusEl = document.getElementById("meet-status");
        
        if (isIntelligenceActive) {
            // Stop logic
            chrome.runtime.sendMessage({ action: "stop_tab_capture" }, (res) => {
                isIntelligenceActive = false;
                btn.innerHTML = "&#127908; Start Audio Transcription";
                btn.classList.replace("btn-danger", "btn-primary");
                statusEl.textContent = "Audio capture stopped.";
            });
            return;
        }
        
        // Start logic
        statusEl.textContent = "Capturing meeting tab audio...";
        chrome.runtime.sendMessage({ action: "start_tab_capture" }, (response) => {
            if (response && response.success) {
                isIntelligenceActive = true;
                btn.innerHTML = "&#10060; Stop Audio Transcription";
                btn.classList.replace("btn-primary", "btn-danger");
                statusEl.textContent = "Listening to meeting tab audio...";
            } else {
                let errStr = (response && response.error) ? response.error : "Unknown error";
                statusEl.textContent = "Error: " + errStr;
                console.error("Tab capture failed", errStr);
            }
        });
    });

    // Cleanup when ending entire session
    const originalEndClick = document.getElementById("end-btn").onclick;
    document.getElementById("end-btn").addEventListener("click", () => {
        if (isIntelligenceActive) {
            document.getElementById("start-intelligence-btn").click(); // toggle off
        }
        document.getElementById("live-transcript").innerHTML = "<em>Waiting for meeting audio...</em>";
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
        }
    });

    function updateWsDot(connected) {
        const dot = document.getElementById("ws-status");
        if (connected) { dot.classList.add("active"); dot.title = "Connected"; }
        else { dot.classList.remove("active"); dot.title = "Disconnected"; }
    }
});
