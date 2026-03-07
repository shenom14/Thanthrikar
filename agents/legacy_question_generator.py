"""
Question Generator Agent

Responsible for synthesizing candidate data from multiple sources (LinkedIn, GitHub, Resume)
and generating a structured, highly personalized JSON payload of interview questions.
It adapts difficulty based on candidate experience.
"""

import json
import logging
import requests as http_requests
from typing import Dict, Any, List, Optional

# In a real environment, you would import LangChain or OpenAI clients.
# For our system design implementation, we'll demonstrate the orchestration structure
# and mock the final LLM text generation to ensure deterministic structured JSON output.
# import openai

from tools.linkedin_scraper import extract_linkedin_data  # type: ignore
from tools.github_analyzer import analyze_github_profile  # type: ignore

logger = logging.getLogger(__name__)


class QuestionGeneratorEngine:
    """Core engine to generate interview questions for a candidate."""

    OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
    OLLAMA_MODEL = "llama3.2"

    def __init__(self, llm_api_key: Optional[str] = None):
        """
        Initialize the Question Generator Engine.
        
        Args:
            llm_api_key (str): Optional OpenAI or LLM provider API key.
        """
        self.api_key = llm_api_key

    def _call_ollama(self, prompt: str, max_retries: int = 1) -> str:
        """
        Calls the local Ollama API with llama3.2 and returns the generated text.
        Falls back gracefully if Ollama is not available.
        """
        for attempt in range(max_retries + 1):
            try:
                resp = http_requests.post(
                    self.OLLAMA_URL,
                    json={
                        "model": self.OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 2048,
                        }
                    },
                    timeout=60
                )
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
            except Exception as e:
                logger.warning(f"Ollama call failed (attempt {attempt + 1}): {e}")
        return ""

    def _determine_difficulty(self, years_of_experience: int) -> str:
        """Determines the appropriate question difficulty based on years of experience."""
        if years_of_experience <= 2:
            return "Junior (Focus on fundamentals and basic application)"
        elif years_of_experience <= 5:
            return "Mid-level (Focus on applied system knowledge and edge cases)"
        else:
            return "Senior (Focus on architecture, leadership, and system design tradeoffs)"

    def _build_context_prompt(self, candidate_info: Dict[str, Any], linkedin_data: Dict[str, Any], github_data: Dict[str, Any]) -> str:
        """Constructs the prompt detailing the candidate's holistic profile."""
        difficulty = self._determine_difficulty(int(candidate_info.get("years_experience", 0)))
        
        prompt = f"""
        Candidate Role: {candidate_info.get("role")}
        Candidate Experience Context: {difficulty}
        ---
        Resume Highlights: {candidate_info.get("resume_text", "No resume provided.")}
        ---
        LinkedIn Summary: {linkedin_data.get("summary", "")}
        Top Skills: {', '.join(linkedin_data.get("skills", []))}
        ---
        GitHub Top Projects: {json.dumps(github_data.get("top_projects", []), indent=2)}
        """
        return prompt

    def generate_questions(self, candidate_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main pipeline method to extract data, build context, and call LLM for question generation.

        Expected Candidate Info format:
        {
            "name": "John Smith",
            "role": "Backend Engineer",
            "years_experience": 5,
            "resume_text": "...",
            "linkedin_url": "https://...",
            "github_username": "johnsmith"
        }
        """
        logger.info(f"Generating questions for {candidate_info.get('name')} for role {candidate_info.get('role')}")

        # 1. Fetch auxiliary data
        linkedin_url = candidate_info.get("linkedin_url", "")
        github_username = candidate_info.get("github_username", "")
        
        linkedin_data = extract_linkedin_data(linkedin_url) if linkedin_url else {}
        github_data = analyze_github_profile(github_username) if github_username else {}

        # 2. Build the context prompt for the LLM
        context_prompt = self._build_context_prompt(candidate_info, linkedin_data, github_data)
        logger.debug(f"LLM Context generated: {context_prompt}")

        # 3. Use mock data for instant initial question generation (Ollama is used for follow-ups)
        # Note: To use Ollama for initial questions too (slower, ~30-60s), call:
        #   return self._ollama_generate_questions(candidate_info, context_prompt) or self._mock_llm_generation(...)
        return self._mock_llm_generation(candidate_info, linkedin_data, github_data)

    def _ollama_generate_questions(self, candidate_info: Dict[str, Any], context_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Uses Ollama llama3.2 to generate 20 personalized interview questions.
        Returns None if Ollama is unavailable or response is malformed.
        """
        prompt = f"""You are an expert technical interviewer. Generate exactly 20 interview questions for a candidate.

Candidate Profile:
{context_prompt}

Generate questions in this EXACT JSON format (no markdown, no extra text, ONLY valid JSON):
{{
  "technical": [
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}}
  ],
  "system_design": [
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}}
  ],
  "behavioral": [
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}}
  ],
  "resume_validation": [
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}}
  ],
  "github_project": [
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}},
    {{"question": "...", "reasoning": "..."}}
  ]
}}

Rules:
- Each category MUST have exactly 4 questions
- Each question must have both "question" and "reasoning" fields
- Questions should be tailored to the candidate's profile
- Output ONLY the JSON object, nothing else"""

        raw = self._call_ollama(prompt)
        if not raw:
            return None

        # Try to extract JSON from the response
        try:
            # Try direct parse
            questions = json.loads(raw)
        except json.JSONDecodeError:
            # Try to find JSON block in the response
            try:
                start = raw.index("{")
                end = raw.rindex("}") + 1
                questions = json.loads(raw[start:end])
            except (ValueError, json.JSONDecodeError):
                logger.warning("Could not parse Ollama response as JSON")
                return None

        # Validate structure
        required_categories = ["technical", "system_design", "behavioral", "resume_validation", "github_project"]
        for cat in required_categories:
            if cat not in questions or not isinstance(questions[cat], list) or len(questions[cat]) < 1:
                logger.warning(f"Ollama response missing or empty category: {cat}")
                return None

        logger.info(f"Ollama generated {sum(len(v) for v in questions.values())} questions successfully")

        return {
            "candidate": candidate_info.get("name"),
            "role": candidate_info.get("role"),
            "experience": f"{candidate_info.get('years_experience')} years",
            "questions": questions
        }

    def _mock_llm_generation(self, candidate_info: Dict[str, Any], linkedin_data: Dict, github_data: Dict) -> Dict[str, Any]:
        """Fallback: provides deterministic JSON with exactly 20 diverse questions."""
        
        # Extract dynamic data for personalized questions
        github_projects = github_data.get("top_projects", [])
        linkedin_skills = linkedin_data.get("skills", [])
        
        # Build dynamic questions based on extracted context
        tech_q = "Explain the architecture of a microservices system you designed."
        tech_r = "Standard technical assessment for engineers."
        
        if linkedin_skills:
            tech_q = f"How would you apply your skills in {', '.join(linkedin_skills[:2])} to optimizing a high-traffic system?"
            tech_r = f"Probing stated skills extracted from LinkedIn profile."
            
        gh_q = "Can you describe a challenging problem you solved in an open-source project?"
        gh_r = "General open-source code contribution question."
        
        if github_projects:
            top_repo = github_projects[0]
            gh_q = f"Your GitHub repository '{top_repo.get('name')}' (written in {top_repo.get('primary_language')}) looks interesting. Can you explain the architectural challenges you faced building it?"
            gh_r = f"Deep-dive into verified open-source contributions detected on GitHub."

        # Exactly 20 questions: 4 technical, 4 system_design, 4 behavioral, 4 resume_validation, 4 github_project
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
                    {"question": "What testing strategies did you employ for your open source repositories to ensure community PRs didn't break functionality?", "reasoning": "CI/CD and test-driven assessment."},
                    {"question": "How do you approach code review and maintaining quality in open-source contributions?", "reasoning": "Collaboration and quality assessment."},
                    {"question": "Explain how you use Git workflows (branching, rebasing, or release tags) in your GitHub projects.", "reasoning": "Version control and release practices."},
                ]
            }
        }

    def generate_follow_up(self, current_question: str, context: str = "") -> str:
        """
        Dynamically generates a logical follow-up question using Ollama.
        This provides infinite drill-down capability with unique questions every time.
        """
        logger.info(f"Generating follow-up for: {current_question}")

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

        result = self._call_ollama(prompt)
        if result:
            # Clean up: remove any leading/trailing quotes or numbering
            result = result.strip('"\' \n')
            if result.startswith(('1.', '1)', '-', '*')):
                result = result[2:].strip()
            return result

        # Fallback if Ollama is unavailable
        logger.warning("Ollama unavailable for follow-up, using fallback.")
        return "Can you elaborate on the specific challenges you faced and how you overcame them?"


def generate_candidate_questions(candidate_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function meant to be imported by the API endpoints.
    """
    engine = QuestionGeneratorEngine()
    return engine.generate_questions(candidate_info)

def generate_followup_question(current_question: str, context: str = "") -> str:
    """Convenience function for API endpoint."""
    engine = QuestionGeneratorEngine()
    return engine.generate_follow_up(current_question, context)
