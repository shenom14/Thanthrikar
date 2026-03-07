"""
Backend FastAPI Endpoint

Enterprise backend for AI Interview Copilot.
Combines REST endpoints for the Chrome Extension with WebSocket streaming for real-time interviews.
"""

import asyncio
import os
import sys

# Ensure backend imports work from any CWD
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # type: ignore
from typing import Optional, Dict, Any

# Config and Logging
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

# Database (graceful if not configured)
try:
    from backend.database import engine, Base, SessionLocal
    from backend.routes import api_router
    Base.metadata.create_all(bind=engine)
    logger.info("Database instantiated successfully.")
    DB_AVAILABLE = True
except Exception as e:
    logger.warning(f"Database not available ({e}); REST-only mode.")
    DB_AVAILABLE = False

# Streaming pipeline (graceful if not configured)
try:
    from services.streaming_pipeline import StreamingPipeline
    from backend.services.transcriber import StreamingTranscriber  # type: ignore
    streaming_pipeline = StreamingPipeline()
    transcriber_service = StreamingTranscriber()
    STREAMING_AVAILABLE = True
except Exception as e:
    logger.warning(f"Streaming pipeline not available ({e}); REST-only mode.")
    STREAMING_AVAILABLE = False

# Extension-facing imports
from agents.question_generator import generate_candidate_questions, generate_followup_question  # type: ignore


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version="3.0.0-Enterprise",
    description="Service-Oriented backend for AI Interview Copilot.",
)

# CORS — allow Chrome extension to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST routes from brum if database is available
if DB_AVAILABLE:
    try:
        app.include_router(api_router)
    except Exception as e:
        logger.warning(f"Could not mount API router: {e}")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_warmup():
    """Pre-warm the AI pipeline in the background so the first request is instant."""
    if STREAMING_AVAILABLE:
        asyncio.create_task(streaming_pipeline._init_components())
        logger.info("Background AI pipeline warm-up task started.")
    else:
        logger.info("Running in REST-only mode (no streaming pipeline).")


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/raw_health")
async def raw_health():
    return {
        "status": "ok",
        "llm_backend": getattr(settings, "LLM_BACKEND", "ollama"),
        "streaming": STREAMING_AVAILABLE,
        "database": DB_AVAILABLE,
    }


# ---------------------------------------------------------------------------
# Extension REST Endpoints (backward compatible with Chrome extension)
# ---------------------------------------------------------------------------

class CandidateRequest(BaseModel):
    """Pydantic model representing incoming candidate data payload"""
    name: str
    role: str
    years_experience: int
    resume_text: str = "No resume provided."
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None


class FollowUpRequest(BaseModel):
    """Payload for requesting a follow-up question"""
    current_question: str
    candidate_context: Optional[str] = ""


@app.post("/api/v1/generate-questions")
async def api_generate_questions(request: CandidateRequest):
    """
    Endpoint to receive candidate details and return 20 generated interview questions.
    Used by the Chrome extension.
    """
    logger.info(f"Received question generation request for candidate: {request.name}")
    try:
        candidate_data = request.model_dump()
        generated_questions = generate_candidate_questions(candidate_data)
        return generated_questions
    except Exception as e:
        logger.error(f"Failed to generate questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate-followup")
async def api_generate_followup(request: FollowUpRequest):
    """
    Endpoint to generate a contextual follow-up question.
    Used by the Chrome extension.
    """
    logger.info("Generating follow-up question...")
    try:
        follow_up = generate_followup_question(request.current_question, request.candidate_context)
        return {"follow_up_question": follow_up}
    except Exception as e:
        logger.error(f"Failed to generate follow up: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# WebSocket Endpoint (enterprise streaming from brum)
# ---------------------------------------------------------------------------

if STREAMING_AVAILABLE:
    @app.websocket("/ws/interviewStream/{session_id}")
    async def interview_stream(websocket: WebSocket, session_id: int):
        """
        WebSocket to receive real-time transcript chunks from the Chrome Extension
        and route them through the AI pipeline.
        """
        expected_key = settings.EXTENSION_API_KEY
        if expected_key:
            client_key = websocket.headers.get("x-api-key")
            if client_key != expected_key:
                logger.warning("WebSocket rejected: invalid API key.")
                await websocket.close(code=1008)
                return

        await websocket.accept()
        logger.info(f"WebSocket client connected for session {session_id}")

        db = SessionLocal()
        audio_buffer = bytearray()
        is_transcribing = False

        async def process_audio_buffer():
            nonlocal audio_buffer, is_transcribing
            if not audio_buffer or is_transcribing:
                return
            is_transcribing = True
            try:
                chunk_to_process = bytes(audio_buffer)
                audio_buffer.clear()
                text_chunk = await transcriber_service.process_chunk(audio_data=chunk_to_process)
                if text_chunk:
                    await websocket.send_json({"type": "transcript", "text": text_chunk})
                    messages = await streaming_pipeline.handle_transcript_chunk(
                        db=db, session_id=session_id, transcript_chunk=text_chunk
                    )
                    for msg in messages:
                        await websocket.send_json(msg)
                    await websocket.send_json({"type": "heartbeat", "message": "Acknowledged."})
            except Exception as e:
                logger.error(f"Audio processing error: {e}")
            finally:
                is_transcribing = False
                if audio_buffer:
                    asyncio.create_task(process_audio_buffer())

        try:
            while True:
                data_event = await websocket.receive()
                if "bytes" in data_event:
                    audio_buffer.extend(data_event["bytes"])
                    if not is_transcribing:
                        asyncio.create_task(process_audio_buffer())
                elif "text" in data_event:
                    text_chunk = data_event["text"]
                    if text_chunk:
                        messages = await streaming_pipeline.handle_transcript_chunk(
                            db=db, session_id=session_id, transcript_chunk=text_chunk
                        )
                        for msg in messages:
                            await websocket.send_json(msg)
                        await websocket.send_json({"type": "heartbeat", "message": "Acknowledged."})
        except Exception as e:
            logger.error(f"WebSocket Session {session_id} Error/Disconnect: {e}")
        finally:
            db.close()
            try:
                await websocket.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn  # type: ignore
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode.")
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)
