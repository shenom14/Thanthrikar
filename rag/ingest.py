import os
import sys
import argparse

# Ensure we can import from tools
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from tools.resume_parser import load_pdf, extract_text, clean_text
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb

# Initialize SentenceTransformer model
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Initialize ChromaDB client to a local folder in the project root
CHROMA_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'chroma_db')

def ingest_pdf(pdf_path: str):
    """
    Ingest a PDF resume into the ChromaDB vector database.
    """
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    print(f"Processing PDF: {pdf_path}")
    
    # 1. Load PDF
    try:
        pdf = load_pdf(pdf_path)
    except Exception as e:
        print(f"Error loading PDF {pdf_path}: {e}")
        return
    
    # 2. Extract Text
    raw_text = extract_text(pdf)
    
    # 3. Clean Text
    cleaned_text = clean_text(raw_text)
    
    # 4. Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = text_splitter.split_text(cleaned_text)
    print(f"Generated {len(chunks)} text chunks.")
    
    if not chunks:
        print(f"Warning: No text could be extracted or chunked from {pdf_path}. Skipping.")
        return
    
    # 5. Embeddings
    print("Generating embeddings...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = model.encode(chunks)
    
    # 6. Vector Database Storage
    print("Storing chunks and embeddings in ChromaDB...")
    try:
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = chroma_client.get_or_create_collection(name="resumes")
    except Exception as e:
        print(f"Error connecting to ChromaDB: {e}")
        return
    
    # Prepare data for insertion
    ids = [f"{os.path.basename(pdf_path)}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": pdf_path} for _ in range(len(chunks))]
    
    try:
        collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            documents=chunks
        )
    except Exception as e:
        print(f"Error saving to ChromaDB: {e}")
        return
    
    print(f"Successfully ingested {pdf_path} into ChromaDB!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a resume PDF into the ChromaDB vector database.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF resume")
    args = parser.parse_args()
    
    ingest_pdf(args.pdf_path)
