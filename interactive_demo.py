import asyncio
import time
import logging
import os
import sys
from pprint import pprint

os.environ["GROQ_API_KEY"] = "mock_key_for_testing_demo"

from agents.job_role_jd_generator import JDGeneratorAgent
from agents.candidate_profile_builder import CandidateProfileBuilder
from agents.weighted_question_generator import WeightedQuestionGenerator
from agents.interactive_engine import InteractiveQuestionEngine

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

async def main():
    print("\n=== JD-Driven Interactive Question Engine Pipeline Validation ===\n")
    
    # 1. Inputs
    role = "Backend Engineer"
    difficulty = "mid"
    skill_weights = {
        "Python": 40,
        "Kubernetes": 30,
        "Docker": 20,
        "Distributed Systems": 10
    }
    
    name = "Sheno M"
    experience_years = "3"
    resume_text = "Experienced Python developer with a focus on AI integrations and backend services using Docker."
    linkedin_url = "https://www.linkedin.com/in/sheno-m-0bb925376"
    github_username = "shenom14"
    
    print(f"Role: {role} | Difficulty: {difficulty}")
    print(f"Weights: {skill_weights}\n")
    
    total_start = time.time()
    
    # --- PIPELINE STEP 1: JD Generation ---
    print("1) Generating Auto-JD...")
    jd_gen = JDGeneratorAgent()
    jd_text = await jd_gen.generate_jd_text(role)
    print("   [Done] JD Generated.")
    
    # --- PIPELINE STEP 2 & 3: Profile Building (Extract & Analyze) ---
    print("\n2) Building Candidate Profile (JD Analysis, LinkedIn, GitHub concurrently)...")
    builder = CandidateProfileBuilder()
    profile = await builder.build_profile(
        name=name,
        role=role,
        experience_years=experience_years,
        resume_text=resume_text,
        linkedin_url=linkedin_url,
        github_username=github_username,
        jd_text=jd_text
    )
    
    print(f"   [Done] Cleaned Profile. JD Skills Evaluated: {profile.jd_skills}")
    print(f"   Repos Detected: {[r.get('name') for r in profile.github_repositories]}\n")
    
    # --- PIPELINE STEP 4: JD-Weighted Question Generation ---
    print("3) Generating Weighted Base Questions...")
    q_gen = WeightedQuestionGenerator()
    questions_category = await q_gen.generate_questions(
        profile=profile,
        skill_weights=skill_weights,
        difficulty=difficulty,
        total_questions=10  # Reduced count for speed during demo
    )
    
    pipeline_duration = time.time() - total_start
    print(f"\n[SUCCESS] PIPELINE COMPLETED IN {pipeline_duration:.2f} seconds.")
    if pipeline_duration >= 5.0:
        print("   WARNING: Pipeline exceeded 5s benchmark!")
        
    # --- PIPELINE STEP 5: Interactive Question Engine ---
    print("\n=== INTERACTIVE ENGINE DEMO ===")
    engine = InteractiveQuestionEngine(profile, skill_weights)
    engine.load_questions(questions_category)
    
    # Next Base Question
    current_q = engine.get_current_question()
    print(f"\n[INTERVIEWER] NEXT QUESTION:\nQ: {current_q.question}")
    
    # First Follow Up
    print("\n[CANDIDATE] A: I typically containerize the application first using a Dockerfile, but I sometimes struggle with networking between containers.")
    print("... interviewer presses FOLLOW-UP ...")
    
    follow_up_1 = await engine.generate_follow_up("I typically containerize the application first using a Dockerfile, but I sometimes struggle with networking between containers.")
    print(f"Q: {follow_up_1}")
    
    # Second Follow Up
    print("\n[CANDIDATE] A: I usually just map ports directly to localhost using the -p flag.")
    print("... interviewer presses FOLLOW-UP ...")
    
    follow_up_2 = await engine.generate_follow_up("I usually just map ports directly to localhost using the -p flag.")
    print(f"Q: {follow_up_2}")
    
    # Next Base Question (Resets context)
    print("\n... interviewer presses NEXT QUESTION ...")
    next_q = engine.next_question()
    if next_q:
        print(f"\n[INTERVIEWER] NEXT QUESTION:\nQ: {next_q.question}")
    else:
        print("\n[INTERVIEWER] No more base questions remaining.")
    
    print("\n=== DEMO FINISHED ===")


if __name__ == "__main__":
    asyncio.run(main())
