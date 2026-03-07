from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class JobDescription(BaseModel):
    role: str = Field(description="The requested job role.")
    required_skills: List[str] = Field(description="List of required technical skills.", default_factory=list)
    responsibilities: List[str] = Field(description="Key responsibilities for the role.", default_factory=list)
    domains: List[str] = Field(description="Technical domains or concepts relevant to the role (e.g. Distributed Systems).", default_factory=list)

class JDAnalysisResult(BaseModel):
    role: str
    required_skills: List[str]
    domains: List[str]
    responsibilities: List[str]

class QuestionMetadata(BaseModel):
    question: str
    jd_skill: Optional[str] = None
    candidate_skill: Optional[str] = None
    difficulty: str
    evaluation_goal: str
    recommended_answer: Optional[str] = None

class EvaluationRequest(BaseModel):
    questionText: str
    evaluationResult: str
    colorRating: str

class QALog(BaseModel):
    question: str
    candidate_answer_summary: str
    evaluation: str
    color: str

class SummaryRequest(BaseModel):
    candidate_name: str
    role: str
    skills: list[str]
    experience: str
    achievements: str
    interview_log: list[QALog]

class QuestionCategory(BaseModel):
    technical_questions: List[QuestionMetadata] = Field(default_factory=list)
    system_design_questions: List[QuestionMetadata] = Field(default_factory=list)
    behavioral_questions: List[QuestionMetadata] = Field(default_factory=list)
    resume_validation_questions: List[QuestionMetadata] = Field(default_factory=list)
    github_project_questions: List[QuestionMetadata] = Field(default_factory=list)

class CandidateProfile(BaseModel):
    name: str = "Unknown"
    role: str
    experience_years: str = "0"
    resume_skills: List[str] = Field(default_factory=list)
    linkedin_skills: List[str] = Field(default_factory=list)
    linkedin_summary: str = ""
    github_repositories: List[Dict] = Field(default_factory=list)
    github_languages: List[str] = Field(default_factory=list)
    jd_skills: List[str] = Field(default_factory=list)
    jd_domains: List[str] = Field(default_factory=list)
