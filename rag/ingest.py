from typing import List

class DocumentChunker:
    """
    Handles chunking of raw resume text into semantically meaningful pieces.
    """
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        # TODO: Configure LangChain's RecursiveCharacterTextSplitter
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:
        """
        Split text into smaller chunks for vector embeddings.
        
        Args:
            text (str): The cleaned text from a resume.
            
        Returns:
            List[str]: A list of text chunks.
        """
        # TODO: Use a LangChain text splitter here.
        return [text]

class ChromaIngestor:
    """
    ChromaIngestor manages creating embeddings from text chunks and loading them into a ChromaDB instance.
    """
    
    def __init__(self, collection_name: str = "resumes"):
        """
        Initialize the connection to ChromaDB and the Embedding model.
        
        Args:
            collection_name (str): The name of the collection to store vectors in.
        """
        # TODO: Initialize SentenceTransformerEmbeddings
        # TODO: Initialize Chroma client targeting a local directory like './chroma_db'
        self.collection_name = collection_name

    def ingest_chunks(self, chunks: List[str], metadata: dict) -> bool:
        """
        Convert text chunks to embeddings and store them with candidate metadata.
        
        Args:
            chunks (List[str]): The chunks of resume text.
            metadata (dict): Metadata to attach to the vectors (e.g., candidate_id).
            
        Returns:
            bool: True if ingestion was successful.
        """
        # TODO: 
        # 1. Generate embeddings for chunks using SentenceTransformers.
        # 2. Add texts, embeddings, and metadata to Chroma instance.
        
        print(f"[ChromaIngestor] Ingesting {len(chunks)} chunks into ChromaDB...")
        return True

def run_ingestion_pipeline(resume_text: str, candidate_id: str):
    """
    End-to-end pipeline linking text splitting with vector ingestion.
    """
    chunker = DocumentChunker()
    ingestor = ChromaIngestor()
    
    chunks = chunker.split_text(resume_text)
    metadata = {"candidate_id": candidate_id}
    
    ingestor.ingest_chunks(chunks, metadata)
