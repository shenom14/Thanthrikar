"""
LinkedIn Scraper Module

Responsible for fetching candidate profile data from LinkedIn.
Directly scraping LinkedIn requires complex browser automation (Puppeteer/Selenium) and often 
triggers Captchas limiting speed. For this high-performance hackathon demo (sub-5s pipeline),
we will simulate a robust API integration (like Proxycurl/Nubela) that parses the public profile URL
into a standardized structured format, with heavy error boundaries and fallbacks.
"""

import logging
import time
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class LinkedInScraper:
    """Class to extract and normalize candidate work experience and skills from LinkedIn."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the scraper.
        
        Args:
            api_key: Optional API key for a third-party LinkedIn scraping service.
        """
        self.api_key = api_key

    def fetch_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Fetch candidate profile data from LinkedIn URL.
        Includes safety nets so a broken link does not crash the pipeline.

        Args:
            profile_url (str): The candidate's LinkedIn profile URL.

        Returns:
            Dict[str, Any]: A structured dictionary containing normalized profile data.
        """
        if not profile_url or "linkedin.com/in/" not in profile_url.lower():
            logger.warning("Invalid or missing LinkedIn URL provided.")
            return self._fallback_data(profile_url, "Invalid URL format")
            
        logger.info(f"Analyzing LinkedIn profile: {profile_url}")
        
        try:
            # Simulate a network call to a paid extraction API (e.g., Proxycurl)
            # In < 0.2 seconds.
            time.sleep(0.15)
            return self._mock_proxycurl_extraction(profile_url)
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn data for {profile_url}: {e}")
            return self._fallback_data(profile_url, f"API Exception: {str(e)}")
            
    def _mock_proxycurl_extraction(self, profile_url: str) -> Dict[str, Any]:
        """
        Provides simulated structured data as if extracted by a commercial API.
        Extracts the presumed username from the URL to make it slightly dynamic.
        """
        # Extract name guess from URL (e.g. linkedin.com/in/john-doe-123 -> John Doe)
        match = re.search(r'in/([^/?]+)', profile_url)
        name_slug = match.group(1).replace('-', ' ') if match else "Unknown Candidate"
        
        return {
            "source_url": profile_url,
            "headline": f"Software Professional | {name_slug.title()}",
            "summary": "Experienced engineer with a focus on scalable systems and clean architecture.",
            "work_experience": [
                {
                    "company": "Current Tech Company",
                    "role": "Senior Engineer",
                    "duration": "2021 - Present",
                    "description": "Architecting backend services and optimizing cloud infrastructure."
                },
                {
                    "company": "Previous Agency",
                    "role": "Software Developer",
                    "duration": "2018 - 2021",
                    "description": "Developed and maintained full-stack web applications."
                }
            ],
            "skills": ["Software Development", "System Architecture", "Agile Methodologies"],
            "education": ["B.S. Computer Science"]
        }

    def _fallback_data(self, profile_url: str, reason: str) -> Dict[str, Any]:
        """Safe fallback to prevent LLM pipeline failures."""
        return {
            "source_url": profile_url,
            "headline": "Profile Unavailable",
            "summary": f"Could not extract detailed LinkedIn profile: {reason}",
            "work_experience": [],
            "skills": [],
            "education": []
        }


def extract_linkedin_data(profile_url: str) -> Dict[str, Any]:
    """Convenience function to fetch LinkedIn data."""
    scraper = LinkedInScraper()
    return scraper.fetch_profile(profile_url)
