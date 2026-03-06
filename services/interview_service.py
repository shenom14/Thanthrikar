from sqlalchemy.orm import Session
from datetime import datetime
from backend import models, schemas
from config.logger import setup_logger

logger = setup_logger(__name__)

class InterviewService:
    """
    Business logic layer for managing Interview Sessions.
    Decouples database operations from FastAPI HTTP endpoints.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def start_session(self, candidate_id: str) -> models.InterviewSession:
        logger.info(f"Starting new interview session for candidate: {candidate_id}")
        
        # Verify candidate exists
        candidate = self.db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
        if not candidate:
            logger.info(f"Candidate {candidate_id} not found in DB. Attempting auto-hydration...")
            from airtable.candidate_loader import CandidateLoader
            loader = CandidateLoader()
            c_data = loader.fetch_candidate(candidate_id)
            if c_data.get("name") == "Unknown":
                logger.warning(f"Attempted to start session for non-existent candidate: {candidate_id}")
                raise ValueError("Candidate not found")
                
            candidate = models.Candidate(
                id=candidate_id,
                name=c_data.get("name"),
                role=c_data.get("role"),
                experience=c_data.get("experience"),
            )
            self.db.add(candidate)
            self.db.flush() # ensure ID is available
            
        new_session = models.InterviewSession(
            candidate_id=candidate_id,
            is_active=True
        )
        self.db.add(new_session)
        self.db.commit()
        self.db.refresh(new_session)
        
        logger.info(f"Successfully started session {new_session.id}")
        return new_session

    def end_session(self, session_id: int) -> models.InterviewSession:
        logger.info(f"Ending interview session: {session_id}")
        
        session = self.db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
        if not session:
            logger.error(f"Failed to find session {session_id} to end.")
            raise ValueError("Session not found")
            
        session.is_active = False
        session.end_time = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(f"Successfully ended session {session_id}")
        return session

    def record_insight(self, session_id: int, insight_data: schemas.InsightCreate) -> models.Insight:
        """
        Save an AI-generated insight to the database during an active session.
        """
        new_insight = models.Insight(
            session_id=session_id,
            claim_text=insight_data.claim_text,
            is_verified=insight_data.is_verified,
            explanation=insight_data.explanation,
            confidence=insight_data.confidence,
            follow_up_suggested=insight_data.follow_up_suggested
        )
        self.db.add(new_insight)
        self.db.commit()
        self.db.refresh(new_insight)
        return new_insight
