import asyncio
import os
import sys

# Ensure backend imports work
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Config and Logging
from config.settings import settings
from config.logger import setup_logger

# Database and Routes
from backend.database import engine, Base, SessionLocal
from backend.routes import api_router
from backend.services.transcriber import StreamingTranscriber
from services.streaming_pipeline import StreamingPipeline

logger = setup_logger(__name__)

# Initialize DB tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database instantiated successfully.")
except Exception as e:
    logger.error(f"Failed to instantiate database: {e}")

# Enterprise FastAPI setup
app = FastAPI(
    title=settings.APP_NAME,
    version="3.0.0-Enterprise",
    description="Service-Oriented backend for AI Interview Copilot.",
)


# Allow extension origin to communicate freely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all unified REST routes
from backend.routers import jd
app.include_router(api_router)
app.include_router(jd.router)


# --- Legacy Question Generation Endpoints (Prep Mode) ---
from pydantic import BaseModel
from typing import Optional, Dict

class CandidateRequest(BaseModel):
    name: str
    role: str
    years_experience: int
    resume_text: str
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None

class FollowUpRequest(BaseModel):
    current_question: str
    candidate_context: Optional[str] = ""

@app.post("/api/v1/generate-questions")
async def api_generate_questions(request: CandidateRequest):
    from agents.legacy_question_generator import generate_candidate_questions
    try:
        candidate_data = request.dict()
        return generate_candidate_questions(candidate_data)
    except Exception as e:
        logger.error(f"Failed to generate questions: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/generate-followup")
async def api_generate_followup(request: FollowUpRequest):
    from agents.legacy_question_generator import generate_followup_question
    try:
        follow_up = generate_followup_question(request.current_question, request.candidate_context)
        return {"follow_up_question": follow_up}
    except Exception as e:
        logger.error(f"Failed to generate follow up: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
# --------------------------------------------------------

# ==================================================================

# Singleton services for all WS connections
streaming_pipeline = StreamingPipeline()
transcriber_service = StreamingTranscriber()


@app.on_event("startup")
async def startup_warmup():
    """Pre-warm the AI pipeline in the background so the first request is instant."""
    import asyncio
    asyncio.create_task(streaming_pipeline._init_components())
    logger.info("Background AI pipeline warm-up task started.")




@app.get("/raw_health")
async def raw_health():
    return {"status": "ok"}


@app.websocket("/ws/interviewStream/{session_id}")
async def interview_stream(websocket: WebSocket, session_id: int):
    """
    WebSocket to receive real-time transcript chunks from the Chrome Extension and
    route them through the AI pipeline to generate and persist insights.
    """
    # Optional API key check for WebSocket connections.
    expected_key = settings.EXTENSION_API_KEY
    if expected_key:
        client_key = websocket.headers.get("x-api-key")
        if client_key != expected_key:
            logger.warning("WebSocket connection rejected due to invalid API key.")
            await websocket.close(code=1008)
            return

    await websocket.accept()
    logger.info(f"WebSocket client connected for session {session_id}")

    db = SessionLocal()
    
    # Async buffer to prevent websocket block
    audio_buffer = bytearray()
    is_transcribing = False

    async def process_audio_buffer():
        nonlocal audio_buffer, is_transcribing
        if not audio_buffer or is_transcribing:
            return
            
        is_transcribing = True
        try:
            # Take everything currently in the buffer and clear it
            chunk_to_process = bytes(audio_buffer)
            audio_buffer.clear()
            
            # Use AsyncGroq directly
            text_chunk = await transcriber_service.process_chunk(audio_data=chunk_to_process)
            
            if text_chunk:
                logger.debug(f"Processing transcript chunk for session {session_id} length: {len(text_chunk)}")
                
                # Emit live transcript to the UI instantly
                await websocket.send_json({"type": "transcript", "text": text_chunk})
                
                messages = await streaming_pipeline.handle_transcript_chunk(
                    db=db, session_id=session_id, transcript_chunk=text_chunk
                )
                for msg in messages:
                    await websocket.send_json(msg)
                
                await websocket.send_json({"type": "heartbeat", "message": "Acknowledged payload."})
        except Exception as e:
            logger.error(f"Error in audio processing task: {e}")
        finally:
            is_transcribing = False
            # Check if more data arrived while we were transcribing
            if audio_buffer:
                asyncio.create_task(process_audio_buffer())

    try:
        while True:
            # This read is never blocked by Vosk anymore, so we drain the socket instantly
            data_event = await websocket.receive()
            
            if "bytes" in data_event:
                audio_buffer.extend(data_event["bytes"])
                if not is_transcribing:
                    asyncio.create_task(process_audio_buffer())
                    
            elif "text" in data_event:
                text_chunk = data_event["text"]
                if text_chunk:
                    logger.debug(f"Processing text chunk for session {session_id} length: {len(text_chunk)}")
                    messages = await streaming_pipeline.handle_transcript_chunk(
                        db=db, session_id=session_id, transcript_chunk=text_chunk
                    )
                    for msg in messages:
                        await websocket.send_json(msg)
                    await websocket.send_json({"type": "heartbeat", "message": "Acknowledged payload."})

    except Exception as e:
        logger.error(f"WebSocket Session {session_id} Error/Disconnect: {e}")
    finally:
        db.close()
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"Starting uvicorn server for {settings.APP_NAME} in {settings.ENVIRONMENT} mode."
    )
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8001, reload=True)
