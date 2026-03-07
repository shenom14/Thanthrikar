import logging
import asyncio
import requests
from config.logger import setup_logger

logger = setup_logger(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


def _call_ollama_sync(prompt: str) -> str:
    """Blocking HTTP call to local Ollama."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 1024}
            },
            timeout=90
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logger.warning(f"Ollama JD generation failed: {e}")
        return ""


class JDGeneratorAgent:
    """Generates a realistic Job Description for a given role using Ollama."""

    FALLBACK = {
        "Backend Engineer":    "Required Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes\nResponsibilities: Design scalable microservices, own CI/CD pipelines, optimize DB queries.",
        "Frontend Engineer":   "Required Skills: React, TypeScript, CSS, REST APIs, Testing\nResponsibilities: Build responsive UIs, collaborate with designers, maintain component libraries.",
        "Full Stack Engineer": "Required Skills: JavaScript, Node.js, React, SQL, Docker\nResponsibilities: End-to-end feature development, RESTful API design, deployment automation.",
        "DevOps Engineer":     "Required Skills: Kubernetes, Terraform, AWS, CI/CD, Linux\nResponsibilities: Manage cloud infra, automate deployments, ensure system reliability.",
        "AI Engineer":         "Required Skills: Python, PyTorch, LLMs, MLOps, FastAPI\nResponsibilities: Train and deploy ML models, build AI pipelines, integrate LLM-powered features.",
        "Data Engineer":       "Required Skills: Python, Spark, SQL, Airflow, dbt\nResponsibilities: Build data pipelines, manage data warehouses, ensure data quality.",
    }

    async def generate_jd_text(self, role: str) -> str:
        logger.info(f"Generating JD for role: {role}")
        prompt = f"""You are an expert technical recruiter.
Generate a realistic and detailed Job Description for: {role}

Include:
- Required Technical Skills (minimum 6 specific skills/technologies)
- Technology Stack
- Technical Domains
- Key Responsibilities (minimum 5)

Be specific and technical. Output only the job description text, no preamble or headers."""

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _call_ollama_sync, prompt)

        if not result:
            logger.warning("Ollama unavailable — using built-in JD fallback.")
            result = self.FALLBACK.get(role, f"Required Skills: Python, Docker, System Design\nResponsibilities: Build scalable systems for {role}.")

        return result
