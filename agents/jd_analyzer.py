import logging
import asyncio
from config.logger import setup_logger
from backend.schemas_jd import JDAnalysisResult

logger = setup_logger(__name__)

class JDAnalyzerAgent:
    """Provides instant structured JD metadata for common roles without LLM overhead."""

    ANALYSIS_CACHE = {
        "Backend Engineer": JDAnalysisResult(
            role="Backend Engineer",
            required_skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes"],
            domains=["Backend Architecture", "Microservices", "Databases"],
            responsibilities=["Design scalable microservices", "Own CI/CD pipelines", "Optimize DB queries"]
        ),
        "Frontend Engineer": JDAnalysisResult(
            role="Frontend Engineer",
            required_skills=["React", "TypeScript", "CSS", "HTML5", "REST APIs"],
            domains=["UI/UX", "Frontend Architecture", "Web Performance"],
            responsibilities=["Build responsive UIs", "Collaborate with designers", "Maintain component libraries"]
        ),
        "Full Stack Engineer": JDAnalysisResult(
            role="Full Stack Engineer",
            required_skills=["JavaScript", "Node.js", "React", "SQL", "Docker"],
            domains=["Frontend Architecture", "Backend Architecture", "APIs"],
            responsibilities=["End-to-end feature development", "RESTful API design", "Deployment automation"]
        ),
        "DevOps Engineer": JDAnalysisResult(
            role="DevOps Engineer",
            required_skills=["Kubernetes", "Terraform", "AWS", "CI/CD", "Linux"],
            domains=["Cloud Infrastructure", "Automation", "Security"],
            responsibilities=["Manage cloud infra", "Automate deployments", "Ensure system reliability"]
        ),
        "AI Engineer": JDAnalysisResult(
            role="AI Engineer",
            required_skills=["Python", "PyTorch", "LLMs", "MLOps", "FastAPI"],
            domains=["Machine Learning", "Artificial Intelligence", "Model Deployment"],
            responsibilities=["Train and deploy ML models", "Build AI pipelines", "Integrate LLM-powered features"]
        ),
        "Data Engineer": JDAnalysisResult(
            role="Data Engineer",
            required_skills=["Python", "Spark", "SQL", "Airflow", "dbt"],
            domains=["Data Pipelines", "Data Warehousing", "ETL"],
            responsibilities=["Build data pipelines", "Manage data warehouses", "Ensure data quality"]
        ),
        "Data Scientist": JDAnalysisResult(
            role="Data Scientist",
            required_skills=["Python", "Pandas", "Scikit-learn", "SQL", "Statistics"],
            domains=["Data Analysis", "Predictive Modeling", "Machine Learning"],
            responsibilities=["Analyze datasets", "Build predictive models", "Communicate insights"]
        ),
        "Mobile Developer": JDAnalysisResult(
            role="Mobile Developer",
            required_skills=["Swift", "Kotlin", "React Native", "REST APIs", "Git"],
            domains=["Mobile App Development", "UI/UX", "State Management"],
            responsibilities=["Build native mobile applications", "Ensure UI responsiveness", "Manage app store deployments"]
        )
    }

    async def analyze_jd(self, jd_text: str, role: str = "Unknown") -> JDAnalysisResult:
        """Returns instantly analyzed JD metadata."""
        logger.info(f"Fetching cached JD analysis for role: {role}")
        
        result = self.ANALYSIS_CACHE.get(role)
        
        if not result:
            logger.info(f"Role '{role}' not in analysis cache. Using generic fallback.")
            result = JDAnalysisResult(
                role=role,
                required_skills=["Software Engineering", "System Design", "APIs"],
                domains=["Software Development"],
                responsibilities=["Design systems", "Write maintainable code"]
            )
            
        return result
