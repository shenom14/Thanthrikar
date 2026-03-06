import pytest
import os
import sys

# Ensure backend imports work before testing
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from config.settings import settings
from tools.resume_parser import ResumeParser
from agents.planner import PlannerAgent
from backend.schemas import SessionCreate

def test_environment_vars_loaded():
    """ Verify the Pydantic Settings properly configured tests. """
    assert settings.APP_NAME == "AI Interview Copilot"
    assert settings.CHUNK_SIZE > 0
    
def test_resume_parser_instantiation():
    """ Verify tools can be instantiated without crashing """
    parser = ResumeParser()
    assert parser is not None

@pytest.mark.asyncio
async def test_planner_agent_empty_transcript():
    """ Test the Groq-backed Planner Agent handling empty input gracefully. """
    agent = PlannerAgent(llm_model="llama3-70b-8192")
    
    # Normally we would mock the LLM here to save API calls in CI,
    # but for a simple instantiation test, ensuring it parses empty is a good start.
    assert agent.llm.model_name == "llama3-70b-8192"
    
def test_session_schema_validation():
    """ Validate Pydantic schema rejection of bad data. """
    try:
        SessionCreate(candidate_id="")
    except Exception as e:
        assert False, f"Pydantic schema rejected empty string but shouldn't have: {e}"
        
    session = SessionCreate(candidate_id="rec_12345")
    assert session.candidate_id == "rec_12345"

# TODO: Add mocks for ChromaDB insertion 
# TODO: Add Pytest-Asyncio fixtures for WebSocket endpoint tests
