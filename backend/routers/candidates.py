from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..security import verify_api_key

# Initialize placeholder for implementations
# from airtable.candidate_loader import CandidateLoader
# from rag.ingest import run_ingestion_pipeline
# from tools.resume_parser import ResumeParser

router = APIRouter(
    prefix="/candidates",
    tags=["candidates"],
    dependencies=[Depends(verify_api_key)],
)

@router.post("/", response_model=schemas.Candidate)
def create_candidate(candidate: schemas.CandidateCreate, db: Session = Depends(get_db)):
    db_candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate.id).first()
    if db_candidate:
        raise HTTPException(status_code=400, detail="Candidate already registered")
    
    new_candidate = models.Candidate(
        id=candidate.id,
        name=candidate.name,
        role=candidate.role,
        experience=candidate.experience,
        resume_processed=False
    )
    db.add(new_candidate)
    db.commit()
    db.refresh(new_candidate)
    return new_candidate

@router.get("/{candidate_id}", response_model=schemas.Candidate)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if not candidate:
        # TODO: loader = CandidateLoader(); return loader.fetch_candidate(candidate_id)
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate

@router.post("/{candidate_id}/resume", response_model=dict)
def process_resume(candidate_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    def _background_process(c_id: str):
        # 1. parser = ResumeParser()
        # 2. raw_text = parser.parse_pdf("local/path/to/resume.pdf") 
        # 3. run_ingestion_pipeline(raw_text, c_id)
        # 4. Mark processed in DB
        db_temp = next(get_db())
        c = db_temp.query(models.Candidate).filter(models.Candidate.id == c_id).first()
        if c:
            c.resume_processed = True
            db_temp.commit()
            
    background_tasks.add_task(_background_process, candidate.id)
    return {"status": "processing_started", "candidate_id": candidate.id}
