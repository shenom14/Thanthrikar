from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True, index=True) # E.g., Airtable Record ID
    name = Column(String, index=True)
    role = Column(String)
    experience = Column(String)
    resume_file = Column(String)
    resume_processed = Column(Boolean, default=False)
    
    sessions = relationship("InterviewSession", back_populates="candidate")

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(String, ForeignKey("candidates.id"))
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    candidate = relationship("Candidate", back_populates="sessions")
    insights = relationship("Insight", back_populates="session")

class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    claim_text = Column(String)
    is_verified = Column(Boolean, nullable=True)
    explanation = Column(String)
    confidence = Column(Integer, nullable=True)
    follow_up_suggested = Column(String, nullable=True)

    session = relationship("InterviewSession", back_populates="insights")
