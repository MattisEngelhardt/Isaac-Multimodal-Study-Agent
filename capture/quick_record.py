import os
import time
import queue
import logging
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav

logger = logging.getLogger(__name__)

class QuickVoiceRecorder:
    def __init__(self, samplerate=16000, channels=1):
        """
        Microphone recorder for quick study notes.
        :param samplerate: Sampling rate (Hz).
        :param channels: Audio channels count (1 = Mono).
        """
        self.samplerate = samplerate
        self.channels = channels
        self.audio_queue = queue.Queue()
        self.stream = None
        self.recording = False
        self.start_time = 0
        self.filepath = None

    def _callback(self, indata, frames, time_info, status):
        """Standard sounddevice InputStream callback queue writer."""
        if status:
            logger.warning(f"Recorder Status Warning: {status}")
        self.audio_queue.put(indata.copy())

    def start_recording(self, watch_dir: str) -> bool:
        """Starts capturing audio stream into memory."""
        if self.recording:
            logger.warning("Recorder already capturing.")
            return False

        os.makedirs(watch_dir, exist_ok=True)
        filename = f"voice_note_{int(time.time())}.wav"
        self.filepath = os.path.abspath(os.path.join(watch_dir, filename))

        self.audio_queue = queue.Queue()
        self.recording = True
        self.start_time = time.time()

        try:
            self.stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                dtype="int16",
                callback=self._callback
            )
            self.stream.start()
            logger.info(f"Recorder: Started quick recording -> {self.filepath}")
            return True
        except Exception as e:
            logger.error(f"Recorder: Failed to start audio input: {e}")
            self.recording = False
            self.stream = None
            return False

    def stop_recording(self) -> str:
        """Stops capturing and flushes WAV file to disk."""
        if not self.recording or not self.stream:
            return None

        logger.info("Recorder: Stopping audio capture...")
        self.recording = False
        self.stream.stop()
        self.stream.close()
        self.stream = None

        # Gather data from queue
        audio_data = []
        while not self.audio_queue.empty():
            audio_data.append(self.audio_queue.get())

        if not audio_data:
            logger.warning("Recorder: Audio queue is empty. No voice data captured.")
            return None

        # Save to WAV file
        try:
            audio_np = np.concatenate(audio_data, axis=0)
            wav.write(self.filepath, self.samplerate, audio_np)
            logger.info(f"Recorder: Audio file written: {self.filepath}")
            return self.filepath
        except Exception as e:
            logger.error(f"Recorder: Error writing WAV output: {e}")
            return None

    def get_duration(self) -> float:
        """Returns elapsed recording duration in seconds."""
        if not self.recording:
            return 0.0
        return time.time() - self.start_time
