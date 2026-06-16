"""Scene detection and audio energy analysis."""
import logging
import cv2
import numpy as np
import librosa
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple
from backend.config import DEFAULT_MIN_DURATION, DEFAULT_MAX_DURATION, DEFAULT_MAX_MOMENTS

logger = logging.getLogger(__name__)


def extract_audio_features(video_path: str) -> Dict[str, np.ndarray]:
    """
    Extract audio energy features using librosa.
    
    Returns:
        Dict with 'energy' (RMS) and 'onsets' arrays with timestamps
    """
    try:
        # Load audio from video
        y, sr = librosa.load(video_path, sr=22050, mono=True)
        
        # Compute RMS energy
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
        
        # Detect onsets (sudden audio changes)
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units='frames')
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)
        
        return {
            'energy': rms,
            'energy_times': rms_times,
            'onsets': onset_times,
        }
    except Exception as e:
        logger.warning(f"Audio feature extraction failed: {e}")
        return {
            'energy': np.array([]),
            'energy_times': np.array([]),
            'onsets': np.array([]),
        }


def detect_scene_changes(video_path: str, sample_interval: float = 2.0) -> List[float]:
    """
    Detect scene changes using frame difference analysis.
    
    Args:
        video_path: Path to video file
        sample_interval: Sample frames every N seconds
        
    Returns:
        List of timestamps where scene changes occur
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps * sample_interval)
    
    scene_changes = []
    prev_frame = None
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % frame_interval == 0:
            # Convert to grayscale and resize for faster processing
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (320, 180))
            
            if prev_frame is not None:
                # Compute frame difference
                diff = cv2.absdiff(prev_frame, gray)
                diff_score = np.mean(diff)
                
                # Detect significant changes (threshold tuned for scene cuts)
                if diff_score > 30:
                    timestamp = frame_idx / fps
                    scene_changes.append(timestamp)
            
            prev_frame = gray
        
        frame_idx += 1
    
    cap.release()
    return scene_changes


def score_audio_energy(
    energy: np.ndarray, 
    energy_times: np.ndarray, 
    start: float, 
    end: float
) -> float:
    """Score a time window based on audio energy."""
    if len(energy) == 0:
        return 0.0
    
    # Get energy values in the window
    mask = (energy_times >= start) & (energy_times <= end)
    window_energy = energy[mask]
    
    if len(window_energy) == 0:
        return 0.0
    
    # Calculate mean and peak relative to overall distribution
    overall_mean = np.mean(energy)
    overall_std = np.std(energy)
    
    window_mean = np.mean(window_energy)
    window_peak = np.max(window_energy)
    
    # Score based on how much above average
    mean_score = max(0, (window_mean - overall_mean) / (overall_std + 1e-6))
    peak_score = max(0, (window_peak - overall_mean) / (overall_std + 1e-6))
    
    # Combine mean and peak (peak is more important)
    score = 0.4 * mean_score + 0.6 * peak_score
    
    return min(100, score * 30)  # Scale to 0-100


def score_scene_density(scene_changes: List[float], start: float, end: float) -> float:
    """Score a time window based on scene change density."""
    if not scene_changes:
        return 0.0
    
    # Count scene changes in window
    changes_in_window = sum(1 for t in scene_changes if start <= t <= end)
    
    duration = end - start
    changes_per_minute = (changes_in_window / duration) * 60
    
    # More scene changes = more dynamic content
    # Typical video has 2-5 scene changes per minute
    score = min(100, changes_per_minute * 15)
    
    return score


def generate_candidate_windows(
    video_duration: float,
    min_duration: float = DEFAULT_MIN_DURATION,
    max_duration: float = DEFAULT_MAX_DURATION,
    step: float = 5.0,
) -> List[Tuple[float, float]]:
    """Generate sliding windows of various durations."""
    windows = []
    
    for duration in [30, 45, 60, 75, 90]:
        if duration < min_duration or duration > max_duration:
            continue
        
        start = 0
        while start + duration <= video_duration:
            windows.append((start, start + duration))
            start += step
    
    return windows


async def detect_moments_from_video(
    video_path: str,
    video_id: str,
    video_duration: float,
    speech_scores: Dict[float, float] = None,
    max_moments: int = DEFAULT_MAX_MOMENTS,
) -> List[Dict[str, Any]]:
    """
    Detect interesting moments using audio energy and scene changes.
    
    Args:
        video_path: Path to video file
        video_id: Video ID for database reference
        video_duration: Total video duration in seconds
        speech_scores: Optional dict mapping timestamps to speech content scores
        max_moments: Maximum number of moments to return
        
    Returns:
        List of moment candidates with scores
    """
    # Extract features
    audio_features = extract_audio_features(video_path)
    scene_changes = detect_scene_changes(video_path)
    
    # Generate candidate windows
    windows = generate_candidate_windows(video_duration)
    
    # Score each window
    scored_windows = []
    
    for start, end in windows:
        # Audio energy score
        audio_score = score_audio_energy(
            audio_features['energy'],
            audio_features['energy_times'],
            start,
            end
        )
        
        # Scene change score
        scene_score = score_scene_density(scene_changes, start, end)
        
        # Speech content score (if provided)
        speech_score = 0.0
        if speech_scores:
            # Average speech scores in this window
            relevant_scores = [
                score for ts, score in speech_scores.items()
                if start <= ts <= end
            ]
            speech_score = np.mean(relevant_scores) if relevant_scores else 0.0
        
        # Combined weighted score
        from backend.config import SCORE_WEIGHTS
        combined_score = (
            audio_score * SCORE_WEIGHTS['audio_energy'] +
            scene_score * SCORE_WEIGHTS['scene_changes'] +
            speech_score * SCORE_WEIGHTS['speech_content']
        )
        
        reason_parts = []
        if audio_score > 50:
            reason_parts.append("High audio energy")
        if scene_score > 50:
            reason_parts.append("Dynamic scenes")
        if speech_score > 50:
            reason_parts.append("Engaging content")
        
        reason = ", ".join(reason_parts) if reason_parts else "Potential moment"
        
        scored_windows.append({
            'start': start,
            'end': end,
            'score': combined_score,
            'audio_score': audio_score,
            'scene_score': scene_score,
            'speech_score': speech_score,
            'reason': reason,
        })
    
    # Sort by score and remove overlaps
    scored_windows.sort(key=lambda x: x['score'], reverse=True)
    
    # Remove overlapping windows (keep highest scoring)
    final_moments = []
    
    for window in scored_windows:
        # Check if this window overlaps with any already selected
        overlaps = False
        for selected in final_moments:
            if not (window['end'] <= selected['start'] or window['start'] >= selected['end']):
                overlaps = True
                break
        
        if not overlaps:
            moment_id = str(uuid.uuid4())
            final_moments.append({
                'id': moment_id,
                'video_id': video_id,
                'start': window['start'],
                'end': window['end'],
                'score': round(window['score'], 2),
                'reason': window['reason'],
                'thumbnail_url': f"/api/thumbnail/{video_id}/{moment_id}",
                'approved': False,
            })
        
        if len(final_moments) >= max_moments:
            break
    
    return final_moments
