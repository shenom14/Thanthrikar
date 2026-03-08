import logging
import random
from typing import Dict, List
from config.logger import setup_logger
from backend.schemas_jd import CandidateProfile, QuestionCategory, QuestionMetadata

logger = setup_logger(__name__)

class WeightedQuestionGenerator:
    """Generates interview questions instantly using a fast template-based hybrid system instead of a slow full LLM generation."""

    # Predefined question templates logic
    TEMPLATES = {
        "technical": [
            "Given your experience with {skill}, how would you approach optimizing a system built with it?",
            "Can you describe a challenging bug you faced while working with {skill} and how you resolved it?",
            "Explain the core principles of {skill} to someone who has never used it before.",
            "What are the common anti-patterns you try to avoid when developing with {skill}?",
            "How do you handle dependency management and versioning when working extensively with {skill}?"
        ],
        "system_design": [
            "How would you design a scalable architecture using {skill} to handle 10,000 requests per second?",
            "If a service relying on {skill} goes down, what failsafe mechanisms would you have in place?",
            "Walk me through how you would structure the data flow for an application heavily utilizing {skill}.",
        ],
        "behavioral": [
            "Tell me about a time you had to learn a new technology quickly to solve a problem with {skill}.",
            "How do you resolve technical disagreements within a team, especially regarding {skill} best practices?",
            "Describe a project where you took the lead on implementing a solution using {skill}.",
        ],
        "github": [
            "I see you have experience with {repo_name}. What was the most complex technical challenge there?",
            "In your project {repo_name}, what was the rationale behind the architectural choices you made?",
            "If you were to rewrite {repo_name} today, what would you do differently?"
        ]
    }

    def _sync_generate(self, profile: CandidateProfile, skill_weights: Dict[str, int],
                       difficulty: str, total_questions: int) -> QuestionCategory:
        logger.info(f"Generating {total_questions} {difficulty} questions via Fast Templates for {profile.name}")

        # Extract top skills based on weights provided by UI
        sorted_skills = sorted(skill_weights.items(), key=lambda x: x[1], reverse=True)
        top_skills = [s[0] for s in sorted_skills] if sorted_skills else profile.jd_skills
        if not top_skills:
            top_skills = ["Software Engineering", "System Design", "Algorithms"]

        repos = [r.get("name", "your past projects") for r in profile.github_repositories]
        if not repos:
            repos = ["your past projects"]

        def _build_questions(category_key: str, count: int, use_repos: bool = False) -> List[QuestionMetadata]:
            questions = []
            templates = self.TEMPLATES.get(category_key, self.TEMPLATES["technical"])
            
            for i in range(count):
                template = random.choice(templates)
                skill = random.choice(top_skills)
                repo = random.choice(repos)
                
                if use_repos and "{repo_name}" in template:
                    q_text = template.replace("{repo_name}", repo)
                else:
                    q_text = template.replace("{skill}", skill).replace("{repo_name}", repo)
                
                questions.append(QuestionMetadata(
                    question=q_text,
                    jd_skill=skill if not use_repos else "GitHub/Projects",
                    candidate_skill=skill,
                    difficulty=difficulty,
                    evaluation_goal=f"Assess {difficulty} knowledge of {skill if not use_repos else repo}",
                    recommended_answer=f"Candidate should demonstrate practical experience and best practices regarding {skill if not use_repos else repo}."
                ))
            return questions

        # Distribute questions
        tech_count = max(1, int(total_questions * 0.4))
        sys_count = max(1, int(total_questions * 0.2))
        beh_count = max(1, int(total_questions * 0.2))
        git_count = total_questions - (tech_count + sys_count + beh_count)
        if git_count < 0: git_count = 0

        return QuestionCategory(
            technical_questions=_build_questions("technical", tech_count),
            system_design_questions=_build_questions("system_design", sys_count),
            behavioral_questions=_build_questions("behavioral", beh_count),
            github_project_questions=_build_questions("github", git_count, use_repos=True),
            resume_validation_questions=_build_questions("technical", 1) # Bonus
        )

    async def generate_questions(self, profile: CandidateProfile, skill_weights: Dict[str, int],
                                  difficulty: str = "mid", total_questions: int = 15) -> QuestionCategory:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._sync_generate, profile, skill_weights, difficulty, total_questions
        )
