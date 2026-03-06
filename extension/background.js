/**
 * background.js
 * 
 * Service Worker for the AI Interview Copilot.
 * Responsibilities:
 * - Communicate with the FastAPI backend over REST/WebSockets.
 * - Manage states (e.g., currently selected candidate, interview active status).
 * - React to UI button clicks (e.g., "Next Question").
 * - Push real-time insights from backend to popup.html.
 */

const API_BASE_URL = "http://localhost:8000";

console.log("[AI Copilot] Service Worker specialized background script initialized.");

// TODO: Establish WebSocket connection for real-time streaming transcripts and claims.
// let socket = new WebSocket('ws://localhost:8000/ws/interview');
// socket.onmessage = function(event) {
//     const data = JSON.parse(event.data);
//     if (data.type === 'insight') {
//         updatePopup(data);
//     }
// };

// TODO: Implement REST API Fetch Wrappers
async function fetchCandidateData(candidateId) {
    try {
        const response = await fetch(`${API_BASE_URL}/candidate/load?id=${candidateId}`);
        const data = await response.json();
        return data;
    } catch (e) {
        console.error("Failed to fetch candidate:", e);
    }
}

// TODO: Wire up popup button logic -> Background -> API 
