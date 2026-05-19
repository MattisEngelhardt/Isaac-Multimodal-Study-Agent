import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

class VoiceProcessor:
    def __init__(self, model="whisper-1", api_key=None, whisper_mode="api", whisper_local_model="base"):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.whisper_mode = whisper_mode
        self.whisper_local_model = whisper_local_model or "base"
        self._local_model = None
        self.client = None

    def _process_local(self, audio_path: str) -> str:
        """Transcribes audio file locally using faster-whisper without API calls."""
        try:
            if not self._local_model:
                logger.info(f"Loading local Whisper model '{self.whisper_local_model}' for Study Agent...")
                from faster_whisper import WhisperModel
                self._local_model = WhisperModel(self.whisper_local_model, device="cpu", compute_type="int8")

            logger.info(f"Voice (Local): Transcribing audio file locally: {audio_path}")
            
            import scipy.io.wavfile as wav
            import numpy as np

            samplerate, data = wav.read(audio_path)

            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            if data.dtype == np.int16:
                data = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                data = data.astype(np.float32) / 2147483648.0
            elif data.dtype == np.uint8:
                data = (data.astype(np.float32) - 128.0) / 128.0
            else:
                data = data.astype(np.float32)

            segments, info = self._local_model.transcribe(data, beam_size=5)
            transcript_text = " ".join([segment.text for segment in segments]).strip()
            logger.info(f"Voice (Local): Transcription finished successfully for {os.path.basename(audio_path)}")
            return transcript_text

        except Exception as e:
            logger.error(f"Error during Study Agent local Whisper transcription: {e}")
            if self.api_key:
                logger.warning("Local transcription failed. Falling back to OpenAI Whisper API...")
                self.whisper_mode = "api"
                return self.process(audio_path)
            return f"[Error transcribing audio locally: {e}]"

    def process(self, audio_path: str) -> str:
        """
        Transcribes voice memos, lecture recordings, or audio files using OpenAI's Whisper (API or local).
        :param audio_path: Path to the audio file.
        :return: Transcription string.
        """
        logger.info(f"Voice: Starting transcription on {audio_path}")
        if not os.path.exists(audio_path):
            return f"[Error: Audio file {audio_path} not found]"

        if self.whisper_mode == "local":
            return self._process_local(audio_path)

        if not self.api_key:
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                logger.error("Voice transcription failed: OpenAI API key is missing.")
                return "[Error: OPENAI_API_KEY is not set]"

        if not self.client:
            self.client = OpenAI(api_key=self.api_key)

        try:
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file
                )
            
            transcript_text = response.text.strip()
            logger.info(f"Voice transcription finished successfully for {os.path.basename(audio_path)}")
            return transcript_text

        except Exception as e:
            logger.error(f"Error during Whisper transcription: {e}")
            return f"[Error transcribing audio: {e}]"
