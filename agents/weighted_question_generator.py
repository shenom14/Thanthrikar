import logging
import json
import requests
from typing import Dict, List
from config.logger import setup_logger
from backend.schemas_jd import CandidateProfile, QuestionCategory, QuestionMetadata

logger = setup_logger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"


def _call_ollama(prompt: str, max_retries: int = 1) -> str:
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.7, "num_predict": 4096}},
                timeout=90
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama call failed (attempt {attempt + 1}): {e}")
    return ""

class WeightedQuestionGenerator:
    """Generates JD-weighted interview questions using Ollama."""

    def _sync_generate(self, profile: CandidateProfile, skill_weights: Dict[str, int],
                       difficulty: str, total_questions: int) -> QuestionCategory:
        logger.info(f"Generating {total_questions} {difficulty} questions via Ollama for {profile.name}")

        repo_str = ", ".join([r.get("name", "") for r in profile.github_repositories]) or "None"
        weight_str = ", ".join([f"{s}: {w}%" for s, w in skill_weights.items()])

        prompt = f"""You are an expert technical interviewer. Generate exactly {total_questions} interview questions for the role of {profile.role}.
        
Candidate: {profile.name}
Experience: {profile.experience_years} years
Difficulty: {difficulty}
Skill Priorities: {weight_str}
GitHub Repos: {repo_str}

Distribute the {total_questions} questions across these categories:
- technical_questions
- system_design_questions  
- behavioral_questions
- resume_validation_questions
- github_project_questions

Return a JSON object with these category keys, each mapping to a list of question objects.
Each question object must have: "question", "jd_skill", "candidate_skill", "difficulty", "evaluation_goal", "recommended_answer".
The "recommended_answer" should be a high-quality, comprehensive expected answer (3-5 sentences).
"""

        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL, 
                    "prompt": prompt, 
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3, "num_predict": 4096}
                },
                timeout=90
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
            return self._fallback_category(difficulty)

        if not raw:
            return self._fallback_category(difficulty)

        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            data = json.loads(raw[start:end])

            def parse_list(lst: list) -> List[QuestionMetadata]:
                result = []
                for q in lst:
                    if isinstance(q, dict) and "question" in q:
                        result.append(QuestionMetadata(
                            question=q.get("question", ""),
                            jd_skill=q.get("jd_skill"),
                            candidate_skill=q.get("candidate_skill"),
                            difficulty=q.get("difficulty", difficulty),
                            evaluation_goal=q.get("evaluation_goal", "Assess candidate knowledge"),
                            recommended_answer=q.get("recommended_answer", "No answer provided by AI model.")
                        ))
                return result

            return QuestionCategory(
                technical_questions=parse_list(data.get("technical_questions", [])),
                system_design_questions=parse_list(data.get("system_design_questions", [])),
                behavioral_questions=parse_list(data.get("behavioral_questions", [])),
                resume_validation_questions=parse_list(data.get("resume_validation_questions", [])),
                github_project_questions=parse_list(data.get("github_project_questions", []))
            )
        except Exception as e:
            logger.warning(f"Failed to parse Ollama question JSON: {e}")
            return self._fallback_category(difficulty)

    def _fallback_category(self, difficulty: str) -> QuestionCategory:
        fallback = QuestionMetadata(
            question="Can you describe a challenging problem you solved in your past roles?",
            difficulty=difficulty,
            evaluation_goal="Problem solving and resilience"
        )
        return QuestionCategory(technical_questions=[fallback])

    async def generate_questions(self, profile: CandidateProfile, skill_weights: Dict[str, int],
                                  difficulty: str = "mid", total_questions: int = 15) -> QuestionCategory:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_generate, profile, skill_weights, difficulty, total_questions
        )
