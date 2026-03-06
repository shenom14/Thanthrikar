from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CandidateBase(BaseModel):
    id: str
    name: str
    role: str
    experience: str

class CandidateCreate(CandidateBase):
    pass

class Candidate(CandidateBase):
    resume_processed: bool

    class Config:
        from_attributes = True

class SessionBase(BaseModel):
    candidate_id: str
    
class SessionCreate(SessionBase):
    pass

class Session(SessionBase):
    id: int
    start_time: datetime
    end_time: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True

class InsightBase(BaseModel):
    claim_text: str
    is_verified: Optional[bool]
    explanation: str
    confidence: Optional[int]
    follow_up_suggested: Optional[str]

class InsightCreate(InsightBase):
    session_id: int

class Insight(InsightBase):
    id: int
    session_id: int
    timestamp: datetime

    class Config:
        from_attributes = True
