"""
Backend FastAPI Endpoint

Exposes the Question Generation Engine as a REST API to be consumed by the Chrome Extension.
"""

from fastapi import FastAPI, HTTPException  # type: ignore
from pydantic import BaseModel  # type: ignore
from typing import Optional, Dict, Any
import logging

from agents.question_generator import generate_candidate_questions  # type: ignore

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi.middleware.cors import CORSMiddleware  # type: ignore

app = FastAPI(
    title="AI Interview Copilot API",
    description="Backend services for the AI Interview Copilot Chrome Extension",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CandidateRequest(BaseModel):
    """Pydantic model representing incoming candidate data payload"""
    name: str
    role: str
    years_experience: int
    resume_text: str
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None

class FollowUpRequest(BaseModel):
    """Payload for requesting an infinite follow-up drill down"""
    current_question: str
    candidate_context: Optional[str] = ""

@app.post("/api/v1/generate-questions")
async def api_generate_questions(request: CandidateRequest):
    """
    Endpoint to receive candidate details and return 20 generated interview questions.
    """
    logger.info(f"Received question generation request for candidate: {request.name}")
    try:
        candidate_data = request.dict()
        generated_questions_json = generate_candidate_questions(candidate_data)
        return generated_questions_json
        
    except Exception as e:
        logger.error(f"Failed to generate questions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/generate-followup")
async def api_generate_followup(request: FollowUpRequest):
    """
    Endpoint to generate a highly contextual dynamic follow-up question.
    """
    from agents.question_generator import generate_followup_question  # type: ignore
    
    logger.info("Generating follow-up question...")
    try:
        follow_up = generate_followup_question(request.current_question, request.candidate_context)
        return {"follow_up_question": follow_up}
    except Exception as e:
        logger.error(f"Failed to generate follow up: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
