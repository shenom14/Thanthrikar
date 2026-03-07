import logging
import json
import requests
from typing import Dict, List, Optional
from config.logger import setup_logger
from backend.schemas_jd import CandidateProfile, QuestionMetadata

logger = setup_logger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

def _call_ollama(prompt: str, max_retries: int = 1) -> str:
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.6, "num_predict": 512}},
                timeout=60
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama follow-up call failed (attempt {attempt + 1}): {e}")
    return ""

class InteractiveQuestionEngine:
    """
    Stateful engine controlling interview flow.
    - next_question(): advance to next base question
    - generate_follow_up(response): infinite contextual follow-ups via Ollama
    """

    def __init__(self, profile: CandidateProfile, skill_weights: Dict[str, int]):
        logger.info(f"Initializing Interactive Engine for {profile.name}")
        self.profile = profile
        self.skill_weights = skill_weights
        self.base_questions: List[QuestionMetadata] = []
        self.current_index = 0
        self.follow_up_history: List[Dict[str, str]] = []

    def load_questions(self, category):
        """Flatten QuestionCategory into ordered queue."""
        self.base_questions = []
        for lst in [
            category.technical_questions,
            category.system_design_questions,
            category.behavioral_questions,
            category.resume_validation_questions,
            category.github_project_questions
        ]:
            self.base_questions.extend(lst)
        self.current_index = 0
        self.follow_up_history = []
        logger.info(f"Loaded {len(self.base_questions)} base questions.")

    def get_current_question(self) -> Optional[QuestionMetadata]:
        if self.current_index < len(self.base_questions):
            return self.base_questions[self.current_index]
        return None

    def next_question(self) -> Optional[QuestionMetadata]:
        """Move to next base question, reset follow-up context."""
        if self.current_index < len(self.base_questions) - 1:
            self.current_index += 1
            self.follow_up_history = []
            return self.base_questions[self.current_index]
        return None

    def _sync_generate_follow_up(self, candidate_response: str) -> str:
        base_q = self.get_current_question()
        if not base_q:
            return "No active question to follow up on."

        history_str = ""
        for item in self.follow_up_history:
            history_str += f"Q: {item['question']}\nA: {item['response']}\n---\n"

        current_q_text = (self.follow_up_history[-1]["question"]
                          if self.follow_up_history else base_q.question)

        self.follow_up_history.append({"question": current_q_text, "response": candidate_response})

        repo_str = ", ".join([r.get("name", "") for r in self.profile.github_repositories]) or "None"
        weight_str = ", ".join([f"{s}: {w}%" for s, w in self.skill_weights.items()])

        prompt = f"""You are an expert technical interviewer.

Role: {self.profile.role} | Focus Areas: {weight_str}
Candidate Repositories: {repo_str}

Base Question: "{base_q.question}"

Previous conversation:
{history_str if history_str else 'None'}

The candidate just responded: "{candidate_response}"

Generate exactly ONE follow-up question that digs deeper into the candidate's response.
Output ONLY the question text. No prefix, no quotes, no explanation."""

        result = _call_ollama(prompt)
        if result:
            result = result.strip('"\'').strip()
            if result.startswith(("1.", "1)", "-", "*")):
                result = result[2:].strip()
            return result

        self.follow_up_history.pop()  # rollback on failure
        logger.warning("Ollama unavailable for follow-up, using fallback.")
        return "Can you expand more on the technical choices involved there?"

    async def generate_follow_up(self, candidate_response: str) -> str:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync_generate_follow_up, candidate_response)
