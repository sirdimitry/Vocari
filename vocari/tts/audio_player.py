"""Plays synthesized speech through sounddevice and drives two things from
the audio's RMS amplitude:

- the 2-state mouth (open/closed, no interpolation — per spec), via a simple
  threshold on the current chunk;
- an audio-reactive bounce level (0..1, smoothed with fast-attack/slow-release
  "envelope follower" ballistics — the same technique VU meters and music
  visualizers use) so a loud/sharp sound makes the avatar hop more sharply
  and it settles gently during quiet passages, instead of bouncing at a
  constant rate regardless of loudness.

Only one thing plays at a time (play() cancels whatever was running), so the
mouth/talking/level callbacks are passed fresh into each play() call rather
than fixed at construction — the caller (TTSQueue) points them at whichever
avatar instance is currently the speaker.

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

# sounddevice/PortAudio's own "high" latency default (already the most
# conservative built-in option) was not enough to keep this stutter-free -
# confirmed via a loopback recording of actual playback output: with only
# the library default, PipeWire logged constant "spa.alsa: front:0p:
# follower ... resync" events (its ALSA output node repeatedly falling
# behind its own target buffer and having to resync) and the recording
# showed ~50ms dropouts roughly every 85ms during speech, on emulated
# VirtualBox audio hardware. Explicitly requesting a bigger client-side
# buffer than the library default gives PipeWire's ALSA follower enough
# slack to absorb that hardware's timing jitter - a follow-up recording
# with these values dropped the dropout count roughly 10x (189 -> 19 over
# the same test phrase). Still not perfectly glitch-free on this hardware,
# but the dominant, strictly-periodic stutter pattern is gone; the
# remaining occasional short gaps look like genuine VM audio-clock jitter,
# not something more buffering can fix.
OUTPUT_LATENCY_S = 0.5
OUTPUT_BLOCKSIZE = 4096

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
    def __init__(self):
        super().__init__()
        self._on_mouth_state: Callable[[bool], None] | None = None
        self._on_talking: Callable[[bool], None] | None = None
        self._on_audio_level: Callable[[float], None] | None = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self._pcm: np.ndarray | None = None
        self._samplerate = 0
        self._start_time = 0.0
        self._on_finished: Callable[[], None] | None = None
        self._envelope = 0.0

    def play(
        self,
        audio_bytes: bytes,
        volume: float,
        on_finished: Callable[[], None],
        on_mouth_state: Callable[[bool], None],
        on_talking: Callable[[bool], None],
        on_audio_level: Callable[[float], None],
    ) -> None:
        """volume: 0.0-1.5 linear gain applied before playback. The three
        on_* callbacks target whichever avatar instance is speaking this
        line — fresh per call, since only one thing plays at a time.

        Decoding/device errors are caught rather than left to propagate: this
        runs from inside a deferred QTimer callback with no caller to catch
        anything, so an uncaught exception here used to leave the avatar
        stuck on stage forever — bubble up, mouth shut, nothing ever
        retiring it, since on_finished (the only thing that eventually calls
        retire) would simply never fire. Treating a failed start as an
        immediate finish keeps that from stalling the queue."""
        self.stop()  # cancel any playback already in progress
        try:
            data, samplerate = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
            if data.ndim > 1:
                data = data.mean(axis=1)
            if volume != 1.0:
                data = np.clip(data * volume, -1.0, 1.0)
            sd.play(data, samplerate, latency=OUTPUT_LATENCY_S, blocksize=OUTPUT_BLOCKSIZE)
            # The requested latency above is a real, audible delay between
            # this call and the first sample actually reaching the speakers
            # (see OUTPUT_LATENCY_S) - reading it back from the stream PortAudio
            # actually opened (rather than assuming our request was granted
            # verbatim) and pushing _start_time out by that much keeps the
            # mouth/bounce polling in _on_tick() in sync with the real audio
            # instead of animating up to half a second ahead of it.
            stream = sd.get_stream()
            output_delay = stream.latency if stream is not None else 0.0
        except Exception:
            logger.exception("Не удалось начать воспроизведение — считаю фразу законченной")
            on_finished()
            return

        self._on_mouth_state = on_mouth_state
        self._on_talking = on_talking
        self._on_audio_level = on_audio_level
        self._pcm = data
        self._samplerate = samplerate
        self._on_finished = on_finished
        self._envelope = 0.0

        self._start_time = time.monotonic() + output_delay
        self._on_talking(True)
        self._on_mouth_state(False)
        self._timer.start(POLL_INTERVAL_MS)

    def skip(self) -> None:
        """Cuts the current utterance short mid-word (the skip hotkey) and
        runs the exact same "done" path a natural finish would — same
        on_finished callback, same mouth/talking/level reset — so the
        stage's exit/promote logic needs no separate code path for this."""
        if self._pcm is None:
            return
        sd.stop()
        self._finish()

    def stop(self) -> None:
        if self._pcm is None:
            return
        sd.stop()
        self._timer.stop()
        self._pcm = None
        self._envelope = 0.0
        if self._on_talking:
            self._on_talking(False)
        if self._on_mouth_state:
            self._on_mouth_state(False)
        if self._on_audio_level:
            self._on_audio_level(0.0)
        self._on_finished = None
        self._on_mouth_state = None
        self._on_talking = None
        self._on_audio_level = None

    def _on_tick(self) -> None:
        if self._pcm is None:
            return
        elapsed = time.monotonic() - self._start_time
        if elapsed < 0:
            # Still inside the output device's own startup latency (see
            # OUTPUT_LATENCY_S) - nothing is audible yet, so keep the mouth
            # shut instead of indexing self._pcm with a negative offset
            # (which would silently wrap around and read from its tail).
            self._on_mouth_state(False)
            return
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
        on_talking, on_mouth_state, on_audio_level = self._on_talking, self._on_mouth_state, self._on_audio_level
        callback = self._on_finished
        self._on_finished = None
        self._on_mouth_state = None
        self._on_talking = None
        self._on_audio_level = None
        if on_talking:
            on_talking(False)
        if on_mouth_state:
            on_mouth_state(False)
        if on_audio_level:
            on_audio_level(0.0)
        if callback:
            callback()
