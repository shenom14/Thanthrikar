import re
import pdfplumber
from typing import Optional, Any
from config.logger import setup_logger

logger = setup_logger(__name__)

def load_pdf(file_path: str) -> Any:
    return pdfplumber.open(file_path)

def extract_text(pdf_obj: Any) -> str:
    text_content = []
    for i, page in enumerate(pdf_obj.pages):
        page_text = page.extract_text()
        if page_text:
            text_content.append(page_text)
        else:
            logger.warning(f"Failed to extract text from page {i+1}")
    return "\n".join(text_content)

def clean_text(raw_text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', raw_text)
    return cleaned.strip()

class ResumeParser:
    """
    ResumeParser extracts raw text content from PDF resume files.
    This component normalizes and cleans the text to prepare it for chunking and embedding.
    """

    def __init__(self) -> None:
        pass

    def parse_pdf(self, file_path: str) -> Optional[str]:
        logger.info(f"Parsing PDF file: {file_path}")
        try:
            with load_pdf(file_path) as pdf_obj:
                raw_text = extract_text(pdf_obj)
            cleaned = clean_text(raw_text)
            logger.info(f"Successfully extracted {len(cleaned)} chars of text from {file_path}")
            return cleaned
        except Exception as e:
            logger.error(f"Error parsing file {file_path}: {e}")
            return None

    def _clean_text(self, text: str) -> str:
        return clean_text(text)
