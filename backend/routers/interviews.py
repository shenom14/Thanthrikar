from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from .. import schemas
from ..database import get_db
from config.logger import setup_logger
from services.interview_service import InterviewService
from services.report_service import ReportService

logger = setup_logger(__name__)

router = APIRouter(
    prefix="/interviews",
    tags=["interviews"]
)

@router.post("/start", response_model=schemas.Session)
def start_interview_session(session_data: schemas.SessionCreate, db: Session = Depends(get_db)):
    """ Initialize a new tracking session via the InterviewService. """
    service = InterviewService(db)
    try:
        return service.start_session(session_data.candidate_id)
    except ValueError as e:
        logger.warning(f"Failed to start interview: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/end", response_model=schemas.Session)
def end_interview_session(session_id: int, db: Session = Depends(get_db)):
    """ End an active interview tracking session via the InterviewService. """
    service = InterviewService(db)
    try:
        return service.end_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{session_id}/report", response_model=dict)
def generate_report(session_id: int, db: Session = Depends(get_db)):
    """ Compile an aggregate AI summary report from session insights. """
    service = ReportService(db)
    try:
        return service.generate_session_report(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
