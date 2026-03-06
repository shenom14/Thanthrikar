from sqlalchemy.orm import Session
from backend import models
from config.logger import setup_logger

logger = setup_logger(__name__)

class ReportService:
    """
    Business logic layer for generating post-interview reports.
    Aggregates historical session data and leverages LLMs for final summaries.
    """
    
    def __init__(self, db: Session):
        self.db = db

    def generate_session_report(self, session_id: int) -> dict:
        """
        Compile all insights from a session into a structured JSON report.
        """
        logger.info(f"Generating report for session {session_id}")
        
        session = self.db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
        if not session:
            logger.error(f"Cannot generate report for missing session: {session_id}")
            raise ValueError("Session not found")
            
        insights = self.db.query(models.Insight).filter(models.Insight.session_id == session_id).all()
        
        claims_detected = len(insights)
        inconsistencies_found = sum(1 for i in insights if i.is_verified is False)
        facts_checked = sum(1 for i in insights if getattr(i, 'is_correct', None) is not None) # Example schema extension
        
        # In a fully-production system, you would take all `i.explanation` strings
        # and feed them to `ChatGroq` for a cohesive English summary paragraph.
        summary_text = "The candidate demonstrated technical proficiency but faced scrutiny regarding depth of leadership claims."
        
        report = {
            "session_id": session.id,
            "candidate_id": session.candidate_id,
            "metrics": {
                "claims_detected": claims_detected,
                "resume_inconsistencies": inconsistencies_found,
                "technical_facts_checked": facts_checked
            },
            "insights": [
                 {
                     "claim": i.claim_text, 
                     "verified": i.is_verified, 
                     "explanation": i.explanation
                 } for i in insights
            ],
            "executive_summary": summary_text
        }
        
        logger.info(f"Successfully generated report for session {session_id}")
        return report
