import io
import queue
import threading
import numpy as np
from faster_whisper import WhisperModel
from pydub import AudioSegment
from config.logger import setup_logger

logger = setup_logger(__name__)

class AudioTranscriptionService:
    def __init__(self, model_size="tiny.en"):
        logger.info(f"Loading faster-whisper model '{model_size}'...")
        # int8 for fast CPU inference
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model loaded successfully.")

    def transcribe_audio_buffer(self, audio_bytes: bytes) -> str:
        """
        Takes an accumulated buffer of WebM/Opus audio bytes from the browser,
        decodes it into standard 16kHz mono PCM using pydub, and runs Whisper.
        """
        try:
            # Pydub can read WebM/Opus bytes directly via ffmpeg under the hood
            audio_io = io.BytesIO(audio_bytes)
            audio_segment = AudioSegment.from_file(audio_io, codec="opus")
            
            # Whisper expects 16kHz mono
            audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)
            
            # Convert to numpy array of float32 expected by faster-whisper
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0 # Normalize 16-bit PCM to [-1.0, 1.0]
            
            # Transcribe the accumulated audio
            segments, info = self.model.transcribe(samples, beam_size=1, word_timestamps=False)
            
            text = " ".join([segment.text for segment in segments]).strip()
            return text
        except Exception as e:
            logger.error(f"Error transcribing audio buffer: {e}")
            return ""

# Global singleton
whisper_service = AudioTranscriptionService()
