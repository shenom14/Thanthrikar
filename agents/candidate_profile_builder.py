import logging
import asyncio
from typing import Dict, Any, List
from config.logger import setup_logger
from backend.schemas_jd import CandidateProfile
from tools.linkedin_scraper import extract_linkedin_data
from tools.github_analyzer import analyze_github_profile
from agents.jd_analyzer import JDAnalyzerAgent

logger = setup_logger(__name__)

class CandidateProfileBuilder:
    def __init__(self):
        self.jd_analyzer = JDAnalyzerAgent()

    async def build_profile(
        self,
        name: str,
        role: str,
        experience_years: str,
        resume_text: str,
        linkedin_url: str,
        github_username: str,
        jd_text: str
    ) -> CandidateProfile:
        logger.info(f"Building unified CandidateProfile for {name}")
        
        # 1. Analyze JD
        jd_task = self.jd_analyzer.analyze_jd(jd_text, role)
        
        # 2. Extract LinkedIn and Github (blocking I/O offloaded to threads)
        loop = asyncio.get_running_loop()
        
        # Graceful handling if URLs are empty to save time
        if linkedin_url:
            linkedin_task = loop.run_in_executor(None, extract_linkedin_data, linkedin_url)
        else:
            linkedin_task = asyncio.sleep(0, result={})
            
        if github_username:
            github_task = loop.run_in_executor(None, analyze_github_profile, github_username)
        else:
            github_task = asyncio.sleep(0, result={})

        jd_result, linkedin_data, github_data = await asyncio.gather(jd_task, linkedin_task, github_task)

        # Basic parsing of resume skills against JD
        resume_skills_found = [s for s in jd_result.required_skills if s.lower() in resume_text.lower()]
        
        logger.info(f"Profile built. JD Skills: {len(jd_result.required_skills)}, Git repos: {len(github_data.get('top_projects', []))}")

        profile = CandidateProfile(
            name=name,
            role=role,
            experience_years=str(experience_years),
            resume_skills=resume_skills_found,
            linkedin_skills=linkedin_data.get("skills", []),
            linkedin_summary=linkedin_data.get("summary", ""),
            github_repositories=github_data.get("top_projects", []),
            github_languages=github_data.get("primary_languages", []),
            jd_skills=jd_result.required_skills,
            jd_domains=jd_result.domains
        )
        
        return profile
