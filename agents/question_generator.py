from typing import List, Dict, Any, Optional

class QuestionGeneratorAgent:
    """
    The QuestionGeneratorAgent produces both pre-interview questions tailored to the candidate's resume,
    as well as real-time follow-up questions during the interview.
    """
    
    def __init__(self, llm_model: str = "gpt-4o"):
        """
        Initialize the AI agent for generating interview questions.
        
        Args:
            llm_model (str): The language model to use.
        """
        # TODO: Configure prompt templates for two distinct modes: base generation and follow-up generation.
        self.llm_model = llm_model

    def generate_initial_questions(self, role: str, experience: str, resume_summary: str, count: int = 5) -> List[str]:
        """
        Generate default questions before the interview starts based on candidate profile.
        
        Args:
            role (str): Job role (e.g., 'Backend Engineer').
            experience (str): Candidate's experience level (e.g., '5 years').
            resume_summary (str): Summarized text from resume_parser.
            count (int): Number of questions to return.
            
        Returns:
            List[str]: List of interview questions.
        """
        # TODO: Create a prompt using the inputs and request a structured list of questions.
        
        print(f"[QuestionGeneratorAgent] Generating initial questions for {role}...")
        
        return [
            "Explain the architecture of a system you built.",
            "What scaling challenges did you face?",
            "How did you ensure system reliability?",
            "Can you discuss a time you resolved a complex backend bug?",
            "How do you handle migrations with zero downtime?"
        ]

    def generate_follow_up(self,
                           claim: str, 
                           verification_result: Optional[Dict[str, Any]] = None,
                           fact_check_result: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Generate an intelligent follow-up question if an irregularity, vagueness, or error is detected.
        
        Args:
            claim (str): What the candidate said.
            verification_result (Dict, optional): Result from the ResumeVerifierAgent.
            fact_check_result (Dict, optional): Result from the FactCheckerAgent.
            
        Returns:
            Optional[str]: A suggested follow-up question, or None if no follow-up is necessary.
        """
        # TODO:
        # 1. Provide the LLM with the context of what the candidate said and what the system found.
        # 2. Instruct the LLM to phrase a polite but probing question for the interviewer to ask.
        
        print(f"[QuestionGeneratorAgent] Generating follow up for claim: '{claim}'")
        
        if verification_result and not verification_result.get("is_verified", True):
            return "Could you clarify the size of the team you managed and your specific leadership responsibilities?"
            
        if fact_check_result and not fact_check_result.get("is_correct", True):
            return "You mentioned Python lists are immutable. Could you elaborate on what you mean by that, or compare it to tuples?"
            
        return None
