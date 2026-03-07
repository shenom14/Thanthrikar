import json
import time
import logging
from agents.legacy_question_generator import generate_candidate_questions  # type: ignore

logging.basicConfig(level=logging.INFO)

def run_validation():
    print("--- Starting Pipeline Validation ---")
    
    # 1. Full Candidate Profile (Happy Path)
    candidate_full = {
        "name": "John Smith",
        "role": "Backend Engineer",
        "years_experience": 5,
        "resume_text": "Experienced in Python, Docker, Kubernetes, and Microservices. Led a team of 4 engineers.",
        "linkedin_url": "https://linkedin.com/in/johnsmith",
        "github_username": "johnsmith"
    }

    print("\n[Test 1] Full Candidate Profile Integration")
    start_time = time.time()
    try:
        result_full = generate_candidate_questions(candidate_full)
        duration = time.time() - start_time
        print(f"Success! Generated questions in {duration:.2f} seconds.")
        print("Output snippet:")
        print(json.dumps(result_full, indent=2)[:500] + "...\n}")  # type: ignore
    except Exception as e:
        print(f"Failed Test 1: {e}")

    # 2. Candidate with Missing Data (Robustness Check)
    candidate_minimal = {
        "name": "Jane Doe",
        "role": "Frontend Engineer",
        "years_experience": 2,
        "resume_text": "Proficient in React, JavaScript, and CSS.",
        # Purposely missing linkedin and github
    }

    print("\n[Test 2] Minimal Candidate Profile (Missing GitHub/LinkedIn)")
    start_time = time.time()
    try:
        result_min = generate_candidate_questions(candidate_minimal)
        duration = time.time() - start_time
        print(f"Success! Generated questions in {duration:.2f} seconds.")
        print("Output snippet:")
        print(json.dumps(result_min, indent=2)[:500] + "...\n}")  # type: ignore
    except Exception as e:
        print(f"Failed Test 2: {e}")

if __name__ == "__main__":
    run_validation()
