let mediaRecorder = null;
let audioContext = null;
let sourceNode = null;

chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
    if (message.target === 'offscreen') {
        if (message.type === 'start_recording') {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        mandatory: {
                            chromeMediaSource: 'tab',
                            chromeMediaSourceId: message.streamId
                        }
                    }
                });

                // To ensure the user can still hear the tab, we must route the audio to the output
                audioContext = new AudioContext();
                sourceNode = audioContext.createMediaStreamSource(stream);
                sourceNode.connect(audioContext.destination);

                mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
                
                mediaRecorder.ondataavailable = async (event) => {
                    if (event.data.size > 0) {
                        const buffer = await event.data.arrayBuffer();
                        const bytes = new Uint8Array(buffer);
                        let binary = '';
                        for (let i = 0; i < bytes.byteLength; i++) {
                            binary += String.fromCharCode(bytes[i]);
                        }
                        const base64Chunk = btoa(binary);
                        
                        chrome.runtime.sendMessage({
                            action: "audio_chunk",
                            data: base64Chunk
                        });
                    }
                };
                
                mediaRecorder.start(1000); // 1-second chunks
                sendResponse({ success: true });
            } catch (err) {
                console.error("Offscreen capture error:", err);
                sendResponse({ success: false, error: err.message });
            }
        } else if (message.type === 'stop_recording') {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                mediaRecorder.stream.getTracks().forEach(t => t.stop());
            }
            if (audioContext) {
                audioContext.close();
            }
            sendResponse({ success: true });
        }
    }
    return true;
});
