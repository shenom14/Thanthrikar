import os
from typing import Dict, Any, Optional
from config.logger import setup_logger

logger = setup_logger(__name__)
# Keep using JSON loader as per the free-tier restriction, but add logging
import json

class CandidateLoader:
    """
    CandidateLoader handles fetching candidate profiles and their resumes.
    It defaults to reading from a local JSON file to avoid requiring paid API keys.
    """

    def __init__(self, use_airtable: bool = False, local_db_path: str = "data/candidates.json"):
        self.use_airtable = use_airtable
        self.local_db_path = local_db_path

    def _ensure_local_db(self) -> None:
        if not os.path.exists(self.local_db_path):
            os.makedirs(os.path.dirname(self.local_db_path), exist_ok=True)
            with open(self.local_db_path, "w") as f:
                json.dump({
                    "rec123": {
                        "name": "Jane Doe",
                        "role": "Senior Backend Engineer",
                        "experience": "8 years",
                        "resume_file": "path/to/downloaded/jane_doe_resume.pdf"
                    }
                }, f)
            logger.info(f"Initialized blank mock candidate database at {self.local_db_path}")

    def fetch_candidate(self, candidate_id: str) -> Dict[str, Any]:
        """
        Fetch a single candidate's record by ID.
        """
        logger.info(f"Fetching candidate {candidate_id}...")
        
        if self.use_airtable:
            # Requires AIRTABLE_API_KEY
            logger.error("Airtable API integration is toggled on but not fully implemented.")
            raise NotImplementedError("Airtable API integration not fully implemented.")
            
        self._ensure_local_db()
        try:
            with open(self.local_db_path, "r") as f:
                candidates = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load candidate DB: {e}")
            candidates = {}
            
        candidate_data = candidates.get(candidate_id)
        if not candidate_data:
            logger.warning(f"Candidate {candidate_id} not found in DB.")
            return {
                "name": "Unknown",
                "role": "Unknown",
                "experience": "Unknown",
                "resume_file": ""
            }
            
        logger.info(f"Successfully loaded candidate data for {candidate_id}")
        return candidate_data

    def fetch_all_candidates(self) -> Dict[str, Any]:
        """
        Fetch all candidate records.
        """
        logger.info("Fetching all candidates...")
        
        if self.use_airtable:
            # Requires AIRTABLE_API_KEY
            logger.error("Airtable API integration is toggled on but not fully implemented.")
            raise NotImplementedError("Airtable API integration not fully implemented.")
            
        self._ensure_local_db()
        try:
            with open(self.local_db_path, "r") as f:
                candidates = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load candidate DB: {e}")
            candidates = {}
            
        return candidates

    def download_resume(self, url: str, destination_path: str) -> bool:
        """
        Helper method to copy or download a resume file.
        """
        logger.debug(f"Stub: Called download_resume for URL {url}")
        return False
