"""YOLOv8n-face detector with BYTETrack for face tracking.

GPU-first: runs on CUDA when available, CPU as fallback.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List
from backend.gpu_config import FACE_MODEL_PATH, FACE_SAMPLE_FPS, FACE_CONFIDENCE_THRESHOLD
from backend.services.vram_manager import vram_manager
from backend.schemas.moment_instruction import FaceDetection, FaceFrame, FaceTimeline

logger = logging.getLogger(__name__)


class FaceDetector:
    """YOLOv8n-face with BYTETrack.
    
    Samples video at specified FPS and tracks faces across frames.
    Automatically unloads model after detection completes.
    """

    def detect_faces_timeline(self, video_path: str) -> FaceTimeline:
        """Detect and track faces throughout video.
        
        Args:
            video_path: Path to video file
            
        Returns:
            FaceTimeline with all face detections and unique track IDs
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
                logger.info("👤 [YOLO] Модель yolov8n-face.pt успешно скачана")
            return YOLO(model_path)

        model = vram_manager.load_model("face", _load)
        load_time = time.time() - load_start
        logger.info(f"👤 [YOLO] Модель загружена за {load_time:.1f}с")

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_interval = max(1, int(fps / FACE_SAMPLE_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sampled_frames_count = total_frames // frame_interval

        frames: List[FaceFrame] = []
        all_track_ids = set()
        frame_idx = 0
        processed_count = 0
        last_log_percent = 0

        logger.info(f"👤 [YOLO] Анализирую кадры ({sampled_frames_count} кадров, каждые 0.5с)...")
        detect_start = time.time()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % frame_interval == 0:
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
                        face_detections.append(FaceDetection(
                            bbox=[x1/w, y1/h, x2/w, y2/h],
                            confidence=float(box.conf[0]),
                            track_id=track_id,
                        ))
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
        
        logger.info(f"👤 [YOLO] Найдено {len(all_track_ids)} уникальных лиц, {len(frames)} треков за {detect_time:.1f}с")
        vram_manager.unload_model("face")
        logger.info(f"👤 [YOLO] Модель выгружена из VRAM")
        return FaceTimeline(frames=frames, unique_face_ids=list(all_track_ids))


# Global singleton instance
face_detector = FaceDetector()
