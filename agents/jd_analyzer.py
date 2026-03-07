import logging
import json
import requests
from config.logger import setup_logger
from backend.schemas_jd import JDAnalysisResult

logger = setup_logger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

def _call_ollama(prompt: str, max_retries: int = 1) -> str:
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.2, "num_predict": 1024}},
                timeout=60
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama call failed (attempt {attempt + 1}): {e}")
    return ""

class JDAnalyzerAgent:
    """Parses a Job Description into structured fields using Ollama."""

    def _sync_analyze(self, jd_text: str, role: str) -> JDAnalysisResult:
        logger.info("Analyzing JD with Ollama...")
        prompt = f"""Extract structured information from the Job Description below.
Output ONLY a valid JSON object with these exact keys:
{{
  "role": "<job role title>",
  "required_skills": ["skill1", "skill2", "skill3", ...],
  "domains": ["domain1", "domain2", ...],
  "responsibilities": ["resp1", "resp2", ...]
}}

Job Description:
{jd_text}

Output ONLY the JSON. No markdown, no explanation."""

        raw = _call_ollama(prompt)
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            data = json.loads(raw[start:end])
            return JDAnalysisResult(
                role=data.get("role", role),
                required_skills=data.get("required_skills", []),
                domains=data.get("domains", []),
                responsibilities=data.get("responsibilities", [])
            )
        except Exception as e:
            logger.warning(f"Failed to parse JD JSON: {e}. Using fallback.")
            return JDAnalysisResult(
                role=role,
                required_skills=["Python", "System Design", "APIs"],
                domains=["Backend architecture"],
                responsibilities=["Develop and maintain systems"]
            )

    async def analyze_jd(self, jd_text: str, role: str = "Unknown") -> JDAnalysisResult:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_analyze, jd_text, role)
