import io
import json
import asyncio
import threading
import re
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from config.logger import setup_logger
from backend.services.system_audio_capture import system_audio
from backend.database import SessionLocal

logger = setup_logger(__name__)

router = APIRouter(prefix="/audio", tags=["Audio"])

# Keep track of active UI clients listening to transcripts
active_websockets: List[WebSocket] = []

# Buffer to accumulate sentences per session
session_buffers: dict[int, str] = {}


def _get_main_loop():
    """Safely get the main asyncio event loop from api module (deferred to avoid circular import)."""
    from backend.api import main_event_loop
    return main_event_loop


def _get_active_sessions():
    """Deferred import to avoid circular import."""
    from backend.api import active_sessions
    return active_sessions


def _get_streaming_pipeline():
    """Deferred import to avoid circular import."""
    from backend.api import streaming_pipeline
    return streaming_pipeline


def broadcast_transcript(text: str, session_id: Optional[int] = None):
    """
    Callback fired by system_audio_capture when a new transcript chunk is ready.
    Runs in the PyAudio daemon thread — must use stored event loop reference.
    """
    loop = _get_main_loop()
    if loop is None:
        logger.error("[Audio] Main event loop not available yet.")
        return

    # 1. Broadcast to all generic audio-stream websocket clients (for live transcript display)
    for ws in list(active_websockets):
        try:
            asyncio.run_coroutine_threadsafe(
                ws.send_json({"type": "transcript", "text": text}),
                loop
            )
        except Exception as e:
            logger.error(f"[Audio] Error broadcasting generic transcript: {e}")

    # 2. Route to specific interview session AI pipeline
    if session_id is not None:
        active_sessions = _get_active_sessions()

        # Send raw live text to the session websocket for immediate UI display
        if session_id in active_sessions:
            try:
                asyncio.run_coroutine_threadsafe(
                    active_sessions[session_id].send_json({"type": "transcript", "text": text}),
                    loop
                )
            except Exception as e:
                logger.error(f"[Audio] Error sending transcript to session {session_id}: {e}")

        # Accumulate into sentence buffer
        current_buffer = session_buffers.get(session_id, "")
        current_buffer += " " + text

        # FIX #3: Don't rely solely on punctuation — Whisper tiny.en rarely emits it.
        # Flush on sentence-ending punctuation OR after ~150 chars (roughly 1-2 sentences).
        is_sentence_end = bool(re.search(r'[.?!]\s*$', text))
        is_buffer_long = len(current_buffer) > 150

        # Also flush every time we receive a non-trivial chunk (>= 20 chars).
        # Since system_audio now clears its buffer after each Whisper call,
        # each chunk is already utterance-sized.
        is_substantial_chunk = len(text.strip()) >= 20

        if is_sentence_end or is_buffer_long or is_substantial_chunk:
            finalized_sentence = current_buffer.strip()
            session_buffers[session_id] = ""

            # Schedule the AI pipeline coroutine directly on the main loop
            async def process_insight(sentence: str, sid: int):
                pipeline = _get_streaming_pipeline()
                sessions = _get_active_sessions()
                db = SessionLocal()
                try:
                    messages = await pipeline.handle_transcript_chunk(
                        db=db, session_id=sid, transcript_chunk=sentence
                    )
                    if sid in sessions:
                        for msg in messages:
                            await sessions[sid].send_json(msg)
                except Exception as e:
                    logger.error(f"[Audio] Pipeline error for session {sid}: {e}")
                finally:
                    db.close()

            asyncio.run_coroutine_threadsafe(
                process_insight(finalized_sentence, session_id),
                loop
            )
        else:
            session_buffers[session_id] = current_buffer


