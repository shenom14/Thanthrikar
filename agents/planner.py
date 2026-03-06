from typing import List, Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from config.logger import setup_logger
from config.settings import settings

logger = setup_logger(__name__)

class ClaimTask(BaseModel):
    task: str = Field(description="The type of task: 'verify_claim' if it's a resume claim, or 'fact_check' if it's a general technical statement.")
    claim: str = Field(description="The exact text of the claim or statement.")

class PlannerTasks(BaseModel):
    tasks: List[ClaimTask] = Field(description="List of detected claims or technical statements.")

class PlannerAgent:
    """
    The Planner Agent listens to the ongoing interview transcript to identify actionable claims
    and route them to the appropriate down-stream validation agents.
    """
    
    def __init__(self, llm_model: str = settings.PLANNER_MODEL) -> None:
        logger.info(f"Initializing PlannerAgent with model: {llm_model}")
        self.llm = ChatGroq(model_name=llm_model, temperature=0.0)
        self.parser = PydanticOutputParser(pydantic_object=PlannerTasks)
        
        self.prompt = PromptTemplate(
            template="""You are an AI assistant analyzing an interview transcript in real-time.
Your goal is to extract any testable claims or technical statements made by the candidate.

If the candidate describes their past experience, projects, metrics, or responsibilities, classify it as 'verify_claim'.
If the candidate makes a general technical assertion (e.g., 'Python lists are immutable'), classify it as 'fact_check'.
Only extract significant, testable statements. If there are none, return an empty list.

{format_instructions}

Transcript snippet:
"{transcript_chunk}"
""",
            input_variables=["transcript_chunk"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )
        
        self.chain = self.prompt | self.llm | self.parser

    async def analyze_transcript(self, transcript_chunk: str) -> List[Dict[str, Any]]:
        """
        Analyze a portion of the transcript for specific verification tasks.
        """
        logger.debug(f"Analyzing transcript chunk length {len(transcript_chunk)}")
        try:
            result = await self.chain.ainvoke({"transcript_chunk": transcript_chunk})
            extracted = [t.dict() for t in result.tasks]
            logger.info(f"Extracted {len(extracted)} actionable distinct claims.")
            return extracted
        except Exception as e:
            logger.error(f"Error parsing PlannerAgent response: {e}")
            return []
