/**
 * content.js
 * 
 * Injected into the active web page.
 * Previously handled microphone capture via getUserMedia.
 * This is now completely removed in favor of Manifest V3 chrome.tabCapture
 * using an Offscreen Document, meaning this extension no longer needs to inject
 * intrusive scripts into the active website to capture audio!
 */

console.log("[AI Copilot] Content script injected. (Audio logic relocated to tabCapture)");
