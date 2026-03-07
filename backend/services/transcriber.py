import os
import sys
import json
import logging

from config.logger import setup_logger

logger = setup_logger(__name__)

# Usually PCM audio from browser getUserMedia (audioWorklet) downsampled will be 16000Hz or 48000Hz.
# We will enforce 16000Hz in the frontend so we hardcode it here.
SAMPLE_RATE = 16000

class StreamingTranscriber:
    """
    Handles real-time audio transcription using an offline Vosk model.
    """
    def __init__(self, model_path: str = "backend/model"):
        self.enabled = False
        self.model_path = model_path
        self._model = None
        self._init_attempted = False

    def _load_model(self):
        if self._init_attempted:
            return
        self._init_attempted = True
        try:
            if not os.path.exists(self.model_path):
                logger.error(f"Vosk model path not found: {self.model_path}")
                return
            
            # Disable Vosk's noisy C-level logging
            from vosk import SetLogLevel
            SetLogLevel(-1)

            logger.info("Loading offline Vosk speech recognition model...")
            from vosk import Model
            self._model = Model(self.model_path)
            self.enabled = True
            logger.info("Vosk model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Vosk model: {e}")

    def create_recognizer(self):
        """
        Creates a new independent recognizer instance for a specific concurrent connection.
        """
        self._load_model()
        if not self.enabled:
            raise RuntimeError("Cannot create recognizer; Vosk engine disabled.")
            
        from vosk import KaldiRecognizer
        return KaldiRecognizer(self._model, SAMPLE_RATE)

    def process_chunk(self, recognizer, audio_data: bytes) -> str:
        """
        Pass binary PCM audio chunk to the recognizer.
        Returns transcribed text if a sentence boundary is detected, else empty string.
        """
        is_boundary = recognizer.AcceptWaveform(audio_data)
        partial = json.loads(recognizer.PartialResult()).get("partial", "")
        # Very noisy log, but good for seeing if we have data
        # logger.debug(f"Transcriber bytes: {len(audio_data)}, partial: '{partial}', boundary: {is_boundary}")
        
        if is_boundary:
            # A full sentence or pause was reached
            result = json.loads(recognizer.Result())
            text = result.get("text", "").strip()
            if text:
                logger.info(f"Vosk Final Text: {text}")
            return text
        else:
            # Return partial if we want real-time feedback, but for now just log it
            if partial and len(partial.split()) > 3:
                # Optionally return partial if it gets long enough, but let's stick to boundaries
                pass
            return ""
