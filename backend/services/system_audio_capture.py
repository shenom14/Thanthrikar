import pyaudio
import time
import numpy as np
from config.logger import setup_logger
from backend.services.whisper_service import whisper_service

logger = setup_logger(__name__)

class SystemAudioCapture:
    def __init__(self, sample_rate=16000, chunk_duration_ms=500):
        self.sample_rate = sample_rate
        self.chunk_size = int(sample_rate * (chunk_duration_ms / 1000.0))
        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = None
        self.is_running = False
        self.format = pyaudio.paInt16
        self.channels = 1
        self.silence_chunks = 0
        self.audio_buffer = bytearray()
        self.on_transcription_callback = None
        self.device_index = self._find_virtual_cable()

    def _find_virtual_cable(self):
        device_count = self.pyaudio_instance.get_device_count()
        for i in range(device_count):
            dev_info = self.pyaudio_instance.get_device_info_by_index(i)
            name = dev_info.get("name", "").lower()
            if dev_info.get("maxInputChannels") > 0:
                if "cable output" in name or "virtual audio cable" in name:
                    logger.info(f"[Audio] Found Virtual Audio Cable at index {i}: {dev_info.get('name')}")
                    return i
        try:
            default_index = self.pyaudio_instance.get_default_input_device_info()["index"]
            name = self.pyaudio_instance.get_device_info_by_index(default_index).get("name")
            logger.warning(f"[Audio] Virtual Audio Cable not found. Falling back to default input: {name}")
            return default_index
        except IOError:
            logger.error("[Audio] No input devices found on this system.")
            return None

    def start(self, on_transcription):
        if self.is_running:
            return
        self.on_transcription_callback = on_transcription
        self.is_running = True

        try:
            self.stream = self.pyaudio_instance.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=self.device_index
            )
            logger.info("[Audio] PyAudio stream opened successfully.")

            self.silence_chunks = 0
            self.audio_buffer = bytearray()
            last_transcription_time = time.time()

            while self.is_running:
                try:
                    raw_bytes = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # VAD check
                    is_speech = whisper_service.is_speech_present(raw_bytes)
                    
                    if is_speech:
                        self.silence_chunks = 0
                        self.audio_buffer.extend(raw_bytes)
                    else:
                        self.silence_chunks += 1

                    # FIX #1 & #2: On silence boundary (end of utterance), transcribe THEN clear
                    # 6 chunks x 500ms = 3s of silence -> end of utterance
                    if self.silence_chunks >= 6 and len(self.audio_buffer) > 0:
                        logger.debug("[Audio] End of utterance detected. Transcribing buffer...")
                        text = whisper_service.transcribe_audio_buffer(bytes(self.audio_buffer))
                        self.audio_buffer.clear()           # Clear AFTER transcribing
                        self.silence_chunks = 0
                        last_transcription_time = time.time()

                        if text and self.on_transcription_callback:
                            logger.info(f"[Whisper -> silence flush] {text}")
                            self.on_transcription_callback(text)
                        continue

                    # Also transcribe periodically while speech is ongoing (~3s of accumulated audio)
                    elapsed = time.time() - last_transcription_time
                    has_enough_data = len(self.audio_buffer) >= (self.chunk_size * 6)  # ~3s of audio

                    if has_enough_data or (elapsed >= 3.0 and len(self.audio_buffer) > 0):
                        text = whisper_service.transcribe_audio_buffer(bytes(self.audio_buffer))
                        self.audio_buffer.clear()           # Always clear after transcription
                        last_transcription_time = time.time()
                        # FIX #4: No delta logic needed -- each call is a fresh independent chunk

                        if text and self.on_transcription_callback:
                            logger.info(f"[Whisper -> periodic] {text}")
                            self.on_transcription_callback(text)

                except IOError as e:
                    logger.error(f"[Audio] PyAudio read error: {e}")

        except Exception as e:
            logger.error(f"[Audio] Failed to open PyAudio stream: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.info("[Audio] PyAudio stream closed.")

    def cleanup(self):
        self.stop()
        self.pyaudio_instance.terminate()

# Global Singleton
system_audio = SystemAudioCapture()
