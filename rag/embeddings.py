from sentence_transformers import SentenceTransformer
from typing import Any
from config.settings import settings
from config.logger import setup_logger

logger = setup_logger(__name__)

class EmbeddingService:
    """
    Singleton class to manage the lifecycle of the SentenceTransformer model.
    Ensures the model is loaded into memory only once across both ingest.py and retriever.py.
    """
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance
    def get_model(self) -> Any:
        """
        Lazily loads the embedding model specified in config/settings.py.
        Uses a timeout to prevent HuggingFace/SentenceTransformers from freezing
        the entire backend during startup when network or multiprocess issues occur.
        """
        if self._model is None:
            import concurrent.futures
            import numpy as np
            
            # Create a mock embedded if loading hangs
            class MockEmbeddingModel:
                def encode(self, texts, *args, **kwargs):
                    logger.warning("Using MockEmbeddingModel. Returning zero embeddings.")
                    return np.zeros((len(texts), 384))
            
            logger.info(f"Attempting load of Embedding Model: {settings.EMBEDDING_MODEL_NAME} within 15s timeout.")
            
            def _load():
                return SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
                
            try:
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                future = executor.submit(_load)
                self._model = future.result(timeout=15)
                logger.info("Embedding Model loaded successfully.")
                executor.shutdown(wait=False)
            except concurrent.futures.TimeoutError:
                logger.error("Embedding Model download/initialization timed out! Falling back to Mock.")
                self._model = MockEmbeddingModel()
                # Don't wait for the frozen huggingface thread to close
                executor.shutdown(wait=False)
            except Exception as e:
                logger.error(f"Error loading Embedding Model: {e}. Falling back to Mock.")
                self._model = MockEmbeddingModel()
                executor.shutdown(wait=False)
                
        return self._model
        
# Export the singleton instance
embedding_service = EmbeddingService()
