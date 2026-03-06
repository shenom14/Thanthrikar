from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from config.logger import setup_logger
from config.settings import settings

logger = setup_logger(__name__)

class FactCheckResult(BaseModel):
    is_correct: bool = Field(description="True if the candidate's statement is technically accurate, False otherwise.")
    explanation: str = Field(description="A brief, polite explanation of the correct technical fact to help the interviewer.")

class FactCheckerAgent:
    """
    The FactCheckerAgent identifies and verifies technical statements made by the candidate.
    It does not rely on the resume; instead, it relies on general LLM knowledge.
    """
    
    def __init__(self, llm_model: str = settings.FACT_CHECKER_MODEL) -> None:
        logger.info(f"Initializing FactCheckerAgent with model: {llm_model}")
        self.llm = ChatGroq(model_name=llm_model, temperature=0.0)
        self.parser = PydanticOutputParser(pydantic_object=FactCheckResult)
        
        self.prompt = PromptTemplate(
            template="""You are a senior staff engineer fact-checking technical assertions made by a candidate in an interview.
            
Candidate's Statement:
"{statement}"

Determine if this statement is fundamentally correct. If they are slightly off on trivia but conceptually right, lean towards correct. 
If they state something objectively wrong (e.g. 'Python lists are immutable'), mark it incorrect and provide the correct understanding.

{format_instructions}""",
            input_variables=["statement"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        self.chain = self.prompt | self.llm | self.parser

    async def verify_technical_statement(self, statement: str) -> Dict[str, Any]:
        """
        Check the correctness of a technical point made during an interview.
        """
        logger.info(f"Evaluating technical statement: '{statement}'")
        try:
            result = await self.chain.ainvoke({"statement": statement})
            res_dict = result.dict()
            res_dict["statement"] = statement
            logger.debug(f"Fact check result: {res_dict['is_correct']}")
            return res_dict
        except Exception as e:
            logger.error(f"Error evaluating fact: {e}")
            return {
                "statement": statement,
                "is_correct": None,
                "explanation": "Failed to evaluate fact."
            }
