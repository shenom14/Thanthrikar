document.addEventListener("DOMContentLoaded", () => {
    // --- UI Elements ---
    const setupContainer = document.getElementById("setup-container");
    const interviewView = document.getElementById("interview-view");
    
    // Tabs
    const tabAirtable = document.getElementById("tab-airtable");
    const tabManual = document.getElementById("tab-manual");
    const viewAirtable = document.getElementById("view-airtable");
    const viewManual = document.getElementById("view-manual");
    
    // Airtable Mode Elements
    const airtableSelect = document.getElementById("airtable-select");
    const btnGenAirtable = document.getElementById("generate-btn-airtable");
    const errAirtable = document.getElementById("error-msg-airtable");

    // Manual Mode Elements
    const btnGenManual = document.getElementById("generate-btn-manual");
    const errManual = document.getElementById("error-msg-manual");

    // Interview View Elements
    const nextBtn = document.getElementById("next-btn");
    const followupBtn = document.getElementById("followup-btn");
    const resetBtn = document.getElementById("reset-btn");
    const followupStackEl = document.getElementById("followup-stack");

    // --- State Variables ---
    let questionsQueue = [];
    let currentIndex = 0;
    let followUpContext = []; // Accumulated follow-up text for next API request (no backend state)

    // --- Mock Airtable CRM Data ---
    const mockAirtableData = [
        {
            id: "rec1",
            name: "Alice Johnson",
            role: "Senior Frontend Engineer",
            years_experience: 6,
            linkedin_url: "https://linkedin.com/in/alicej",
            github_username: "alicejs",
            resume_text: "Expert in React, TypeScript, and Webpack. Performance optimization and accessibility advocate."
        },
        {
            id: "rec2",
            name: "Bob Builder",
            role: "DevOps Engineer",
            years_experience: 4,
            linkedin_url: "https://linkedin.com/in/bobops",
            github_username: "bobinfra",
            resume_text: "Built CI/CD pipelines using GitHub Actions, deployed workloads on AWS EKS and automated via Terraform."
        }
    ];

    // Initialize mock dropdown
    mockAirtableData.forEach((candidate, index) => {
        const option = document.createElement("option");
        option.value = index;
        option.text = `${candidate.name} - ${candidate.role}`;
        airtableSelect.appendChild(option);
    });

    // --- Persistence on Load ---
    chrome.storage.local.get(["interviewQuestions", "currentIndex"], (res) => {
        if (res.interviewQuestions && res.interviewQuestions.length > 0) {
            questionsQueue = res.interviewQuestions;
            currentIndex = res.currentIndex || 0;
            showInterviewView();
        }
    });

    // --- Tab Switching Logic ---
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

    // --- Generation Trigger (Airtable Mode) ---
    btnGenAirtable.addEventListener("click", () => {
        const selectedIndex = airtableSelect.value;
        const payload = mockAirtableData[selectedIndex];

        btnGenAirtable.disabled = true;
        btnGenAirtable.innerText = "Analyzing CRM Data...";
        errAirtable.style.display = 'none';

        makeQuestionsRequest(payload, btnGenAirtable, errAirtable, "Generate Questions from CRM");
    });

    // --- Generation Trigger (Manual Mode) ---
    btnGenManual.addEventListener("click", () => {
        const name = document.getElementById("candidate-name").value.trim();
        const role = document.getElementById("candidate-role").value.trim();
        const exp = parseInt(document.getElementById("candidate-exp").value) || 0;
        const linkedin = document.getElementById("candidate-linkedin").value.trim();
        const github = document.getElementById("candidate-github").value.trim();
        const resume = document.getElementById("candidate-resume").value.trim();

        if (!name || !role) {
            showError(errManual, "Name and Role are required.");
            return;
        }

        btnGenManual.disabled = true;
        btnGenManual.innerText = "Analyzing Candidate...";
        errManual.style.display = 'none';

        const payload = {
            name: name,
            role: role,
            years_experience: exp,
            resume_text: resume || "No resume provided.",
            linkedin_url: linkedin || null,
            github_username: github || null
        };

        makeQuestionsRequest(payload, btnGenManual, errManual, "Generate Question Set");
    });

    // --- Shared Request Logic ---
    function makeQuestionsRequest(payload, btnElement, errElement, originalBtnText) {
        chrome.runtime.sendMessage({ action: "generate_questions", payload: payload }, (response) => {
            if (response && response.success) {
                questionsQueue = flattenQuestions(response.data.questions);
                currentIndex = 0;
                
                chrome.storage.local.set({ 
                    interviewQuestions: questionsQueue,
                    currentIndex: currentIndex
                });
                
                showInterviewView();
                
                // Reset button background state
                btnElement.disabled = false;
                btnElement.innerText = originalBtnText;

            } else {
                showError(errElement, "Failed to generate questions: " + (response ? response.error : "Backend unavailable. Is uvicorn running?"));
                btnElement.disabled = false;
                btnElement.innerText = originalBtnText;
            }
        });
    }

    // --- Flashcard Navigation ---
    nextBtn.addEventListener("click", () => {
        if (currentIndex < questionsQueue.length - 1) {
            currentIndex++;
            followUpContext = [];
            clearFollowUpStack();
            chrome.storage.local.set({ currentIndex: currentIndex });
            renderCurrentQuestion();
        } else {
            nextBtn.disabled = true;
            nextBtn.innerText = "No More Questions";
        }
    });

    // --- Follow-up Question ---
    followupBtn.addEventListener("click", () => {
        if (!questionsQueue.length || currentIndex >= questionsQueue.length) return;
        const q = questionsQueue[currentIndex];
        const context = followUpContext.join(" ");
        followupBtn.disabled = true;
        followupBtn.innerText = "Generating...";
        chrome.runtime.sendMessage({
            action: "generate_followup",
            current_question: q.question,
            candidate_context: context
        }, (response) => {
            followupBtn.disabled = false;
            followupBtn.innerText = "Generate Follow-up Question";
            if (response && response.success && response.follow_up_question) {
                followUpContext.push(response.follow_up_question);
                appendFollowUpToStack(response.follow_up_question);
            } else {
                const msg = response && response.error ? response.error : "Failed to generate follow-up.";
                appendFollowUpToStack("Error: " + msg, true);
            }
        });
    });

    resetBtn.addEventListener("click", () => {
        chrome.storage.local.remove(["interviewQuestions", "currentIndex"]);
        questionsQueue = [];
        currentIndex = 0;
        followUpContext = [];
        clearFollowUpStack();
        
        nextBtn.disabled = false;
        nextBtn.innerText = "Next Question";
        
        setupContainer.style.display = "block";
        interviewView.style.display = "none";
    });

    // --- Helper Functions ---
    function showInterviewView() {
        setupContainer.style.display = "none";
        interviewView.style.display = "block";
        renderCurrentQuestion();
    }

    function renderCurrentQuestion() {
        if (!questionsQueue || questionsQueue.length === 0) return;
        
        const q = questionsQueue[currentIndex];
        
        document.getElementById("q-counter").innerText = `Question ${currentIndex + 1} of ${questionsQueue.length}`;
        document.getElementById("q-category").innerText = q.category.replace("_", " ");
        document.getElementById("q-text").innerText = q.question;
        document.getElementById("q-reasoning").innerText = q.reasoning;
        
        if (currentIndex >= questionsQueue.length - 1) {
            nextBtn.disabled = true;
            nextBtn.innerText = "End of Questions";
        }
    }

    function clearFollowUpStack() {
        if (followupStackEl) followupStackEl.innerHTML = "";
    }

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
            arr.forEach(q => {
                flat.push({
                    category: category,
                    question: q.question,
                    reasoning: q.reasoning
                });
            });
        }
        return flat;
    }

    function showError(errElement, msg) {
        errElement.innerText = msg;
        errElement.style.display = "block";
    }
});
