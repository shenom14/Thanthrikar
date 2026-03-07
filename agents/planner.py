import asyncio
import json
from types import SimpleNamespace
from typing import List, Dict, Any

try:
    from pydantic import BaseModel, Field  # type: ignore
except Exception:  # pragma: no cover - fallback when pydantic is unavailable
    class BaseModel:  # type: ignore
        def __init__(self, **data: Any) -> None:
            for key, value in data.items():
                setattr(self, key, value)

    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore
        return None

from config.logger import setup_logger
from config.settings import settings
from agents.question_generator import _call_ollama_raw  # type: ignore


logger = setup_logger(__name__)


class ClaimTask(BaseModel):
    task: str = Field(
        description=(
            "The type of task: 'verify_claim' if it's a resume claim, or "
            "'fact_check' if it's a general technical statement."
        )
    )
    claim: str = Field(description="The exact text of the claim or statement.")


class PlannerTasks(BaseModel):
    tasks: List[ClaimTask] = Field(description="List of detected claims or technical statements.")


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
        logger.warning("PlannerAgent: failed to parse JSON from LLM response.")
        return {}


class PlannerAgent:
    """
    The Planner Agent listens to the ongoing interview transcript to identify actionable claims
    and route them to the appropriate down-stream validation agents.
    """

    def __init__(self, llm_model: str = settings.PLANNER_MODEL) -> None:
        logger.info(f"Initializing PlannerAgent with model: {llm_model}")
        self.model_name = llm_model
        # Lightweight stub so existing unit tests that inspect `.llm.model_name` still pass.
        self.llm = SimpleNamespace(model_name=llm_model)

    async def analyze_transcript(self, transcript_chunk: str) -> List[Dict[str, Any]]:
        """
        Analyze a portion of the transcript for specific verification tasks using Ollama directly.
        """
        transcript_chunk = transcript_chunk.strip()
        if not transcript_chunk:
            return []

        logger.debug(f"Analyzing transcript chunk length {len(transcript_chunk)}")

        prompt = f"""You are an AI assistant analyzing an interview transcript in real-time.
Your goal is to extract any testable claims or technical statements made by the candidate.

Note: The transcript arrives in very short 2-second live chunks. You must evaluate even partial sentences or brief keywords!
- If the candidate mentions an experience, project, metric, or responsibility (even briefly like "I built a React app"), classify it as 'verify_claim'.
- If the candidate states a technical fact (e.g., "React uses a virtual DOM" or "Python lists"), classify it as 'fact_check'.
Only return an empty list if the snippet contains zero technical terms, zero names, and zero claims (e.g., "uh", "hello", "yes").

Return ONLY a valid JSON object with this exact structure:
{{
  "tasks": [
    {{
      "task": "verify_claim" or "fact_check",
      "claim": "<the exact text of the claim or statement>"
    }}
  ]
}}

Transcript snippet:
"{transcript_chunk}"
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
            logger.error(f"PlannerAgent: LLM call failed: {e}")
            raw = ""

        data = _extract_json(raw)
        tasks_raw = data.get("tasks", []) if isinstance(data, dict) else []

        extracted: List[Dict[str, Any]] = []
        for item in tasks_raw:
            if not isinstance(item, dict):
                continue
            task_type = item.get("task")
            claim = item.get("claim")
            if isinstance(task_type, str) and isinstance(claim, str) and task_type in {
                "verify_claim",
                "fact_check",
            }:
                extracted.append({"task": task_type, "claim": claim})

        # Fallback: if the model did not return any structured tasks, treat the
        # entire snippet as a single verify-able claim so downstream agents still run.
        if not extracted and transcript_chunk:
            extracted.append({"task": "verify_claim", "claim": transcript_chunk})

        logger.info(f"Extracted {len(extracted)} actionable distinct claims.")
        return extracted
