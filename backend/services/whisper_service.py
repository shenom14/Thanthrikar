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

    def is_speech_present(self, audio_bytes: bytes, threshold=0.002) -> bool:
        """
        Simple energy-based Voice Activity Detection.
        Returns True if the audio chunk has enough volume to be considered speech.
        """
        if len(audio_bytes) == 0:
            return False
            
        # Convert bytes to int16 array
        samples = np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0
        
        # Calculate Root Mean Square energy
        rms_energy = np.sqrt(np.mean(samples**2))
        return bool(rms_energy > threshold)

    def transcribe_audio_buffer(self, audio_bytes: bytes) -> str:
        """
        Takes raw 16kHz mono PCM bytes directly from the browser's AudioContext
        and runs them through Whisper without ffmpeg overhead.
        """
        try:
            # The browser now sends pure 16-bit PCM, no WebM decoding needed!
            # Convert raw bytes directly to numpy float32 expected by faster-whisper
            samples = np.frombuffer(audio_bytes, np.int16).astype(np.float32) / 32768.0
            
            # Transcribe the accumulated audio
            segments, info = self.model.transcribe(samples, beam_size=1, word_timestamps=False, condition_on_previous_text=False)
            
            text = " ".join([segment.text for segment in segments]).strip()
            return text
        except Exception as e:
            logger.error(f"Error transcribing audio buffer: {e}")
            return ""

# Global singleton
whisper_service = AudioTranscriptionService()
