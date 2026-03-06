from typing import List, Dict, Any

class PlannerAgent:
    """
    The Planner Agent listens to the ongoing interview transcript to identify actionable claims
    and route them to the appropriate down-stream validation agents.
    """
    
    def __init__(self, llm_model: str = "gpt-4o"):
        """
        Initialize the Planner agent with an LLM.
        
        Args:
            llm_model (str): Name of the underlying language model used to parse intent.
        """
        # TODO: Initialize LangChain LLM and set up a system prompt/chain.
        self.llm_model = llm_model

    def analyze_transcript(self, transcript_chunk: str) -> List[Dict[str, Any]]:
        """
        Analyze a portion of the transcript for specific verification tasks.
        
        Args:
            transcript_chunk (str): Recent speech from the candidate.
            
        Returns:
            List[Dict[str, Any]]: A list of structured tasks.
            Example: [{"task": "verify_claim", "claim": "Managed 10 engineers"}]
        """
        # TODO: 
        # 1. Provide the transcript chunk to the LLM.
        # 2. Ask the LLM to extract "claims" or "technical statements" into JSON format.
        # 3. Parse the LLM output into python dictionaries.
        
        print(f"[PlannerAgent] Analyzing transcript input...")
        
        # Simulate extraction behavior
        extracted_tasks = []
        if "led" in transcript_chunk.lower() or "team" in transcript_chunk.lower():
            extracted_tasks.append({
                "task": "verify_claim", 
                "claim": transcript_chunk
            })
            
        if "immutable" in transcript_chunk.lower():
            extracted_tasks.append({
                "task": "fact_check", 
                "statement": transcript_chunk
            })
            
        return extracted_tasks
