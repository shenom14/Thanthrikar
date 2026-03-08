import logging
import asyncio
from config.logger import setup_logger

logger = setup_logger(__name__)

class JDGeneratorAgent:
    """Provides instant Job Descriptions for common roles using a static cache instead of LLM generation."""

    # Static Cache to eliminate LLM latency for JD generation
    JD_CACHE = {
        "Backend Engineer":    "Required Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes\nResponsibilities: Design scalable microservices, own CI/CD pipelines, optimize DB queries.",
        "Frontend Engineer":   "Required Skills: React, TypeScript, CSS, HTML5, REST APIs\nResponsibilities: Build responsive UIs, collaborate with designers, maintain component libraries.",
        "Full Stack Engineer": "Required Skills: JavaScript, Node.js, React, SQL, Docker\nResponsibilities: End-to-end feature development, RESTful API design, deployment automation.",
        "DevOps Engineer":     "Required Skills: Kubernetes, Terraform, AWS, CI/CD, Linux\nResponsibilities: Manage cloud infra, automate deployments, ensure system reliability.",
        "AI Engineer":         "Required Skills: Python, PyTorch, LLMs, MLOps, FastAPI\nResponsibilities: Train and deploy ML models, build AI pipelines, integrate LLM-powered features.",
        "Data Engineer":       "Required Skills: Python, Spark, SQL, Airflow, dbt\nResponsibilities: Build data pipelines, manage data warehouses, ensure data quality.",
        "Data Scientist":      "Required Skills: Python, Pandas, Scikit-learn, SQL, Statistics\nResponsibilities: Analyze datasets, build predictive models, communicate insights.",
        "Mobile Developer":    "Required Skills: Swift, Kotlin, React Native, REST APIs, Git\nResponsibilities: Build native mobile applications, ensure UI responsiveness, manage app store deployments.",
    }

    async def generate_jd_text(self, role: str) -> str:
        """Returns a cached JD instantly. Fallback handles unknown roles without LLM overhead."""
        logger.info(f"Fetching cached JD for role: {role}")
        
        # O(1) cache lookup
        result = self.JD_CACHE.get(role)
        
        if not result:
            logger.info(f"Role '{role}' not in cache. Using generic fallback.")
            result = f"Required Skills: Software Engineering, System Design, Communication, Problem Solving\nResponsibilities: Design and implement scalable software systems for the {role} role."
            
        return result
