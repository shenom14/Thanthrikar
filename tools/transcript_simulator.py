"""
Transcript Simulator — Tests the RAG Pipeline Without Live Speech.

Feeds predefined interview transcript segments sequentially through the
StreamingPipeline, exactly as if they were coming from live transcription.

Each segment triggers:
  - claim detection (keyword trigger / planner)
  - technology extraction (logged)
  - RAG retrieval (logged with results)
  - follow-up question generation (logged)

At the end, generates a full interview summary report.

Usage:
  python tools/transcript_simulator.py
"""

import os
import sys
import asyncio
import time
import json
from datetime import datetime

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Force UTF-8 stdout on Windows
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from config.logger import setup_logger
from backend.database import SessionLocal, engine, Base
from backend import models
from services.streaming_pipeline import StreamingPipeline

logger = setup_logger("transcript_simulator")

# ======================================================================
# Simulated Interview Transcript Segments
# ======================================================================

SEGMENTS = [
    {
        "id": 1,
        "speaker": "Candidate (Arun)",
        "text": (
            "Hi, my name is Arun. I recently graduated in Computer Science. "
            "My main interests are machine learning and backend systems. "
            "Recently I built a distributed machine learning pipeline using Kubernetes."
        ),
    },
    {
        "id": 2,
        "speaker": "Candidate (Arun)",
        "text": (
            "The pipeline had three components. Data ingestion using Python and Kafka. "
            "Distributed training using Spark. Deployment using FastAPI."
        ),
    },
    {
        "id": 3,
        "speaker": "Candidate (Arun)",
        "text": (
            "I optimized the model training using GPU acceleration which reduced "
            "training time by 40 percent."
        ),
    },
    {
        "id": 4,
        "speaker": "Candidate (Arun)",
        "text": (
            "I also built a recommendation system using collaborative filtering "
            "and matrix factorization."
        ),
    },
    {
        "id": 5,
        "speaker": "Candidate (Arun)",
        "text": "That summarizes my projects.",
    },
]

# ======================================================================
# Technology Extraction Helper
# ======================================================================

KNOWN_TECHNOLOGIES = {
    "python", "java", "javascript", "typescript", "c++", "go", "rust",
    "kubernetes", "docker", "kafka", "spark", "hadoop", "airflow",
    "fastapi", "django", "flask", "react", "angular", "vue",
    "aws", "gcp", "azure", "terraform", "ansible",
    "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "machine learning", "deep learning", "neural network", "tensorflow",
    "pytorch", "scikit-learn", "gpu", "gpu acceleration",
    "collaborative filtering", "matrix factorization",
    "microservices", "rest api", "graphql",
}

def extract_technologies(text: str) -> list[str]:
    """Extract known technologies mentioned in the text."""
    lower = text.lower()
    found = []
    for tech in sorted(KNOWN_TECHNOLOGIES, key=len, reverse=True):
        if tech in lower:
            found.append(tech)
    return list(dict.fromkeys(found))  # deduplicate preserving order


# ======================================================================
# Main Simulation
# ======================================================================

