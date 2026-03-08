import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from config.logger import setup_logger
from backend.services.whisper_service import whisper_service

logger = setup_logger(__name__)

router = APIRouter(prefix="/audio", tags=["Audio"])

@router.websocket("/stream")
async def websocket_enpoint(websocket: WebSocket):
    """
    WebSocket endpoint that receives live audio chunks from the frontend.
    Accumulates WebM chunks and runs Whisper transcription.
    """
    await websocket.accept()
    logger.info("WebSocket connection established for microphone stream.")
    
    # Accumulate the raw WebM stream bytes
    audio_buffer = bytearray()
    last_transcribed_text = ""
    
    try:
        while True:
            # The frontend can send text (metadata/commands) or bytes (audio)
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                logger.info(f"Client disconnected from audio stream with code {message.get('code')}")
                break
            
            if message.get("bytes") is not None:
                audio_chunk = message["bytes"]
                audio_buffer.extend(audio_chunk)
                
                # Only run transcription if we have enough audio (approx 500ms = 16KB for mono 16kHz)
                if len(audio_buffer) > 16000:
                    text = await asyncio.to_thread(whisper_service.transcribe_audio_buffer, bytes(audio_buffer))
                    
                    if text and text != last_transcribed_text:
                        import difflib
                        old_words = last_transcribed_text.split()
                        new_words = text.split()
                        
                        s = difflib.SequenceMatcher(None, old_words, new_words)
                        match = s.find_longest_match(0, len(old_words), 0, len(new_words))
                        
                        new_part = text
                        if match.size > 0:
                            # Only take the words after the longest matching block
                            novel_words = new_words[match.b + match.size:]
                            new_part = " ".join(novel_words).strip()
                        
                        if new_part:
                            logger.info(f"[Whisper] {new_part}")
                            last_transcribed_text = text
                            
                            # Send the newly transcribed text back to the frontend
                            await websocket.send_json({"type": "transcript", "text": new_part})
                            
                            # TODO: Send completed sentences into LangChain for claim extraction
                
            elif message.get("text") is not None:
                data = json.loads(message["text"])
                if data.get("action") == "stop":
                    logger.info("Client requested stop streaming.")
                    break
                
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass
