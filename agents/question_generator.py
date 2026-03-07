"""
Question Generator Agent

Unified implementation supporting both Ollama (local) and Groq (cloud) LLM backends.
Produces pre-interview questions and real-time follow-ups during interviews.
"""

import json
import logging
import requests as http_requests
from typing import List, Dict, Any, Optional

from config.logger import setup_logger
from config.settings import settings

logger = setup_logger(__name__)


# ---------------------------------------------------------------------------
# LLM Factory — creates the right LLM based on settings.LLM_BACKEND
# ---------------------------------------------------------------------------

def _create_llm(temperature: float = 0.7, model_override: str = None):
    """
    Factory that returns a LangChain-compatible LLM.
    Uses Ollama (local) by default; falls back to Groq if configured.
    """
    backend = getattr(settings, "LLM_BACKEND", "ollama").lower()
    model = model_override or settings.QGEN_MODEL

    if backend == "groq":
        try:
            from langchain_groq import ChatGroq  # type: ignore
            logger.info(f"Using Groq LLM backend with model: {model}")
            return ChatGroq(model_name=model, temperature=temperature)
        except Exception as e:
            logger.warning(f"Groq init failed ({e}), falling back to Ollama.")
            backend = "ollama"

    # Default: Ollama
    try:
        from langchain_ollama import ChatOllama  # type: ignore
        ollama_model = getattr(settings, "OLLAMA_MODEL", "llama3.2")
        ollama_url = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        logger.info(f"Using Ollama LLM backend with model: {ollama_model}")
        return ChatOllama(
            model=ollama_model,
            base_url=ollama_url,
            temperature=temperature,
        )
    except ImportError:
        logger.warning("langchain-ollama not installed; using raw HTTP fallback.")
        return None


# ---------------------------------------------------------------------------
# Raw Ollama HTTP helper (fallback when LangChain isn't available)
# ---------------------------------------------------------------------------

OLLAMA_API_URL = getattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434") + "/api/generate"
OLLAMA_MODEL = getattr(settings, "OLLAMA_MODEL", "llama3.2")


