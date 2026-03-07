/**
 * background.js
 * 
 * Service Worker for the AI Interview Copilot.
 * Integrates directly with the new FastAPI sequence (/api/v1/generate-questions).
 */

const API_BASE_URL = "http://127.0.0.1:8000"; // Ensure this matches FastAPI port

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "generate_questions") {
        fetchQuestionsFromBackend(request.payload)
            .then(data => sendResponse({ success: true, data: data }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
    }
    if (request.action === "generate_followup") {
        fetchFollowUpFromBackend(request.current_question, request.candidate_context || "")
            .then(followUp => sendResponse({ success: true, follow_up_question: followUp }))
            .catch(err => sendResponse({ success: false, error: err.message }));
        return true;
    }
});

async function fetchQuestionsFromBackend(payload) {
    console.log("[Copilot] Fetching questions from backend...", payload);
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/generate-questions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Backend Error (${response.status}): ${errText}`);
        }

        const data = await response.json();
        return data;
    } catch (e) {
        console.error("Network or Backend Failure:", e);
        throw e;
    }
}

async function fetchFollowUpFromBackend(current_question, candidate_context) {
    console.log("[Copilot] Fetching follow-up from backend...");
    try {
        const response = await fetch(`${API_BASE_URL}/api/v1/generate-followup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_question, candidate_context })
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`Backend Error (${response.status}): ${errText}`);
        }

        const data = await response.json();
        return data.follow_up_question;
    } catch (e) {
        console.error("Follow-up request failed:", e);
        throw e;
    }
}