@router.post("/system-capture/start")
async def start_system_capture(session_id: Optional[int] = Query(None, description="Interview Session ID")):
    """Starts the backend PyAudio listener on the Virtual Audio Cable."""
    if system_audio.is_running:
        return {"success": True, "message": "Capture already running."}

    logger.info(f"[Audio] Starting System Audio Capture (Virtual Cable)... session={session_id}")

    # Initialize sentence buffer for this session if needed
    if session_id is not None:
        session_buffers[session_id] = ""

    # Run the blocking capture in a background daemon thread
    thread = threading.Thread(
        target=system_audio.start,
        args=(lambda text: broadcast_transcript(text, session_id),),
        daemon=True
    )
    thread.start()

    return {"success": True, "message": "System audio capture started."}


@router.post("/system-capture/stop")
async def stop_system_capture():
    """Stops the backend PyAudio listener."""
    logger.info("[Audio] Stopping System Audio Capture...")
    system_audio.stop()
    return {"success": True, "message": "System audio capture stopped."}


@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint that GUI clients connect to in order to receive live transcripts.
    """
    await websocket.accept()
    active_websockets.append(websocket)
    logger.info("GUI connected to Audio Transcript Stream.")

    try:
        while True:
            message = await websocket.receive()
            if "text" in message:
                data = json.loads(message["text"])
                if data.get("action") == "stop":
                    logger.info("GUI requested stop streaming.")
                    break
    except WebSocketDisconnect:
        logger.info("GUI disconnected from transcript stream.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        try:
            await websocket.close()
        except:
            pass


@router.websocket("/tab-stream")
async def tab_stream_endpoint(websocket: WebSocket, session_id: Optional[int] = Query(None)):
    """
    WebSocket endpoint for receiving binary audio chunks from the Chrome extension's
    Offscreen Document (tab audio capture via MediaRecorder, webm/opus format).

    Flow:
      1. Receive binary webm chunk (~2 seconds of audio)
      2. Decode to raw 16kHz mono PCM using pydub (requires ffmpeg)
      3. Transcribe with Whisper
      4. Broadcast transcript to popup and feed into AI pipeline
    """
    await websocket.accept()
    logger.info(f"[TabStream] Client connected. session_id={session_id}")

    # Initialize sentence buffer for this session
    if session_id is not None:
        session_buffers[session_id] = ""

    from backend.services.whisper_service import whisper_service

    try:
        while True:
            # Receive binary audio data
            data = await websocket.receive_bytes()

            if not data or len(data) < 100:
                # Skip tiny chunks (likely silence or metadata-only)
                continue

            logger.debug(f"[TabStream] Received audio chunk: {len(data)} bytes")

            try:
                # Convert webm/opus to raw 16kHz mono PCM using pydub
                from pydub import AudioSegment

                audio_segment = AudioSegment.from_file(io.BytesIO(data), format="webm")
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                raw_pcm = audio_segment.raw_data

                if len(raw_pcm) < 1600:  # Less than 0.05s at 16kHz — skip
                    continue

                # Transcribe with Whisper
                text = whisper_service.transcribe_audio_buffer(raw_pcm)

                if text and text.strip():
                    logger.info(f"[TabStream] Whisper: \"{text.strip()}\"")

                    # Send transcript back to the extension via this WebSocket
                    await websocket.send_json({"type": "transcript", "text": text.strip()})

                    # Feed into AI pipeline if session is active
                    if session_id is not None:
                        await _process_tab_transcript(text.strip(), session_id, websocket)

            except Exception as decode_err:
                logger.error(f"[TabStream] Audio decode/transcribe error: {decode_err}")

    except WebSocketDisconnect:
        logger.info("[TabStream] Client disconnected.")
    except Exception as e:
        logger.error(f"[TabStream] Error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass


async def _process_tab_transcript(text: str, session_id: int, websocket: WebSocket):
    """
    Feed transcribed text into the AI interview pipeline.
    Sends insight/follow-up results back through the same WebSocket.
    """
    pipeline = _get_streaming_pipeline()
    db = SessionLocal()

    try:
        messages = await pipeline.handle_transcript_chunk(
            db=db, session_id=session_id, transcript_chunk=text
        )
        for msg in messages:
            try:
                await websocket.send_json(msg)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[TabStream] Pipeline error for session {session_id}: {e}")
    finally:
        db.close()

