import logging
import json
import requests
from backend.schemas_jd import SummaryRequest
from config.logger import setup_logger

logger = setup_logger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest" 

class InterviewSummarizerAgent:
    """Generates an AI summary of an interview based on the recorded log."""

    def _sync_summarize(self, summary_request: SummaryRequest) -> dict:
        logger.info(f"Generating interview summary for {summary_request.candidate_name}")

        log_text = ""
        for i, entry in enumerate(summary_request.interview_log):
            log_text += f"\n--- Question {i+1} ---\n"
            log_text += f"Q: {entry.question}\n"
            log_text += f"Candidate Answer Summary: {entry.candidate_answer_summary}\n"
            log_text += f"Evaluation: {entry.evaluation} ({entry.color})\n"

        prompt = f"""You are an expert technical hiring manager. Based on the following interview log, generate a final AI summary of the candidate's performance.

Candidate Name: {summary_request.candidate_name}
Role: {summary_request.role}
Skills: {", ".join(summary_request.skills)}
Experience: {summary_request.experience}

Interview Log:
{log_text}

Analyze the candidate's answers and the interviewer's evaluations.
Produce exactly four sections in a structured JSON response under these keys:
- "strengths": A short paragraph summarizing technical strengths.
- "weaknesses": A short paragraph summarizing knowledge gaps.
- "overall_technical_capability": A short summary of their capability.
- "hiring_recommendation": Choose exactly one of ["Hire", "Proceed to next round", "Needs improvement", "Reject"].

JSON Output only:"""

        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL, 
                    "prompt": prompt, 
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3, "num_predict": 1024}
                },
                timeout=90
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama summarization failed: {e}")
            return self._fallback_summary()

        if not raw:
            return self._fallback_summary()

        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            data = json.loads(raw[start:end])
            return {
                "strengths": data.get("strengths", "Not enough data to determine strengths."),
                "weaknesses": data.get("weaknesses", "Not enough data to determine weaknesses."),
                "overall_technical_capability": data.get("overall_technical_capability", "Unknown."),
                "hiring_recommendation": data.get("hiring_recommendation", "Needs improvement")
            }
        except Exception as e:
            logger.warning(f"Failed to parse Ollama summary JSON: {e}")
            return self._fallback_summary()

    def _fallback_summary(self) -> dict:
        return {
            "strengths": "AI model failed to generate summary.",
            "weaknesses": "AI model failed to generate summary.",
            "overall_technical_capability": "Unknown due to system error.",
            "hiring_recommendation": "Needs improvement"
        }

    async def generate_summary(self, summary_request: SummaryRequest) -> dict:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_summarize, summary_request
        )
