import requests
import time

BASE_URL = "http://127.0.0.1:8001/api/v1/jd"

def run_benchmark():
    print("--- Running Performance Benchmark ---")
    
    # 1. Test /generate-jd
    print("\nTesting JD Generation (/generate-jd)...")
    start = time.time()
    resp_jd = requests.post(
        f"{BASE_URL}/generate-jd", 
        json={"role": "Backend Engineer"}
    )
    t_jd = time.time() - start
    
    if resp_jd.status_code == 200:
        data = resp_jd.json()
        print(f"âœ… Success! Time: {t_jd:.3f} seconds")
        print(f"Skills extracted: {', '.join(data['required_skills'])}")
    else:
        print(f"âŒ Failed: {resp_jd.text}")

    # 2. Test /generate-questions
    print("\nTesting Question Generation (/generate-questions)...")
    start = time.time()
    resp_q = requests.post(
        f"{BASE_URL}/generate-questions",
        json={
            "role": "Backend Engineer",
            "name": "Alex",
            "years_experience": "5",
            "skill_weights": {"Python": 50, "Docker": 30, "Kubernetes": 20},
            "github_username": "testuser", # Will auto fallback gracefully if slow
            "total_questions": 15
        }
    )
    t_q = time.time() - start
    
    if resp_q.status_code == 200:
        data = resp_q.json()
        print(f"âœ… Success! Time: {t_q:.3f} seconds")
        print(f"Questions generated: {len(data['questions'])}")
    else:
        print(f"âŒ Failed: {resp_q.text}")
        
    print("\n--- Summary ---")
    print(f"Target: JD < 3s, Questions < 5s")
    print(f"Actual: JD = {t_jd:.3f}s, Questions = {t_q:.3f}s")
    print("-----------------------------------")

if __name__ == "__main__":
    run_benchmark()
