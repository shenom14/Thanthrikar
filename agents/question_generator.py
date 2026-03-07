from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from config.logger import setup_logger
from config.settings import settings

logger = setup_logger(__name__)

class FollowUpResult(BaseModel):
    question: Optional[str] = Field(description="The suggested follow-up question, or null if no question is necessary.")

class QuestionGeneratorAgent:
    """
    The QuestionGeneratorAgent produces both pre-interview questions tailored to the candidate's resume,
    as well as real-time follow-up questions during the interview.
    """
    
    def __init__(self, llm_model: str = settings.QGEN_MODEL) -> None:
        logger.info(f"Initializing QuestionGeneratorAgent with model: {llm_model}")
        self.llm = ChatGroq(model_name=llm_model, temperature=0.7)
        self.parser = PydanticOutputParser(pydantic_object=FollowUpResult)
        
        self.initial_prompt = PromptTemplate(
            template="""You are preparing questions for an interview for a {role} position.
The candidate has {experience} of experience.

Resume Overview:
{resume_summary}

Generate EXACTLY {count} specific, deeply technical interview questions targeting their resume experience.
Output them as a simple numbered list.""",
            input_variables=["role", "experience", "resume_summary", "count"]
        )
        self.initial_chain = self.initial_prompt | self.llm
        
        self.follow_up_prompt = PromptTemplate(
            template="""You are an AI assistant helping an interviewer inside a live interview.
The candidate just made this statement: "{claim}"

Based on background verification, we found the following AI Insight:
"{insight_context}"

If this insight suggests an exaggeration, falsehood, or point of confusion, generate a polite but probing follow-up question to dig deeper.
If the insight confirms everything is perfectly fine, you should STILL generate a natural, engaging follow-up question to keep the conversation flowing and show interest. Only return null if the topic is completely exhausted.

{format_instructions}""",
            input_variables=["claim", "insight_context"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        self.follow_up_chain = self.follow_up_prompt | ChatGroq(model_name=llm_model, temperature=0.5) | self.parser

    async def generate_initial_questions(self, role: str, experience: str, resume_summary: str, count: int = 5) -> List[str]:
        logger.info(f"Generating {count} initial questions for {role}...")
        try:
            result = await self.initial_chain.ainvoke({
                "role": role, 
                "experience": experience, 
                "resume_summary": resume_summary, 
                "count": count
            })
            lines = result.content.strip().split('\n')
            extracted = [line.strip() for line in lines if line.strip()]
            logger.debug(f"Generated {len(extracted)} initial questions.")
            return extracted
        except Exception as e:
            logger.error(f"Error generating initial questions: {e}")
            return []

    async def generate_follow_up(self,
                           claim: str, 
                           verification_result: Optional[Dict[str, Any]] = None,
                           fact_check_result: Optional[Dict[str, Any]] = None) -> Optional[str]:
        logger.info(f"Attempting to generate follow up for claim: '{claim}'")
        
        insight_context = ""
        if verification_result and not verification_result.get("is_verified", True):
            insight_context = f"Resume verification failed: {verification_result.get('explanation')}"
        elif fact_check_result and not fact_check_result.get("is_correct", True):
            insight_context = f"Fact check failed: {fact_check_result.get('explanation')}"
        else:
            insight_context = "All claims appear verified and correct. Suggest a natural follow-up question to keep the conversation engaging."
            logger.debug("Positive insight detected. Requesting proactive follow-up.")
            
        try:
            result = await self.follow_up_chain.ainvoke({
                "claim": claim,
                "insight_context": insight_context
            })
            logger.debug(f"Generated follow-up: {result.question}")
            return result.question
        except Exception as e:
            logger.error(f"Error generating follow up question: {e}")
            return None
