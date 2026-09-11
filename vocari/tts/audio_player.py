"""Plays synthesized speech through sounddevice and drives the 2-state mouth
(open/closed, no interpolation — per spec) from the audio's RMS amplitude.

Rather than a sounddevice callback (which runs on PortAudio's own thread and
would need cross-thread marshalling into Qt), this polls elapsed wall-clock
time on a Qt timer and reads the matching slice of the already-decoded PCM
buffer — simpler, and plenty accurate for a 2-state mouth.
"""
from __future__ import annotations

import io
import time
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf
from PySide6.QtCore import QObject, QTimer

from vocari.logging_setup import get_logger

logger = get_logger("tts.audio")

POLL_INTERVAL_MS = 33
RMS_WINDOW_SAMPLES = 1024
MOUTH_RMS_THRESHOLD = 0.02


class AudioPlayer(QObject):
    def __init__(
        self,
        on_mouth_state: Callable[[bool], None],
        on_talking: Callable[[bool], None],
    ):
        super().__init__()
        self._on_mouth_state = on_mouth_state
        self._on_talking = on_talking

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._pcm: np.ndarray | None = None
        self._samplerate = 0
        self._start_time = 0.0
        self._on_finished: Callable[[], None] | None = None

    def play(self, audio_bytes: bytes, volume: float, on_finished: Callable[[], None]) -> None:
        """volume: 0.0-1.5 linear gain applied before playback."""
        data, samplerate = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if volume != 1.0:
            data = np.clip(data * volume, -1.0, 1.0)

        self.stop()  # cancel any playback already in progress
        self._pcm = data
        self._samplerate = samplerate
        self._on_finished = on_finished

        sd.play(data, samplerate)
        self._start_time = time.monotonic()
        self._on_talking(True)
        self._on_mouth_state(False)
        self._timer.start(POLL_INTERVAL_MS)

    def stop(self) -> None:
        if self._pcm is None:
            return
        sd.stop()
        self._timer.stop()
        self._pcm = None
        self._on_talking(False)
        self._on_mouth_state(False)
        self._on_finished = None

    def _on_tick(self) -> None:
        if self._pcm is None:
            return
        elapsed = time.monotonic() - self._start_time
        index = int(elapsed * self._samplerate)
        window = self._pcm[index : index + RMS_WINDOW_SAMPLES]
        if index >= len(self._pcm) or len(window) == 0:
            self._finish()
            return
        rms = float(np.sqrt(np.mean(np.square(window))))
        self._on_mouth_state(rms > MOUTH_RMS_THRESHOLD)

    def _finish(self) -> None:
        self._timer.stop()
        self._pcm = None
        self._on_talking(False)
        self._on_mouth_state(False)
        callback = self._on_finished
        self._on_finished = None
        if callback:
            callback()
