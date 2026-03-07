from typing import Dict, Any, List
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser
from config.logger import setup_logger
from config.settings import settings

logger = setup_logger(__name__)

class VerificationResult(BaseModel):
    is_verified: bool = Field(description="True if the resume evidence clearly supports the claim, False if it contradicts or exaggerates it.")
    explanation: str = Field(description="A concise explanation of why the claim is verified or not, based solely on the provided evidence.")
    confidence: int = Field(description="Confidence level in the assessment from 0 to 100.")

class ResumeVerifierAgent:
    """
    The ResumeVerifierAgent compares claims detected during the interview 
    against the retrieved evidence chunks from the RAG database.
    """
    
    def __init__(self, llm_model: str = settings.VERIFIER_MODEL) -> None:
        logger.info(f"Initializing ResumeVerifierAgent with model: {llm_model}")
        self.llm = ChatOllama(model=llm_model, temperature=0.0, base_url=settings.OLLAMA_BASE_URL)
        self.parser = PydanticOutputParser(pydantic_object=VerificationResult)
        
        self.prompt = PromptTemplate(
            template="""You are a strict technical recruiter verifying a candidate's spoken interview claim against their resume.
            
Candidate's spoken claim:
"{claim}"

Resume Evidence Retrieved:
{evidence_text}

Analyze if the resume evidence supports the claim. Be highly critical of exaggerated metrics or expanded responsibilities not present in the resume.
If the evidence is empty or entirely irrelevant, the claim cannot be verified.

{format_instructions}""",
            input_variables=["claim", "evidence_text"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        self.chain = self.prompt | self.llm | self.parser

    async def verify_against_evidence(self, claim: str, evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Determine if the candidate's spoken claim is backed up by their resume text.
        """
        logger.info(f"Verifying claim: '{claim}' against {len(evidence)} evidence chunks.")
        
        evidence_text = "\n---\n".join([chunk.get("text", chunk.get("chunk", "")) for chunk in evidence])
        if not evidence_text.strip():
            logger.warning("No relevant knowledge base evidence found for claim.")
            evidence_text = "No relevant resume evidence found."
            
        try:
            result = await self.chain.ainvoke({
                "claim": claim,
                "evidence_text": evidence_text
            })
            res_dict = result.dict()
            res_dict["claim"] = claim
            logger.debug(f"Verification completed. Result: {res_dict['is_verified']}")
            return res_dict
        except Exception as e:
            logger.error(f"Error verifying claim within agent: {e}")
            return {
                "claim": claim,
                "is_verified": None,
                "explanation": "Agent failed to process verification.",
                "confidence": 0
            }
