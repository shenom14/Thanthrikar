import os
import argparse
from typing import List, Dict, Any
import chromadb

from rag.embeddings import embedding_service

# Initialize DB path same as ingest
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'chroma_db')

class ResumeRetriever:
    """
    ResumeRetriever handles querying the Chroma vector database to find resume evidence matching user claims.
    """
    
    def __init__(self, collection_name: str = "resumes"):
        """
        Initialize the connection to ChromaDB and the Embedding model for queries.
        
        Args:
            collection_name (str): The name of the collection to search within.
        """
        self.collection_name = collection_name
        # Reuse the shared embedding model to avoid reloading it per-component
        self.model = embedding_service.get_model()
        
        try:
            self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            self.collection = self.chroma_client.get_collection(name=self.collection_name)
        except Exception as e:
            print(f"Could not connect to ChromaDB or collection '{self.collection_name}' does not exist. Error: {e}")
            self.collection = None

    def retrieve_evidence(self, candidate_id: str, claim: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Perform a semantic similarity search in the vector DB to retrieve relevant resume chunks.
        
        Args:
            candidate_id (str): The ID of the candidate (used for metadata filtering).
            claim (str): The extracted claim text to search against.
            top_k (int): Number of most relevant chunks to return.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing retrieved text and its metadata.
        """
        claim = claim.strip()
        if not claim:
            print("Error: Empty claim provided.")
            return []
            
        if not self.collection:
            print("Error: Collection not initialized.")
            return []
            
        print(f"[ResumeRetriever] Searching for evidence related to claim: '{claim}'")
        
        # 1. Generate an embedding for the `claim` query.
        query_embedding = self.model.encode([claim])
        
        # 2. Perform a similarity search in Chroma.
        # Filter by candidate_id when provided so each candidate's resume evidence is isolated.
        where_clause = {}
        if candidate_id:
            where_clause["candidate_id"] = candidate_id
        
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=top_k,
            where=where_clause or None
        )
        
        retrieved_chunks = []
        if results and 'documents' in results and results['documents']:
            docs = results['documents'][0]
            metadatas = results['metadatas'][0] if 'metadatas' in results and results['metadatas'] else [{}] * len(docs)
            distances = results['distances'][0] if 'distances' in results and results['distances'] else [0.0] * len(docs)
            
            for doc, meta, dist in zip(docs, metadatas, distances):
                retrieved_chunks.append({
                    "text": doc,
                    "metadata": meta,
                    "score": 1 - dist # Pseudo-similarity
                })
                
        return retrieved_chunks


def retrieve(query: str, top_k: int = 5):
    """
    Search the vector database for chunks most relevant to the user query (CLI interface).
    """
    retriever = ResumeRetriever()
    # Using a dummy candidate_id for CLI testing globally
    results = retriever.retrieve_evidence(candidate_id="", claim=query, top_k=top_k)
    
    mapped_results = []
    for res in results:
        mapped_results.append({
            "source": res["metadata"].get("source", "Unknown"),
            "chunk": res["text"]
        })
    return mapped_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieve top relevant chunks from the resume vector database.")
    parser.add_argument("query", type=str, help="The search query (e.g., 'Python experience')")
    parser.add_argument("--top_k", type=int, default=5, help="Number of results to retrieve")
    args = parser.parse_args()
    
    results = retrieve(args.query, top_k=args.top_k)
    
    if results:
        print("\n--- Top Relevant Chunks ---")
        for i, res in enumerate(results, 1):
            print(f"\n[Result {i}] Source: {os.path.basename(res['source'])}")
            print(f"Content: {res['chunk']}")
            print("-" * 60)
    else:
        print("\nNo results found.")
