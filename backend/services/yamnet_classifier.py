"""YamNet audio-event classifier (ONNX Runtime).

Unlike librosa RMS/onset (which only measures *energy*), YamNet says *what*
the sound is — laughter, applause, cheering, music — which are far stronger
virality signals. Runs on the ONNX port (no TensorFlow dependency) and degrades
gracefully: if onnxruntime or the model file is missing, classify() returns []
and the pipeline keeps working on energy peaks alone.

Model expects mono 16 kHz float32 waveform in [-1, 1]. Output scores are
[num_frames, 521] over AudioSet classes, one frame per ~0.48 s hop.
"""
from __future__ import annotations
import csv
import logging
import os
from typing import List

from backend.schemas.moment_instruction import AudioEvent
from backend.gpu_config import YAMNET_ONNX_PATH, YAMNET_CLASSMAP_PATH

logger = logging.getLogger(__name__)

# AudioSet classes that correlate with viral / high-engagement moments.
# Anything not in this set is ignored (we don't surface "Speech", "Silence"...).
VIRAL_LABELS = {
    "Laughter", "Baby laughter", "Giggle", "Snicker", "Belly laugh",
    "Chuckle, chortle", "Applause", "Clapping", "Cheering", "Crowd",
    "Whoop", "Children shouting", "Screaming", "Shout", "Yell",
    "Gasp", "Crying, sobbing", "Music", "Booing", "Chatter",
}

# Hop between YamNet frames (seconds). Fixed by the model architecture.
_FRAME_HOP = 0.48
_TARGET_SR = 16000


class YamNetClassifier:
    def __init__(self):
        self._session = None
        self._labels: List[str] = []
        self._input_name = None
        self._available = None  # tri-state: None=unprobed, True/False after load

    def _ensure_loaded(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            if not os.path.exists(YAMNET_ONNX_PATH):
                logger.warning(f"🔊 [YamNet] модель не найдена: {YAMNET_ONNX_PATH} — события аудио отключены")
                self._available = False
                return False
            import onnxruntime as ort
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            self._session = ort.InferenceSession(YAMNET_ONNX_PATH, providers=providers)
            self._input_name = self._session.get_inputs()[0].name
            self._labels = self._load_labels()
            active = self._session.get_providers()[0]
            logger.info(f"🔊 [YamNet] загружен ({active}), классов: {len(self._labels)}")
            self._available = True
        except Exception as e:
            logger.warning(f"🔊 [YamNet] недоступен ({e}) — события аудио отключены")
            self._available = False
        return self._available

    def _load_labels(self) -> List[str]:
        labels: List[str] = []
        if YAMNET_CLASSMAP_PATH and os.path.exists(YAMNET_CLASSMAP_PATH):
            with open(YAMNET_CLASSMAP_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    labels.append(row.get("display_name") or row.get("name") or "")
        return labels

    def classify(self, waveform, sr: int, min_score: float = 0.4) -> List[AudioEvent]:
        """Return de-duplicated viral AudioEvents from a mono waveform."""
        if not self._ensure_loaded():
            return []
        try:
            import numpy as np

            wav = np.asarray(waveform, dtype=np.float32)
            if wav.ndim > 1:
                wav = wav.mean(axis=0)
            if sr != _TARGET_SR:
                # cheap linear resample; YamNet is tolerant
                import math
                ratio = _TARGET_SR / float(sr)
                idx = np.round(np.arange(0, len(wav) * ratio) / ratio).astype(int)
                idx = idx[idx < len(wav)]
                wav = wav[idx]

            scores = self._session.run(None, {self._input_name: wav})[0]
            scores = np.asarray(scores)
            if scores.ndim != 2 or not self._labels:
                return []

            top_idx = scores.argmax(axis=1)
            events: List[AudioEvent] = []
            last_label = None
            for frame, ci in enumerate(top_idx):
                if ci >= len(self._labels):
                    continue
                label = self._labels[ci]
                conf = float(scores[frame, ci])
                if label in VIRAL_LABELS and conf >= min_score:
                    # collapse consecutive identical labels into one event
                    if label == last_label and events:
                        if conf > events[-1].score:
                            events[-1].score = conf
                        continue
                    events.append(AudioEvent(
                        timestamp=round(frame * _FRAME_HOP, 2),
                        label=label,
                        score=round(conf, 3),
                    ))
                    last_label = label
                else:
                    last_label = None
            logger.info(f"🔊 [YamNet] найдено {len(events)} семантических аудио-событий")
            return events
        except Exception as e:
            logger.warning(f"🔊 [YamNet] ошибка классификации ({e})")
            return []


# Global singleton
yamnet_classifier = YamNetClassifier()
