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
from backend.database import engine, Base
from backend.routes import api_router

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
    description="Service-Oriented backend for AI Interview Copilot."
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

@app.websocket("/ws/interviewStream/{session_id}")
async def interview_stream(websocket: WebSocket, session_id: int):
    """
    WebSocket to receive real-time audio chunks or transcript from Chrome Extension.
    """
    await websocket.accept()
    logger.info(f"WebSocket client connected for session {session_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received WS payload for session {session_id} length: {len(data)}")
            
            # TODO: Invoke Agents (Planner -> Verifier -> FactChecker)
            # Use Dependency Injection for DB:
            # db = next(get_db())
            # service = InterviewService(db)
            # service.record_insight(session_id, InsightCreate(...))
            
            await asyncio.sleep(0.5)
            await websocket.send_json({
                "type": "heartbeat",
                "message": "Acknowledged payload."
            })
            
    except Exception as e:
        logger.error(f"WebSocket Session {session_id} Error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting uvicorn server for {settings.APP_NAME} in {settings.ENVIRONMENT} mode.")
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)
