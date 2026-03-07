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
app.include_router(api_router)

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
    
    # Each WebSocket gets its own independent speech recognizer state tracker
    recognizer = transcriber_service.create_recognizer() if transcriber_service.enabled else None

    try:
        while True:
            data_event = await websocket.receive()
            text_chunk = ""
            
            if "bytes" in data_event:
                if recognizer:
                    loop = asyncio.get_running_loop()
                    text_chunk = await loop.run_in_executor(
                        None, transcriber_service.process_chunk, recognizer, data_event["bytes"]
                    )
            elif "text" in data_event:
                text_chunk = data_event["text"]
                
            if not text_chunk:
                continue
                
            logger.debug(
                f"Processing transcript chunk for session {session_id} length: {len(text_chunk)}"
            )

            # Process the transcript chunk through the streaming pipeline.
            try:
                messages = await streaming_pipeline.handle_transcript_chunk(
                    db=db, session_id=session_id, transcript_chunk=text_chunk
                )
            except Exception as e:
                logger.error(f"Streaming pipeline error for session {session_id}: {e}")
                messages = []

            for msg in messages:
                await websocket.send_json(msg)

            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "message": "Acknowledged payload.",
                }
            )

    except Exception as e:
        logger.error(f"WebSocket Session {session_id} Error: {e}")
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
