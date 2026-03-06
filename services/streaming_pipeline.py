from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from config.logger import setup_logger
from config.settings import settings
from backend import models, schemas
from services.interview_service import InterviewService
from rag.retriever import ResumeRetriever
from agents.planner import PlannerAgent
from agents.verifier import ResumeVerifierAgent
from agents.fact_checker import FactCheckerAgent
from agents.question_generator import QuestionGeneratorAgent


logger = setup_logger(__name__)


class StreamingPipeline:
    """
    Orchestrates the real-time interview pipeline:
    transcript chunk -> planner -> RAG/verification/fact-check -> follow-up -> Insight persistence.

    This implementation intentionally keeps audio/STT out of the loop for now and operates
    on text chunks delivered over the WebSocket. It is designed so that a future audio
    layer (Whisper streaming) can feed it with transcript strings.
    """

    def __init__(self) -> None:
        """
        Initialize the streaming pipeline.

        We attempt to enable the full LLM-backed path only if a usable Groq API
        key is configured and the agents can be constructed successfully.
        Otherwise we gracefully fall back to a no-LLM mode that never attempts
        external API calls and simply stores raw transcript insights.
        """
        import os

        self.llm_enabled = False
        self.retriever = ResumeRetriever()

        # Prefer explicit GROQ_API_KEY from env; fall back to settings value.
        groq_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY

        if not groq_key:
            logger.warning(
                "GROQ_API_KEY not set; StreamingPipeline will run in 'no-LLM' mode. "
                "Insights will be stored as raw transcript snippets without verification."
            )
            self.planner = None
            self.verifier = None
            self.fact_checker = None
            self.qgen = None
            return

        try:
            logger.info("Initializing StreamingPipeline with LLM-backed agents.")
            self.planner = PlannerAgent()
            self.verifier = ResumeVerifierAgent()
            self.fact_checker = FactCheckerAgent()
            self.qgen = QuestionGeneratorAgent()
            self.llm_enabled = True
        except Exception as exc:
            logger.error(
                f"Failed to initialize LLM-backed agents; "
                f"running StreamingPipeline in no-LLM mode instead. Error: {exc}"
            )
            self.planner = None
            self.verifier = None
            self.fact_checker = None
            self.qgen = None

    async def handle_transcript_chunk(
        self,
        db: Session,
        session_id: int,
        transcript_chunk: str,
    ) -> List[Dict[str, Any]]:
        """
        Process a single transcript chunk for a given session and return
        WebSocket messages to push back to the client.
        """
        transcript_chunk = transcript_chunk.strip()
        if not transcript_chunk:
            return []

        interview_service = InterviewService(db)
        ws_messages: List[Dict[str, Any]] = []

        # Degraded path when no external LLM is available.
        if not self.llm_enabled:
            insight_data = schemas.InsightCreate(
                session_id=session_id,
                claim_text=transcript_chunk,
                is_verified=None,
                explanation="LLM not configured; storing raw transcript as insight.",
                confidence=None,
                follow_up_suggested=None,
            )
            interview_service.record_insight(session_id, insight_data)
            ws_messages.append(
                {
                    "type": "insight",
                    "message": insight_data.explanation,
                    "follow_up": None,
                }
            )
            return ws_messages

        # Full LLM-backed path.
        try:
            tasks = await self.planner.analyze_transcript(transcript_chunk)
        except Exception as exc:
            logger.error(f"PlannerAgent failed: {exc}")
            return []

        if not tasks:
            return []

        session = (
            db.query(models.InterviewSession)
            .filter(models.InterviewSession.id == session_id)
            .first()
        )
        if not session:
            logger.error(f"Session {session_id} not found while handling transcript.")
            return []

        candidate_id = session.candidate_id

        for task in tasks:
            task_type = task.get("task")
            claim = task.get("claim", transcript_chunk)
            msg: Optional[Dict[str, Any]] = None

            if task_type == "verify_claim":
                msg = await self._handle_verify_claim(
                    interview_service, session_id, candidate_id, claim
                )
            elif task_type == "fact_check":
                msg = await self._handle_fact_check(
                    interview_service, session_id, claim
                )
            else:
                logger.warning(f"Unknown planner task type: {task_type}")

            if msg:
                ws_messages.append(msg)

        return ws_messages

    async def _handle_verify_claim(
        self,
        interview_service: InterviewService,
        session_id: int,
        candidate_id: str,
        claim: str,
    ) -> Optional[Dict[str, Any]]:
        evidence = self.retriever.retrieve_evidence(
            candidate_id=candidate_id, claim=claim, top_k=3
        )

        try:
            verification = await self.verifier.verify_against_evidence(claim, evidence)
        except Exception as exc:
            logger.error(f"ResumeVerifierAgent failed: {exc}")
            return None

        follow_up: Optional[str] = None
        try:
            follow_up = await self.qgen.generate_follow_up(
                claim, verification_result=verification
            )
        except Exception as exc:
            logger.error(f"QuestionGeneratorAgent follow-up failed: {exc}")

        insight_data = schemas.InsightCreate(
            session_id=session_id,
            claim_text=verification.get("claim", claim),
            is_verified=verification.get("is_verified"),
            explanation=verification.get("explanation", ""),
            confidence=verification.get("confidence"),
            follow_up_suggested=follow_up,
        )
        interview_service.record_insight(session_id, insight_data)

        return {
            "type": "insight",
            "message": insight_data.explanation,
            "follow_up": follow_up,
        }

    async def _handle_fact_check(
        self,
        interview_service: InterviewService,
        session_id: int,
        statement: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            fact_result = await self.fact_checker.verify_technical_statement(statement)
        except Exception as exc:
            logger.error(f"FactCheckerAgent failed: {exc}")
            return None

        follow_up: Optional[str] = None
        try:
            follow_up = await self.qgen.generate_follow_up(
                statement, fact_check_result=fact_result
            )
        except Exception as exc:
            logger.error(f"QuestionGeneratorAgent follow-up failed: {exc}")

        # Map fact-check correctness into the existing Insight schema.
        is_correct = fact_result.get("is_correct")

        insight_data = schemas.InsightCreate(
            session_id=session_id,
            claim_text=fact_result.get("statement", statement),
            is_verified=is_correct,
            explanation=fact_result.get("explanation", ""),
            confidence=None,
            follow_up_suggested=follow_up,
        )
        interview_service.record_insight(session_id, insight_data)

        return {
            "type": "insight",
            "message": insight_data.explanation,
            "follow_up": follow_up,
        }

