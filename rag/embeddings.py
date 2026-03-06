from sentence_transformers import SentenceTransformer
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

    def get_model(self) -> SentenceTransformer:
        """
        Lazily loads the embedding model specified in config/settings.py.
        """
        if self._model is None:
            logger.info(f"Initial load of Embedding Model: {settings.EMBEDDING_MODEL_NAME} into memory.")
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
            logger.info("Embedding Model loaded successfully.")
        return self._model
        
# Export the singleton instance
embedding_service = EmbeddingService()
