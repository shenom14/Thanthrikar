import requests
import json

try:
    res = requests.post('http://127.0.0.1:8000/api/v1/generate-questions', json={
        'name': 'Alice Johnson',
        'role': 'Senior Frontend Engineer',
        'years_experience': 6,
        'linkedin_url': 'https://linkedin.com/in/alicej',
        'github_username': 'alicejs',
        'resume_text': 'a'
    }).json()

    print("Total keys:", len(res['questions'].keys()))
    print("Total questions:", sum(len(v) for v in res['questions'].values()))
    
    for k, v in res['questions'].items():
        print(f"{k}: {len(v)}")
        
except Exception as e:
    print(e)
