import logging
from typing import Optional, Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.logger import setup_logger
from backend.schemas_jd import CandidateProfile, QuestionMetadata, EvaluationRequest, SummaryRequest

logger = setup_logger(__name__)

router = APIRouter(prefix="/api/v1/jd", tags=["jd-engine"])

# --- Request Models ---

class JDGenerateRequest(BaseModel):
    role: str

class JDQuestionRequest(BaseModel):
    role: str
    name: str
    years_experience: str = "3"
    resume_text: str = ""
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None
    skill_weights: Dict[str, int]
    difficulty: str = "mid"
    total_questions: int = 15

class JDFollowUpRequest(BaseModel):
    candidate_response: str
    base_question: str
    skill_weights: Dict[str, int]
    github_repositories: list = []
    experience_years: str = "3"
    role: str = "Engineer"
    jd_skills: list = []
    follow_up_history: list = []

# --- Route Handlers ---

@router.get("/candidates")
async def get_all_candidates():
    from airtable.candidate_loader import CandidateLoader
    try:
        loader = CandidateLoader()
        candidates = loader.fetch_all_candidates()
        
        # Transform dict into list with IDs for frontend
        candidate_list = []
        for cid, data in candidates.items():
            candidate_list.append({
                "id": cid,
                **data
            })
            
        return {"candidates": candidate_list}
    except Exception as e:
        logger.error(f"Failed to fetch candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/evaluation")
async def post_evaluation(request: EvaluationRequest):
    from backend.database import SessionLocal
    from backend.models import EvaluationLog
    db = SessionLocal()
    try:
        new_log = EvaluationLog(
            question_text=request.questionText,
            evaluation_result=request.evaluationResult,
            color_rating=request.colorRating
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return {"status": "success", "id": new_log.id}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save evaluation log: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/generate-summary")
async def api_jd_generate_summary(request: SummaryRequest):
    """Generate final AI summary based on collected interview log."""
    from agents.interview_summarizer import InterviewSummarizerAgent
    try:
        summarizer = InterviewSummarizerAgent()
        result = await summarizer.generate_summary(request)
        return result
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-jd")
async def api_jd_generate(request: JDGenerateRequest):
    """Step 1: Generate a JD from a role and return parsed skills for the UI to display."""
    from agents.job_role_jd_generator import JDGeneratorAgent
    from agents.jd_analyzer import JDAnalyzerAgent
    try:
        jd_gen = JDGeneratorAgent()
        jd_text = await jd_gen.generate_jd_text(request.role)

        jd_analyzer = JDAnalyzerAgent()
        jd_result = await jd_analyzer.analyze_jd(jd_text, request.role)

        return {
            "role": jd_result.role,
            "jd_text": jd_text,
            "required_skills": jd_result.required_skills,
            "domains": jd_result.domains,
            "responsibilities": jd_result.responsibilities[:4]
        }
    except Exception as e:
        logger.error(f"JD generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-questions")
async def api_jd_generate_questions(request: JDQuestionRequest):
    """Step 2: Build candidate profile and generate weighted questions from JD + candidate data."""
    from agents.job_role_jd_generator import JDGeneratorAgent
    from agents.candidate_profile_builder import CandidateProfileBuilder
    from agents.weighted_question_generator import WeightedQuestionGenerator
    try:
        jd_gen = JDGeneratorAgent()
        jd_text = await jd_gen.generate_jd_text(request.role)

        builder = CandidateProfileBuilder()
        profile = await builder.build_profile(
            name=request.name,
            role=request.role,
            experience_years=request.years_experience,
            resume_text=request.resume_text or "No resume provided.",
            linkedin_url=request.linkedin_url or "",
            github_username=request.github_username or "",
            jd_text=jd_text
        )

        q_gen = WeightedQuestionGenerator()
        questions_category = await q_gen.generate_questions(
            profile=profile,
            skill_weights=request.skill_weights,
            difficulty=request.difficulty,
            total_questions=request.total_questions
        )

        flat_questions = []
        category_map = {
            "technical": questions_category.technical_questions,
            "system_design": questions_category.system_design_questions,
            "behavioral": questions_category.behavioral_questions,
            "resume_validation": questions_category.resume_validation_questions,
            "github_project": questions_category.github_project_questions,
        }
        for cat_name, cat_list in category_map.items():
            for q in cat_list:
                flat_questions.append({
                    "category": cat_name,
                    "question": q.question,
                    "reasoning": q.evaluation_goal,
                    "jd_skill": q.jd_skill or "",
                    "difficulty": q.difficulty,
                    "recommended_answer": q.recommended_answer or "No answer provided by AI model."
                })

        return {
            "candidate": request.name,
            "role": request.role,
            "github_repositories": profile.github_repositories,
            "questions": flat_questions
        }
    except Exception as e:
        logger.error(f"JD question generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-followup")
async def api_jd_generate_followup(request: JDFollowUpRequest):
    """Generate a contextual follow-up question using the Interactive Engine logic."""
    from agents.interactive_engine import InteractiveQuestionEngine
    from backend.schemas_jd import CandidateProfile, QuestionMetadata
    try:
        profile = CandidateProfile(
            role=request.role,
            experience_years=request.experience_years,
            github_repositories=request.github_repositories,
            jd_skills=request.jd_skills
        )
        engine = InteractiveQuestionEngine(profile, request.skill_weights)

        engine.follow_up_history = [
            {"question": h.get("question", ""), "response": h.get("response", "")}
            for h in request.follow_up_history
        ]

        base_q = QuestionMetadata(
            question=request.base_question,
            difficulty="mid",
            evaluation_goal="Context-driven follow-up"
        )
        engine.base_questions = [base_q]
        engine.current_index = 0

        follow_up_data = await engine.generate_follow_up(request.candidate_response)
        
        # follow_up_data is now a dict: {"question": "...", "recommended_answer": "..."}
        if isinstance(follow_up_data, dict):
            return {
                "follow_up_question": follow_up_data.get("question", "Could not generate follow-up."),
                "recommended_answer": follow_up_data.get("recommended_answer", "")
            }
        else:
            # Fallback if engine accidentally returned a string
            return {
                "follow_up_question": follow_up_data,
                "recommended_answer": "No answer reasoning provided."
            }
            
    except Exception as e:
        logger.error(f"JD follow-up failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