def _call_ollama_raw(prompt: str, temperature: float = 0.7, timeout: int = 60) -> str:
    """Direct HTTP call to Ollama API. Returns generated text or empty string."""
    try:
        resp = http_requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": 2048},
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning(f"Raw Ollama call failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel, Field
    from langchain_core.output_parsers import PydanticOutputParser  # type: ignore
    from langchain_core.prompts import PromptTemplate  # type: ignore

    class FollowUpResult(BaseModel):
        question: Optional[str] = Field(
            description="The suggested follow-up question, or null if no question is necessary."
        )

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain not available; using raw Ollama API directly.")


# ---------------------------------------------------------------------------
# QuestionGeneratorAgent — main class
# ---------------------------------------------------------------------------

class QuestionGeneratorAgent:
    """
    Generates pre-interview questions and real-time follow-up questions.
    Supports both Ollama (local) and Groq (cloud) backends.
    """

    def __init__(self, llm_model: str = None) -> None:
        model = llm_model or settings.QGEN_MODEL
        logger.info(f"Initializing QuestionGeneratorAgent with model: {model}")

        self.llm = _create_llm(temperature=0.7, model_override=model)
        self.langchain_mode = LANGCHAIN_AVAILABLE and self.llm is not None

        if self.langchain_mode:
            self.parser = PydanticOutputParser(pydantic_object=FollowUpResult)

            self.initial_prompt = PromptTemplate(
                template="""You are preparing questions for an interview for a {role} position.
The candidate has {experience} of experience.

Resume Overview:
{resume_summary}

Generate EXACTLY {count} specific, deeply technical interview questions targeting their resume experience.
Output them as a simple numbered list.""",
                input_variables=["role", "experience", "resume_summary", "count"],
            )
            self.initial_chain = self.initial_prompt | self.llm

            self.follow_up_prompt = PromptTemplate(
                template="""You are an AI assistant helping an interviewer inside a live interview.
The candidate just made this statement: "{claim}"

Based on background verification, we found the following AI Insight:
"{insight_context}"

If this insight suggests an exaggeration, falsehood, or point of confusion, generate a polite but probing follow-up question to dig deeper.
If the insight confirms everything is perfectly fine, you should STILL generate a natural, engaging follow-up question to keep the conversation flowing.
Only return null if the topic is completely exhausted.

{format_instructions}""",
                input_variables=["claim", "insight_context"],
                partial_variables={"format_instructions": self.parser.get_format_instructions()},
            )
            self.follow_up_chain = (
                self.follow_up_prompt
                | _create_llm(temperature=0.5, model_override=model)
                | self.parser
            )

    # -----------------------------------------------------------------------
    # Initial question generation
    # -----------------------------------------------------------------------

    async def generate_initial_questions(
        self, role: str, experience: str, resume_summary: str, count: int = 5
    ) -> List[str]:
        """Generate initial interview questions using the LLM."""
        logger.info(f"Generating {count} initial questions for {role}...")
        try:
            if self.langchain_mode:
                result = await self.initial_chain.ainvoke({
                    "role": role,
                    "experience": experience,
                    "resume_summary": resume_summary,
                    "count": count,
                })
                lines = result.content.strip().split("\n")
                extracted = [line.strip() for line in lines if line.strip()]
                logger.debug(f"Generated {len(extracted)} initial questions.")
                return extracted
            else:
                # Raw Ollama fallback
                prompt = f"""You are preparing questions for an interview for a {role} position.
The candidate has {experience} of experience.

Resume Overview:
{resume_summary}

Generate EXACTLY {count} specific, deeply technical interview questions.
Output them as a simple numbered list."""
                raw = _call_ollama_raw(prompt)
                if raw:
                    lines = raw.strip().split("\n")
                    return [line.strip() for line in lines if line.strip()]
                return []
        except Exception as e:
            logger.error(f"Error generating initial questions: {e}")
            return []

    # -----------------------------------------------------------------------
    # Follow-up generation (used by StreamingPipeline)
    # -----------------------------------------------------------------------

    async def generate_follow_up(
        self,
        claim: str,
        verification_result: Optional[Dict[str, Any]] = None,
        fact_check_result: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Generate a contextual follow-up question based on claim verification."""
        logger.info(f"Attempting to generate follow up for claim: '{claim}'")

        insight_context = ""
        if verification_result and not verification_result.get("is_verified", True):
            insight_context = f"Resume verification failed: {verification_result.get('explanation')}"
        elif fact_check_result and not fact_check_result.get("is_correct", True):
            insight_context = f"Fact check failed: {fact_check_result.get('explanation')}"
        else:
            insight_context = (
                "All claims appear verified and correct. "
                "Suggest a natural follow-up question to keep the conversation engaging."
            )
            logger.debug("Positive insight detected. Requesting proactive follow-up.")

        try:
            if self.langchain_mode:
                result = await self.follow_up_chain.ainvoke({
                    "claim": claim,
                    "insight_context": insight_context,
                })
                logger.debug(f"Generated follow-up: {result.question}")
                return result.question
            else:
                # Raw Ollama fallback
                prompt = f"""You are an AI interviewer assistant. The candidate said: "{claim}"
AI Insight: "{insight_context}"
Generate one probing follow-up question. Respond with ONLY the question text."""
                raw = _call_ollama_raw(prompt, temperature=0.5)
                return raw if raw else None
        except Exception as e:
            logger.error(f"Error generating follow up question: {e}")
            return None


# ---------------------------------------------------------------------------
# Extension-facing convenience functions (backward compatibility with boom)
# ---------------------------------------------------------------------------

def _get_mock_questions(candidate_info: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback mock data — returns 20 hardcoded questions instantly."""
    from tools.linkedin_scraper import extract_linkedin_data  # type: ignore
    from tools.github_analyzer import analyze_github_profile  # type: ignore

    linkedin_url = candidate_info.get("linkedin_url", "")
    github_username = candidate_info.get("github_username", "")
    linkedin_data = extract_linkedin_data(linkedin_url) if linkedin_url else {}
    github_data = analyze_github_profile(github_username) if github_username else {}

    github_projects = github_data.get("top_projects", [])
    linkedin_skills = linkedin_data.get("skills", [])

    tech_q = "Explain the architecture of a microservices system you designed."
    tech_r = "Standard technical assessment for engineers."
    if linkedin_skills:
        tech_q = f"How would you apply your skills in {', '.join(linkedin_skills[:2])} to optimizing a high-traffic system?"
        tech_r = "Probing stated skills extracted from LinkedIn profile."

    gh_q = "Can you describe a challenging problem you solved in an open-source project?"
    gh_r = "General open-source code contribution question."
    if github_projects:
        top_repo = github_projects[0]
        gh_q = f"Your GitHub repository '{top_repo.get('name')}' (written in {top_repo.get('primary_language')}) looks interesting. Can you explain the architectural challenges you faced building it?"
        gh_r = "Deep-dive into verified open-source contributions detected on GitHub."

    return {
        "candidate": candidate_info.get("name"),
        "role": candidate_info.get("role"),
        "experience": f"{candidate_info.get('years_experience')} years",
        "questions": {
            "technical": [
                {"question": tech_q, "reasoning": tech_r},
                {"question": "Can you explain the difference between container orchestration and container runtime?", "reasoning": "Standard backend engineering question."},
                {"question": "How do you handle zero-downtime deployments in a load-balanced environment?", "reasoning": "Assessing DevOps and reliability mechanics."},
                {"question": "What is the N+1 query problem, and how do you resolve it in an ORM?", "reasoning": "Basic database access optimization."},
            ],
            "system_design": [
                {"question": "How would you design a scalable notification system capable of 1M RPS?", "reasoning": "Evaluates architectural tradeoffs."},
                {"question": "Design a URL shortener service like bit.ly.", "reasoning": "Classic state-storage and redirection problem."},
                {"question": "How would you implement leader election in a distributed database cluster?", "reasoning": "Testing knowledge of consensus algorithms like Raft/Paxos."},
                {"question": "How do you implement distributed tracing across microservices?", "reasoning": "Observability and debugging at scale."},
            ],
            "behavioral": [
                {"question": "Tell me about a challenging technical problem you solved recently where you had tight deadlines.", "reasoning": "Standard behavioral indicator for engineering execution."},
                {"question": "Describe a time you strongly disagreed with a senior engineer on a technical design. How did you resolve it?", "reasoning": "Assessing conflict resolution and communication."},
                {"question": "Tell me about a production outage you caused or helped mitigate. What was the post-mortem action?", "reasoning": "Evaluating blameless culture and incident response."},
                {"question": "Describe a situation where you had to learn a completely new technology stack in a matter of days.", "reasoning": "Assessing learning velocity."},
            ],
            "resume_validation": [
                {"question": "Your resume mentions specific technical leadership. What was the team structure and your specific responsibilities?", "reasoning": "Follow-up verification of claims."},
                {"question": "You mentioned delivering a major refactor. How did you ensure feature parity during the rewrite?", "reasoning": "Validating legacy code understanding."},
                {"question": "How did you measure the performance improvements listed on your resume?", "reasoning": "Checking metrics-driven engineering claims."},
                {"question": "Walk me through a key project from your resume and the technical decisions you owned.", "reasoning": "Validating ownership and depth of experience."},
            ],
            "github_project": [
                {"question": gh_q, "reasoning": gh_r},
                {"question": "What testing strategies did you employ for your open source repositories?", "reasoning": "CI/CD and test-driven assessment."},
                {"question": "How do you approach code review and maintaining quality in open-source contributions?", "reasoning": "Collaboration and quality assessment."},
                {"question": "Explain how you use Git workflows (branching, rebasing, or release tags) in your GitHub projects.", "reasoning": "Version control and release practices."},
            ],
        },
    }


def generate_candidate_questions(candidate_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extension-facing function: generates 20 structured interview questions.
    Uses mock data for instant response (the extension expects structured JSON).
    """
    return _get_mock_questions(candidate_info)


def generate_followup_question(current_question: str, context: str = "") -> str:
    """
    Extension-facing function: generates a follow-up question using Ollama.
    """
    prompt = f"""You are an expert technical interviewer conducting a deep-dive interview.

The current interview question is:
"{current_question}"

{f'Previous follow-up questions already asked (DO NOT repeat any of these):' + chr(10) + context if context else ''}

Generate exactly ONE follow-up question that:
1. Digs deeper into the topic of the current question
2. Is completely different from any previous follow-ups listed above
3. Tests a different angle or aspect of the candidate's knowledge
4. Is specific and technical, not generic

Respond with ONLY the follow-up question text, nothing else. No quotes, no prefix, no numbering."""

    result = _call_ollama_raw(prompt)
    if result:
        result = result.strip('"\'  \n')
        if result.startswith(("1.", "1)", "-", "*")):
            result = result[2:].strip()
        return result

    return "Can you elaborate on the specific challenges you faced and how you overcame them?"
