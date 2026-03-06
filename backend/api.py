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

# Singleton streaming pipeline for all WS connections
streaming_pipeline = StreamingPipeline()


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

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(
                f"Received WS payload for session {session_id} length: {len(data)}"
            )

            # Process the transcript chunk through the streaming pipeline.
            try:
                messages = await streaming_pipeline.handle_transcript_chunk(
                    db=db, session_id=session_id, transcript_chunk=data
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
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)
