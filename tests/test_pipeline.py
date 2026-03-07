import time
import json
import logging
from agents.question_generator import generate_candidate_questions, generate_followup_question  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')


def flatten_questions(questions_obj):
    """Flatten nested questions dict to a list for counting."""
    flat = []
    for arr in questions_obj.values():
        flat.extend(arr)
    return flat


def run_tests():
    print("--- Starting Pipeline Validation & Profiling ---\n")
    total_start = time.time()

    test_payload = {
        "name": "Sheno M",
        "role": "Software Engineer",
        "years_experience": 3,
        "resume_text": "Experienced Python developer with a focus on AI integrations and backend services.",
        "linkedin_url": "https://www.linkedin.com/in/sheno-m-0bb925376",
        "github_username": "shenom14"
    }

    print("[Test 1] Full Candidate Profile – 20 questions + follow-up (End-to-End)")
    start_time = time.time()

    try:
        result = generate_candidate_questions(test_payload)
        execution_time = time.time() - start_time
        questions_flat = flatten_questions(result["questions"])
        assert len(questions_flat) == 20, f"Expected 20 questions, got {len(questions_flat)}"
        print(f"Success! Generated {len(questions_flat)} questions in {execution_time:.2f} seconds.")

        if execution_time > 5.0:
            print("WARNING: Execution time exceeded 5 seconds!")

        print("\n[Follow-up simulation]")
        base_q = "Explain Docker."
        follow_up = generate_followup_question(base_q, "")
        print(f"  Base: {base_q}")
        print(f"  Follow-up: {follow_up}")
        follow_up2 = generate_followup_question(follow_up, base_q + " " + follow_up)
        print(f"  Follow-up 2: {follow_up2}")
        print("  Interaction logic: base -> follow-up -> follow-up2 (context concatenated).")

        print("\nOutput snippet (first 2 categories):")
        out_snippet = {k: v for k, v in result["questions"].items() if k in ("technical", "system_design")}
        print(json.dumps(out_snippet, indent=2))

    except AssertionError as e:
        print(f"FAILED: {e}")
    except Exception as e:
        print(f"FAILED: Pipeline crashed: {e}")

    print("\n--------------------------------------------------\n")

    print("[Test 2] Minimal Candidate Profile (Missing GitHub/LinkedIn) - Resilience Test")
    minimal_payload = {
        "name": "Jane Doe",
        "role": "Frontend Engineer",
        "years_experience": 2,
        "resume_text": "React developer.",
        "linkedin_url": "",
        "github_username": ""
    }

    start_time = time.time()
    try:
        result2 = generate_candidate_questions(minimal_payload)
        execution_time = time.time() - start_time
        questions_flat2 = flatten_questions(result2["questions"])
        assert len(questions_flat2) == 20, f"Expected 20 questions, got {len(questions_flat2)}"
        print(f"Success! Generated {len(questions_flat2)} questions in {execution_time:.2f} seconds.")
        print("System correctly bypassed missing auxiliary data sources.")
    except Exception as e:
        print(f"FAILED: System crashed on missing data: {e}")

    total_elapsed = time.time() - total_start
    print(f"\n--- Total test run: {total_elapsed:.2f}s (must be < 5s) ---")
    if total_elapsed >= 5.0:
        print("WARNING: Total execution exceeded 5 second boundary.")


if __name__ == "__main__":
    run_tests()
