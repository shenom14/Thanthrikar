# Architecture Overview: AI Interview Copilot

## Core Design Philosophy
The system follows a modular, service-oriented architecture designed for scalability, maintainability, and parallel development. It strictly separates routing (FastAPI), business logic (Services), Intelligence APIs (Agents), and persistent state (ChromaDB / SQLite).

## System Boundaries
- **FastAPI / Routes Layer**: Entrypoint receiving REST calls from the Chrome Extension. Handles JSON serialization (Pydantic) and HTTP error throwing. NO business logic.
- **Service Layer**: The bridge connecting the API to the Agents and Databases. Coordinates things like: *“Fetch Candidate -> Transcribe Audio -> Pass to Planner Agent -> Evaluate Facts -> Save Session Insight.”*
- **Agents Layer**: Stateless classes orchestrating Prompt Templates, LLMs, and Parsers (LangChain). They receive pure strings/dicts and return structured JSON.
- **RAG Layer**: Responsible solely for knowledge injection. `ingest.py` chunks data into ChromaDB, and `retriever.py` pulls evidence based on Semantic Similarity using singleton models from `embeddings.py`.

## Data Stores
1. **SQLite / PostgreSQL (`data/copilot.db`)**: Tracks long-lived relational entities like Candidates, Sessions, and Insights.
2. **ChromaDB (`chroma_db/`)**: Specialized local vector database storing isolated chunks of candidate resumes for retrieval.

## Real-Time Constraints (WebSockets)
Live interview audio/transcripts are processed over WebSocket boundaries. The server must handle reconnects, maintain session state via IDs, and prevent runaway LLM calls on incomplete text chunks.
