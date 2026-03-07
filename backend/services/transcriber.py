import os
import sys
import json
import logging

from config.logger import setup_logger

logger = setup_logger(__name__)

# Usually PCM audio from browser getUserMedia (audioWorklet) downsampled will be 16000Hz or 48000Hz.
# We will enforce 16000Hz in the frontend so we hardcode it here.
SAMPLE_RATE = 16000

import os
import sys
import logging
from typing import Optional
from groq import AsyncGroq
from fastapi import UploadFile

from config.logger import setup_logger
from config.settings import settings

logger = setup_logger(__name__)

class StreamingTranscriber:
    """
    Handles near real-time audio transcription using Groq's insanely fast Whisper API.
    Audio chunks are sent directly to the cloud, bypassing the need for heavy offline models.
    """
    def __init__(self):
        self.enabled = False
        api_key = settings.GROQ_API_KEY
        if not api_key:
            logger.error("GROQ_API_KEY not found in settings! Transcriber disabled.")
            return

        self.client = AsyncGroq(api_key=api_key)
        self.enabled = True
        logger.info("Groq Whisper Transcriber initialized successfully.")

    async def process_chunk(self, audio_data: bytes, filename: str = "chunk.webm") -> str:
        """
        Pass compressed audio (webm) to Groq's whisper model.
        Returns transcribed text if successful, else an empty string.
        """
        if not self.enabled or not audio_data:
            return ""

        try:
            # We must pass a tuple of (filename, file_content) to the files parameter
            transcription = await self.client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=(filename, audio_data),
                response_format="text"
            )
            
            # groq returns the raw text string if response_format="text"
            text = transcription.strip() if isinstance(transcription, str) else ""
            if text:
                logger.info(f"Groq Whisper Text: {text}")
            return text

        except Exception as e:
            logger.error(f"Groq Whisper API failed on {len(audio_data)} bytes chunk: {e}")
            return ""
