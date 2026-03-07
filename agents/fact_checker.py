import asyncio
import json
from typing import Dict, Any

try:
    from pydantic import BaseModel, Field, ValidationError  # type: ignore
except Exception:  # pragma: no cover - fallback when pydantic is unavailable
    class BaseModel:  # type: ignore
        def __init__(self, **data: Any) -> None:
            for key, value in data.items():
                setattr(self, key, value)

    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore
        return None

    class ValidationError(Exception):  # type: ignore
        pass

from config.logger import setup_logger
from config.settings import settings
from agents.question_generator import _call_ollama_raw  # type: ignore


logger = setup_logger(__name__)


class FactCheckResult(BaseModel):
    is_correct: bool = Field(
        description="True if the candidate's statement is technically accurate, False otherwise."
    )
    explanation: str = Field(
        description="A brief, polite explanation of the correct technical fact to help the interviewer."
    )


def _extract_json(text: str) -> Dict[str, Any]:
    """
    Best-effort extraction of a JSON object from a raw LLM response.
    Falls back to an empty dict on failure.
    """
    if not text:
        return {}

    start = text.find("{")
    end = text.rfind("}")
    candidate = text[start : end + 1] if start != -1 and end != -1 and end > start else text

    try:
        return json.loads(candidate)
    except Exception:
        logger.warning("FactCheckerAgent: failed to parse JSON from LLM response.")
        return {}


class FactCheckerAgent:
    """
    The FactCheckerAgent identifies and verifies technical statements made by the candidate.
    It does not rely on the resume; instead, it relies on general LLM knowledge.
    """

    def __init__(self, llm_model: str = settings.FACT_CHECKER_MODEL) -> None:
        logger.info(f"Initializing FactCheckerAgent with model: {llm_model}")
        self.model_name = llm_model

    async def verify_technical_statement(self, statement: str) -> Dict[str, Any]:
        """
        Check the correctness of a technical point made during an interview.
        """
        statement = statement.strip()
        if not statement:
            return {
                "statement": "",
                "is_correct": None,
                "explanation": "No statement provided for fact checking.",
            }

        logger.info(f"Evaluating technical statement: '{statement}'")

        prompt = f"""You are a senior staff engineer fact-checking technical assertions made by a candidate in an interview.
            
Candidate's Statement:
"{statement}"

Determine if this statement is fundamentally correct. If they are slightly off on trivia but conceptually right, lean towards correct. 
If they state something objectively wrong (e.g. 'Python lists are immutable'), mark it incorrect and provide the correct understanding.

Return ONLY a valid JSON object with this exact structure:
{{
  "is_correct": true or false,
  "explanation": "<brief explanation of the correct technical fact>"
}}
"""
        try:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None,
                _call_ollama_raw,
                prompt,
                0.0,
                60,
            )
        except Exception as e:
            logger.error(f"FactCheckerAgent: LLM call failed: {e}")
            raw = ""

        data = _extract_json(raw)

        try:
            result = FactCheckResult(**data)
        except ValidationError as ve:
            logger.warning(f"FactCheckerAgent: validation error on LLM output: {ve}")
            result = FactCheckResult(
                is_correct=None,
                explanation="Failed to confidently evaluate the technical statement.",
            )

        res_dict: Dict[str, Any] = {
            "statement": statement,
            "is_correct": result.is_correct,
            "explanation": result.explanation,
        }
        logger.debug(f"Fact check result: {res_dict['is_correct']}")
        return res_dict
