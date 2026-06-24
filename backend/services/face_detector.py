"""YOLOv8n-face detector with BYTETrack for face tracking.

GPU-first: runs on CUDA when available, CPU as fallback.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict
from backend.gpu_config import FACE_MODEL_PATH, FACE_SAMPLE_FPS, FACE_CONFIDENCE_THRESHOLD
from backend.services.vram_manager import vram_manager
from backend.schemas.moment_instruction import FaceDetection, FaceFrame, FaceTimeline, FacePresenceSegment

logger = logging.getLogger(__name__)

# Filtering constants
MIN_TRACK_FRAMES = 15  # face must persist 7.5s at 2fps — eliminates background/incidental faces
MIN_FACE_HEIGHT_RATIO = 0.05  # face must be >=5% of frame height — eliminates tiny background faces
MAX_UNIQUE_FACES = 150  # cap to prevent CGI over-detection in films like Avatar


class FaceDetector:
    """YOLOv8n-face with BYTETrack.
    
    Samples video at specified FPS and tracks faces across frames.
    Automatically unloads model after detection completes.
    Filters out short tracks and small faces to reduce false positives.
    """

    def detect_faces_timeline(self, video_path: str) -> FaceTimeline:
        """Detect and track faces throughout video.
        
        Args:
            video_path: Path to video file
            
        Returns:
            FaceTimeline with filtered face detections (long tracks, large faces only)
        """
        from ultralytics import YOLO
        import cv2
        import time

        device = vram_manager.device
        
        load_start = time.time()
        logger.info(f"👤 [YOLO] Загрузка YOLOv8n-face (~200 MB VRAM)...")

        def _load():
            model_path = str(FACE_MODEL_PATH)
            if not Path(model_path).exists():
                logger.info("👤 [YOLO] Первая загрузка — скачиваю yolov8n-face.pt (~6 MB)...")
                # Download face-specific model from GitHub release
                import urllib.request
                FACE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
                face_model_url = "https://github.com/akanametov/yolov8-face/releases/download/v0.0.0/yolov8n-face.pt"
                urllib.request.urlretrieve(face_model_url, model_path)
            
            return YOLO(model_path)

        model = vram_manager.load_model("face", _load)
        load_time = time.time() - load_start
        logger.info(f"👤 [YOLO] Модель загружена за {load_time:.1f}с")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0
        frame_interval = max(1, int(fps / FACE_SAMPLE_FPS))
        sampled_frames_count = total_frames // frame_interval

        logger.info(f"👤 [YOLO] Анализирую кадры ({sampled_frames_count} кадров, каждые {1/FACE_SAMPLE_FPS:.1f}с)...")
        
        detect_start = time.time()
        frames: List[FaceFrame] = []
        frame_idx = 0
        processed_count = 0
        last_log_percent = 0
        all_track_ids = set()
        
        # Collect raw detections with tracks
        raw_tracks: Dict[int, List[FaceDetection]] = {}  # track_id -> list of detections
        
        while cap.isOpened():
            # Only fully DECODE frames we actually sample. For skipped frames use
            # grab(), which advances the decoder without the expensive colour
            # conversion + numpy copy that retrieve()/read() perform. Previously
            # every one of the ~54k source frames was decoded just to process
            # every Nth — that made YOLO face detection take ~25 min on a 30-min
            # clip. Skipping decode of non-sampled frames cuts that dramatically.
            if frame_idx % frame_interval != 0:
                if not cap.grab():
                    break
                frame_idx += 1
                continue

            ret, frame = cap.read()
            if not ret:
                break

            if True:
                timestamp = frame_idx / fps
                results = model.track(
                    frame,
                    persist=True,
                    conf=FACE_CONFIDENCE_THRESHOLD,
                    device=device,
                    tracker="bytetrack.yaml",
                    verbose=False,
                )
                
                face_detections: List[FaceDetection] = []
                if results and results[0].boxes is not None:
                    h, w = frame.shape[:2]
                    for box in results[0].boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        track_id = int(box.id[0]) if box.id is not None else None
                        
                        if track_id:
                            all_track_ids.add(track_id)
                            # Normalized bbox
                            detection = FaceDetection(
                                bbox=[x1/w, y1/h, x2/w, y2/h],
                                confidence=float(box.conf[0]),
                                track_id=track_id,
                            )
                            face_detections.append(detection)
                            
                            # Group by track_id for filtering
                            if track_id not in raw_tracks:
                                raw_tracks[track_id] = []
                            raw_tracks[track_id].append(detection)
                
                frames.append(FaceFrame(timestamp=timestamp, faces=face_detections))
                processed_count += 1
                
                # Log progress every 25%
                progress_percent = int((processed_count / sampled_frames_count) * 100)
                if progress_percent >= last_log_percent + 25:
                    logger.info(f"👤 [YOLO] Прогресс: {progress_percent}% ({processed_count}/{sampled_frames_count} кадров)")
                    last_log_percent = progress_percent
            
            frame_idx += 1

        cap.release()
        detect_time = time.time() - detect_start
        
        logger.info(f"👤 [YOLO] Найдено {len(all_track_ids)} сырых треков за {detect_time:.1f}с")
        
        # Apply filtering
        filtered_tracks = self._filter_tracks(raw_tracks)
        
        # Rebuild frames with only valid tracks
        filtered_frames = []
        for frame in frames:
            valid_faces = [f for f in frame.faces if f.track_id in filtered_tracks]
            if valid_faces:  # Only include frames with valid faces
                filtered_frames.append(FaceFrame(
                    timestamp=frame.timestamp,
                    faces=valid_faces
                ))
        
        valid_track_ids = list(filtered_tracks.keys())
        logger.info(
            f"👤 [YOLO] После фильтрации: {len(valid_track_ids)} валидных лиц "
            f"({len(all_track_ids) - len(valid_track_ids)} отброшено)"
        )
        
        vram_manager.unload_model("face")
        logger.info(f"👤 [YOLO] Модель выгружена из VRAM")
        
        return FaceTimeline(frames=filtered_frames, unique_face_ids=valid_track_ids)


    def _build_presence_timeline(self, timeline: FaceTimeline) -> list[FacePresenceSegment]:
        """Build temporal segments when faces are visible.
        
        Instead of counting unique IDs (which explodes due to tracker losing faces),
        we compute time segments when ANY face is visible in frame.
        
        Two frames are considered part of the same segment if they're within 2 seconds.
        
        Args:
            timeline: FaceTimeline with all face detections
            
        Returns:
            List of FacePresenceSegment with start/end times and face count
        """
        if not timeline.frames:
            return []
        
        # Collect all timestamps where at least one face is visible
        face_times = sorted([frame.timestamp for frame in timeline.frames if frame.faces])
        
        if not face_times:
            return []
        
        # Build segments with 2-second gap threshold
        segments = []
        seg_start = face_times[0]
        prev_time = face_times[0]
        frames_in_segment = []
        
        for t in face_times:
            if t - prev_time > 2.0:  # Gap > 2 seconds = new segment
                # Calculate avg face count for this segment
                segment_frames = [f for f in timeline.frames if seg_start <= f.timestamp <= prev_time and f.faces]
                avg_faces = sum(len(f.faces) for f in segment_frames) / len(segment_frames) if segment_frames else 0
                
                segments.append(FacePresenceSegment(
                    start=seg_start,
                    end=prev_time,
                    avg_face_count=round(avg_faces, 1)
                ))
                seg_start = t
                frames_in_segment = []
            
            frames_in_segment.append(t)
            prev_time = t
        
        # Add final segment
        segment_frames = [f for f in timeline.frames if seg_start <= f.timestamp <= prev_time and f.faces]
        avg_faces = sum(len(f.faces) for f in segment_frames) / len(segment_frames) if segment_frames else 0
        
        segments.append(FacePresenceSegment(
            start=seg_start,
            end=prev_time,
            avg_face_count=round(avg_faces, 1)
        ))
        
        return segments

    def _filter_tracks(self, tracks: Dict[int, List[FaceDetection]]) -> Dict[int, List[FaceDetection]]:
        """Filter tracks to remove short tracks and small faces.
        
        Filters:
        1. Minimum track length: >= MIN_TRACK_FRAMES (default 15 frames = 7.5s at 2fps)
        2. Minimum face size: bbox height >= MIN_FACE_HEIGHT_RATIO (default 5% of frame)
        3. Maximum unique faces: <= MAX_UNIQUE_FACES (default 150) to prevent CGI over-detection
        
        Args:
            tracks: Dict mapping track_id to list of FaceDetection
            
        Returns:
            Filtered dict with only valid tracks
        """
        valid_tracks = {}
        
        for track_id, detections in tracks.items():
            # Filter 1: Track must appear in at least MIN_TRACK_FRAMES frames
            if len(detections) < MIN_TRACK_FRAMES:
                continue
            
            # Filter 2: Remove detections where face is too small
            large_detections = []
            for det in detections:
                x1, y1, x2, y2 = det.bbox
                face_height = y2 - y1  # Normalized height (0-1)
                if face_height >= MIN_FACE_HEIGHT_RATIO:
                    large_detections.append(det)
            
            # Track must still have enough frames after size filtering
            if len(large_detections) >= MIN_TRACK_FRAMES:
                valid_tracks[track_id] = large_detections
        
        # Cap at MAX_UNIQUE_FACES most-seen face tracks to prevent CGI over-detection
        if len(valid_tracks) > MAX_UNIQUE_FACES:
            sorted_by_freq = sorted(valid_tracks.items(), key=lambda x: len(x[1]), reverse=True)
            logger.info(f"[YOLO] Capped face tracks from {len(sorted_by_freq)} to {MAX_UNIQUE_FACES}")
            valid_tracks = dict(sorted_by_freq[:MAX_UNIQUE_FACES])
        
        return valid_tracks


# Global singleton instance
face_detector = FaceDetector()