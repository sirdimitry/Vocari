"""Plays synthesized speech through sounddevice and drives two things from
the audio's RMS amplitude:

- the 2-state mouth (open/closed, no interpolation — per spec), via a simple
  threshold on the current chunk;
- an audio-reactive bounce level (0..1, smoothed with fast-attack/slow-release
  "envelope follower" ballistics — the same technique VU meters and music
  visualizers use) so a loud/sharp sound makes the avatar hop more sharply
  and it settles gently during quiet passages, instead of bouncing at a
  constant rate regardless of loudness.

Rather than a sounddevice callback (which runs on PortAudio's own thread and
would need cross-thread marshalling into Qt), this polls elapsed wall-clock
time on a Qt timer and reads the matching slice of the already-decoded PCM
buffer — simpler, and plenty accurate for both use cases.
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

# Envelope follower for the bounce: raw RMS is noisy from sample to sample,
# so it's smoothed toward a target level with different speeds depending on
# direction — quick to rise (a sudden loud sound should hit fast) and slower
# to fall (so it doesn't twitch between every word), which is what reads as
# "reacting" to the sound rather than just oscillating on a timer.
LEVEL_REFERENCE_RMS = 0.18  # RMS treated as "full" bounce (1.0); calibrated
# against edge-tts RU output where voiced-frame RMS runs ~0.08 median, ~0.17
# at the 90th percentile — so typical speech sits mid-range and only
# genuinely loud/sharp peaks reach the max hop.
ATTACK_COEFF = 0.6
RELEASE_COEFF = 0.15


class AudioPlayer(QObject):
    def __init__(
        self,
        on_mouth_state: Callable[[bool], None],
        on_talking: Callable[[bool], None],
        on_audio_level: Callable[[float], None],
    ):
        super().__init__()
        self._on_mouth_state = on_mouth_state
        self._on_talking = on_talking
        self._on_audio_level = on_audio_level

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._pcm: np.ndarray | None = None
        self._samplerate = 0
        self._start_time = 0.0
        self._on_finished: Callable[[], None] | None = None
        self._envelope = 0.0

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
        self._envelope = 0.0

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
        self._envelope = 0.0
        self._on_talking(False)
        self._on_mouth_state(False)
        self._on_audio_level(0.0)
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

        target = min(1.0, rms / LEVEL_REFERENCE_RMS)
        coeff = ATTACK_COEFF if target > self._envelope else RELEASE_COEFF
        self._envelope += (target - self._envelope) * coeff
        self._on_audio_level(self._envelope)

    def _finish(self) -> None:
        self._timer.stop()
        self._pcm = None
        self._envelope = 0.0
        self._on_talking(False)
        self._on_mouth_state(False)
        self._on_audio_level(0.0)
        callback = self._on_finished
        self._on_finished = None
        if callback:
            callback()
