"""CPU-based audio analysis: RMS energy + onset strength + peak detection.

This service is CPU-only (librosa) and doesn't use GPU resources.
"""
from __future__ import annotations
import logging
import subprocess
import tempfile
import os
from typing import List
from backend.schemas.moment_instruction import AudioPeak, AudioAnalysis
from backend.services.yamnet_classifier import yamnet_classifier

logger = logging.getLogger(__name__)

# Max time (seconds) we allow ffmpeg audio extraction to run before giving up.
FFMPEG_TIMEOUT = 600


class AudioAnalyzer:
    """CPU-based audio analysis using librosa.

    Extracts RMS energy, onset strength, and detects emotional peaks.
    Runs entirely on CPU, no GPU usage.
    """

    def analyze(self, video_path: str) -> AudioAnalysis:
        """Analyze audio energy and detect emotional peaks.

        Args:
            video_path: Path to video file

        Returns:
            AudioAnalysis with peaks, RMS timeline, and statistics
        """
        import librosa
        import numpy as np
        from scipy.signal import find_peaks
        import time
        import cv2

        # Get video duration for logging
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration_min = (total_frames / fps) / 60.0
        cap.release()

        # Create a temp WAV path, but close the handle immediately.
        # On Windows an open handle locks the file, and ffmpeg with -y cannot
        # overwrite it -> deadlock. mkstemp + os.close avoids that conflict.
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        try:
            start_time = time.time()
            logger.info(f"🔊 [Аудио] Загрузка аудиодорожки...")
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-nostdin", "-y", "-i", video_path,
                        "-vn", "-ar", "16000", "-ac", "1", tmp_path,
                    ],
                    check=True,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    timeout=FFMPEG_TIMEOUT,
                )
            except subprocess.TimeoutExpired as exc:
                logger.error(
                    f"🔊 [Аудио] ffmpeg превысил таймаут ({FFMPEG_TIMEOUT}s) "
                    f"при извлечении аудио из {video_path}"
                )
                raise RuntimeError(
                    f"ffmpeg audio extraction timed out after {FFMPEG_TIMEOUT}s "
                    f"for {video_path}"
                ) from exc
            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
                logger.error(f"🔊 [Аудио] ffmpeg завершился с ошибкой: {stderr}")
                raise RuntimeError(
                    f"ffmpeg audio extraction failed for {video_path}: {stderr}"
                ) from exc

            logger.info(f"🔊 [Аудио] Анализирую пики громкости ({video_duration_min:.1f} мин)...")
            y, sr = librosa.load(tmp_path, sr=16000)
            hop_length = 512
            frame_duration = hop_length / sr

            # RMS energy (volume)
            rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)
            avg_rms = float(np.mean(rms))
            max_rms = float(np.max(rms))

            # Onset strength (emotional spikes: laughter, reactions, applause)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

            # Find peaks with minimum distance of 0.5s between peaks
            min_dist_frames = int(0.5 / frame_duration)

            # Spike peaks (sudden bursts)
            spike_indices, _ = find_peaks(
                onset_env,
                height=np.mean(onset_env) * 2.0,
                distance=min_dist_frames
            )

            # Sustained peaks (prolonged energy)
            sustained_indices, _ = find_peaks(
                rms,
                height=avg_rms * 1.8,
                distance=min_dist_frames
            )

            peaks: List[AudioPeak] = []

            # Add spike peaks
            for idx in spike_indices:
                if idx < len(times):
                    peaks.append(AudioPeak(
                        timestamp=float(times[idx]),
                        magnitude=float(onset_env[idx]),
                        peak_type="spike"
                    ))

            # Add sustained peaks
            for idx in sustained_indices:
                if idx < len(times):
                    peaks.append(AudioPeak(
                        timestamp=float(times[idx]),
                        magnitude=float(rms[idx]),
                        peak_type="sustained"
                    ))

            # Sort peaks by timestamp
            peaks.sort(key=lambda p: p.timestamp)

            # Downsample RMS timeline for context log (every 10th frame)
            rms_timeline = [
                {"time": round(float(t), 2), "rms": round(float(r), 4)}
                for t, r in zip(times[::10], rms[::10])
            ]

            # Semantic audio events (YamNet ONNX): laughter, applause, cheering...
            # Reuses the already-loaded 16 kHz mono waveform — no extra I/O.
            # Degrades to [] if onnxruntime/model are unavailable.
            events = yamnet_classifier.classify(y, sr)
            if events:
                from collections import Counter
                by_label = Counter(ev.label for ev in events)
                summary = ", ".join(f"{lbl}×{cnt}" for lbl, cnt in by_label.most_common())
                logger.info(f"🔊 [YamNet] События по типам: {summary}")
            else:
                logger.info("🔊 [YamNet] Семантических событий не найдено (модель отсутствует или тишина)")

            analysis_time = time.time() - start_time
            logger.info(f"🔊 [Аудио] Найдено {len(peaks)} пиков активности, {len(events)} аудио-событий")
            logger.info(f"🔊 [Аудио] Анализ завершён за {analysis_time:.1f}с")
            return AudioAnalysis(
                peaks=peaks,
                rms_timeline=rms_timeline,
                avg_rms=avg_rms,
                max_rms=max_rms,
                events=events
            )

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# Global singleton instance
audio_analyzer = AudioAnalyzer()