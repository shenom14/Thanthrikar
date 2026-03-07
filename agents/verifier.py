import asyncio
import json
from typing import Dict, Any, List

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


class VerificationResult(BaseModel):
    is_verified: bool = Field(
        description=(
            "True if the resume evidence clearly supports the claim, "
            "False if it contradicts or exaggerates it."
        )
    )
    explanation: str = Field(
        description="A concise explanation of why the claim is verified or not, based solely on the provided evidence."
    )
    confidence: int = Field(description="Confidence level in the assessment from 0 to 100.")


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
        logger.warning("ResumeVerifierAgent: failed to parse JSON from LLM response.")
        return {}


class ResumeVerifierAgent:
    """
    The ResumeVerifierAgent compares claims detected during the interview
    against the retrieved evidence chunks from the RAG database.
    """

    def __init__(self, llm_model: str = settings.VERIFIER_MODEL) -> None:
        logger.info(f"Initializing ResumeVerifierAgent with model: {llm_model}")
        self.model_name = llm_model

    async def verify_against_evidence(self, claim: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Determine if the candidate's spoken claim is backed up by their resume text.
        """
        logger.info(f"Verifying claim: '{claim}' against {len(evidence)} evidence chunks.")

        evidence_text = "\n---\n".join([chunk.get("text", chunk.get("chunk", "")) for chunk in evidence])
        if not evidence_text.strip():
            logger.warning("No relevant knowledge base evidence found for claim.")
            evidence_text = "No relevant resume evidence found."

        prompt = f"""You are a strict technical recruiter verifying a candidate's spoken interview claim against their resume.
            
Candidate's spoken claim:
"{claim}"

Resume Evidence Retrieved:
{evidence_text}

Analyze if the resume evidence supports the claim. Be highly critical of exaggerated metrics or expanded responsibilities not present in the resume.
If the evidence is empty or entirely irrelevant, the claim cannot be verified.

Return ONLY a valid JSON object with this exact structure:
{{
  "is_verified": true or false,
  "explanation": "<short explanation based solely on the evidence above>",
  "confidence": <integer between 0 and 100>
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
            logger.error(f"ResumeVerifierAgent: LLM call failed: {e}")
            raw = ""

        data = _extract_json(raw)

        try:
            result = VerificationResult(**data)
        except ValidationError as ve:
            logger.warning(f"ResumeVerifierAgent: validation error on LLM output: {ve}")
            # Fallback to a neutral, unverified result.
            result = VerificationResult(
                is_verified=False,
                explanation="Unable to confidently verify claim based on provided resume evidence.",
                confidence=0,
            )

        confidence = max(0, min(100, result.confidence))
        res_dict: Dict[str, Any] = {
            "claim": claim,
            "is_verified": bool(result.is_verified),
            "explanation": result.explanation,
            "confidence": confidence,
        }
        logger.debug(f"Verification completed. Result: {res_dict['is_verified']} (confidence={confidence})")
        return res_dict