async def run_simulation():
    """Execute the full transcript simulation."""
    
    print("\n" + "=" * 80)
    print("  TRANSCRIPT SIMULATOR -- RAG Pipeline Test")
    print("=" * 80)
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Segments to process: {len(SEGMENTS)}")
    print("=" * 80 + "\n")

    # --- 1. Initialize Database ---
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # --- 2. Create a test candidate and session ---
    CANDIDATE_ID = "sim_arun_001"
    candidate = db.query(models.Candidate).filter(models.Candidate.id == CANDIDATE_ID).first()
    if not candidate:
        candidate = models.Candidate(
            id=CANDIDATE_ID,
            name="Arun (Simulated)",
            role="ML Engineer",
            experience="Fresher / Recent Graduate",
        )
        db.add(candidate)
        db.commit()
        logger.info(f"Created simulated candidate: {CANDIDATE_ID}")

    session = models.InterviewSession(
        candidate_id=CANDIDATE_ID,
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session_id = session.id
    logger.info(f"Created simulated interview session: {session_id}")

    # --- 3. Initialize the Streaming Pipeline ---
    print("\n⏳ Initializing StreamingPipeline (loading LLM agents)...\n")
    pipeline = StreamingPipeline()
    await pipeline._init_components()

    if pipeline.llm_enabled:
        print("[OK] Pipeline initialized with LLM agents.\n")
    else:
        print("[WARN] Pipeline running in no-LLM mode. Insights will be raw transcript snippets.\n")

    # --- 4. Process each segment ---
    all_results = []
    all_technologies = []
    total_start = time.time()

    for segment in SEGMENTS:
        seg_id = segment["id"]
        speaker = segment["speaker"]
        text = segment["text"]

        print("\n" + "-" * 80)
        print(f"📝 SEGMENT {seg_id} — {speaker}")
        print("-" * 80)
        print(f"   \"{text}\"")
        print()

        # Extract technologies
        techs = extract_technologies(text)
        all_technologies.extend(techs)
        if techs:
            print(f"   [TECH] Technologies Detected: {', '.join(techs)}")
        else:
            print(f"   [TECH] Technologies Detected: (none)")

        # Feed into the pipeline
        seg_start = time.time()
        try:
            ws_messages = await pipeline.handle_transcript_chunk(
                db=db,
                session_id=session_id,
                transcript_chunk=text,
            )
            seg_elapsed = time.time() - seg_start

            print(f"   [TIME]  Processing Time: {seg_elapsed:.2f}s")
            print(f"   [MSGS]  Pipeline Messages: {len(ws_messages)}")

            for i, msg in enumerate(ws_messages, 1):
                msg_type = msg.get("type", "unknown")
                explanation = msg.get("message", "")
                follow_up = msg.get("follow_up", None)

                print(f"\n   --- Result {i} (type: {msg_type}) ---")
                print(f"   [INSIGHT] {explanation[:200]}{'...' if len(explanation) > 200 else ''}")
                if follow_up:
                    print(f"   [FOLLOW-UP] {follow_up}")
                else:
                    print(f"   [FOLLOW-UP] (none generated)")

            all_results.append({
                "segment_id": seg_id,
                "text": text,
                "technologies": techs,
                "elapsed_seconds": round(seg_elapsed, 2),
                "messages": ws_messages,
            })

        except Exception as e:
            seg_elapsed = time.time() - seg_start
            print(f"   [ERROR] ERROR processing segment: {e}")
            logger.error(f"Segment {seg_id} failed: {e}", exc_info=True)
            all_results.append({
                "segment_id": seg_id,
                "text": text,
                "technologies": techs,
                "elapsed_seconds": round(seg_elapsed, 2),
                "messages": [],
                "error": str(e),
            })

    total_elapsed = time.time() - total_start

    # --- 5. Check RAG retrieval logs ---
    print("\n\n" + "=" * 80)
    print("  RAG RETRIEVAL VERIFICATION")
    print("=" * 80)
    
    # Query insights from DB to confirm they were persisted
    insights = db.query(models.Insight).filter(models.Insight.session_id == session_id).all()
    print(f"\n   Total Insights Persisted in DB: {len(insights)}")
    for ins in insights:
        print(f"   [ID {ins.id}] Claim: \"{ins.claim_text[:80]}...\"")
        print(f"            Verified: {ins.is_verified} | Confidence: {ins.confidence}")
        print(f"            Follow-Up: {ins.follow_up_suggested or '(none)'}")
        print()

    # --- 6. Generate Summary Report ---
    unique_techs = list(dict.fromkeys(all_technologies))

    print("\n" + "=" * 80)
    print("  FULL INTERVIEW SIMULATION SUMMARY REPORT")
    print("=" * 80)
    print(f"\n   Candidate:          Arun (Simulated)")
    print(f"   Role:               ML Engineer")
    print(f"   Session ID:         {session_id}")
    print(f"   Segments Processed: {len(SEGMENTS)}")
    print(f"   Total Processing:   {total_elapsed:.2f}s")
    print(f"   Avg per Segment:    {total_elapsed / len(SEGMENTS):.2f}s")
    print(f"\n   Technologies Found: {', '.join(unique_techs) if unique_techs else '(none)'}")
    
    total_insights = sum(len(r.get("messages", [])) for r in all_results)
    total_followups = sum(
        1 for r in all_results 
        for m in r.get("messages", []) 
        if m.get("follow_up")
    )
    total_errors = sum(1 for r in all_results if "error" in r)
    
    print(f"\n   Total Insights:     {total_insights}")
    print(f"   Follow-Up Q's:     {total_followups}")
    print(f"   Errors:            {total_errors}")
    
    print(f"\n   DB Insights Saved:  {len(insights)}")
    print(f"   Pipeline LLM:      {'Enabled' if pipeline.llm_enabled else 'Disabled (no-LLM mode)'}")

    # Per-segment summary table
    print(f"\n   {'Seg':>3} | {'Time':>6} | {'Msgs':>4} | Technologies")
    print(f"   {'---':>3} | {'------':>6} | {'----':>4} | {'---' * 10}")
    for r in all_results:
        t = ', '.join(r['technologies']) if r['technologies'] else '—'
        print(f"   {r['segment_id']:>3} | {r['elapsed_seconds']:>5.2f}s | {len(r['messages']):>4} | {t}")

    print("\n" + "=" * 80)
    print("  SIMULATION COMPLETE")
    print("=" * 80 + "\n")

    # --- 7. Write report to file ---
    report_path = os.path.join(os.path.dirname(__file__), '..', 'simulation_report.json')
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "candidate": "Arun (Simulated)",
        "session_id": session_id,
        "total_segments": len(SEGMENTS),
        "total_processing_seconds": round(total_elapsed, 2),
        "technologies_detected": unique_techs,
        "total_insights": total_insights,
        "total_follow_ups": total_followups,
        "total_errors": total_errors,
        "db_insights_count": len(insights),
        "llm_enabled": pipeline.llm_enabled,
        "segments": [
            {
                "id": r["segment_id"],
                "text": r["text"],
                "technologies": r["technologies"],
                "elapsed_seconds": r["elapsed_seconds"],
                "insight_count": len(r.get("messages", [])),
                "messages": r.get("messages", []),
                "error": r.get("error"),
            }
            for r in all_results
        ],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, default=str)
    print(f"[REPORT] Report saved to: {report_path}\n")

    # Cleanup
    db.close()


if __name__ == "__main__":
    asyncio.run(run_simulation())
