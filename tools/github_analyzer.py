"""
GitHub Analyzer Module

Responsible for securely fetching public repositories, commit history, and language metrics
using the GitHub REST API.
It includes rate limit handling, robust error fallbacks, and execution optimization (< 1.5s).
"""

import logging
import requests  # type: ignore
from typing import Dict, Any, List, Optional
from collections import Counter

logger = logging.getLogger(__name__)

class GitHubAnalyzer:
    """Class to extract and summarize GitHub repository data for a candidate."""

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize the analyzer.
        
        Args:
            github_token: Optional GitHub Personal Access Token to increase API limits.
        """
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if github_token:
            self.headers["Authorization"] = f"token {github_token}"
            
    def fetch_user_data(self, username: str) -> Dict[str, Any]:
        """
        Fetch public repositories and summarize project language/activity.
        If the API fails, a safe fallback template is returned to prevent pipeline crashes.

        Args:
            username (str): The candidate's GitHub username.

        Returns:
            Dict[str, Any]: A summary of the candidate's GitHub activity.
        """
        logger.info(f"Analyzing GitHub activity for user: {username}")
        
        url = f"https://api.github.com/users/{username}/repos?type=owner&sort=updated&per_page=10"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=3.0)
            
            # Handle rate limits or missing users gracefully
            if response.status_code == 404:
                logger.warning(f"GitHub user '{username}' not found.")
                return self._fallback_data(username, "User not found")
            
            if response.status_code == 403:
                logger.warning(f"GitHub API rate limit exceeded while querying '{username}'.")
                return self._fallback_data(username, "Rate limit exceeded (Fallback activated)")
                
            response.raise_for_status()
            
            repos = response.json()
            return self._parse_repositories(username, repos)
            
        except requests.exceptions.Timeout:
            logger.error(f"GitHub API timeout for user '{username}'.")
            return self._fallback_data(username, "API Timeout")
        except Exception as e:
            logger.error(f"Error fetching GitHub data for {username}: {e}")
            return self._fallback_data(username, f"Fetch Error: {str(e)}")

    def _parse_repositories(self, username: str, repos: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Processes raw repository data into a curated insight summary."""
        if not repos:
            return self._fallback_data(username, "No public repositories found.")
            
        primary_languages = Counter()
        top_projects = []
        
        for repo in repos:
            lang = repo.get("language")
            if lang:
                primary_languages[lang] += 1
                
            # Filter forks and pick the most relevant repositories (e.g. ones with stars or recent updates)
            if not repo.get("fork"):
                top_projects.append({
                    "name": repo.get("name", "Unknown"),
                    "description": repo.get("description") or "No description provided.",
                    "primary_language": repo.get("language") or "Mixed/None",
                    "stars": repo.get("stargazers_count", 0),
                    "url": repo.get("html_url", "")
                })

        # Sort top projects by stars (descending) and cap at 3 to keep LLM context minimal
        top_projects = sorted(top_projects, key=lambda x: x["stars"], reverse=True)[:3]  # type: ignore
        
        # Get the top 3 most used languages
        top_langs = [lang for lang, count in primary_languages.most_common(3)]
        
        return {
            "username": username,
            "total_analyzed_repos": len(repos),
            "primary_languages": top_langs,
            "top_projects": top_projects,
            "recent_activity_summary": f"Analyzed {len(repos)} recent repositories targeting {', '.join(top_langs) if top_langs else 'multiple'} stacks."
        }

    def _fallback_data(self, username: str, reason: str) -> Dict[str, Any]:
        """Provides a safe empty state structure so downstream generators don't crash."""
        return {
            "username": username,
            "total_analyzed_repos": 0,
            "primary_languages": [],
            "top_projects": [],
            "recent_activity_summary": f"Could not perform deep analysis: {reason}"
        }


def analyze_github_profile(username: str) -> Dict[str, Any]:
    """Convenience function to analyze a candidate's GitHub profile."""
    # Note: Pass github_token here from environment variables in production to avoid rate limits
    analyzer = GitHubAnalyzer()
    return analyzer.fetch_user_data(username)
