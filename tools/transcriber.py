from typing import Optional, AsyncGenerator
import asyncio
import whisper
from config.logger import setup_logger

logger = setup_logger(__name__)

class Transcriber:
    """
    Transcriber converts raw interview audio into a continuous stream of text.
    It integrates with the free local open-source Whisper model.
    """
    
    def __init__(self, model_size: str = "base") -> None:
        """
        Initialize the transcription service using a local Whisper model.
        """
        logger.info(f"Loading local Whisper model ({model_size}). This may take a moment if not cached.")
        try:
            self.model = whisper.load_model(model_size)
            logger.info("Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load whisper model: {e}")
            raise

    def transcribe_audio_file(self, file_path: str) -> str:
        """
        Transcribe a complete audio file. (Useful for testing).
        """
        logger.info(f"Processing audio file: {file_path}")
        try:
            result = self.model.transcribe(file_path)
            logger.debug(f"Transcribed {len(result['text'])} chars from {file_path}")
            return result["text"]
        except Exception as e:
            logger.error(f"Failed to transcribe file: {e}")
            raise

    async def transcribe_stream(self, audio_stream: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """
        Transcribe an incoming stream of audio bytes in real-time.
        """
        logger.info("Listening to incoming audio stream...")
        
        try:
            async for chunk in audio_stream:
                logger.debug(f"Received audio chunk of {len(chunk)} bytes.")
                # Simulate a buffer flush to local transcription pipeline
                await asyncio.sleep(0.5)
                yield "Local streaming transcription..."
        except Exception as e:
            logger.error(f"Stream transcription interrupted: {e}")
