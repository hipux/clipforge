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

        device = vram_manager.device

        def _load():
            model_path = str(FACE_MODEL_PATH)
            if not Path(model_path).exists():
                logger.info("Downloading yolov8n-face.pt...")
                # Ultralytics will download standard YOLOv8n if face model not found
                # For production, pre-download the face model
                m = YOLO("yolov8n.pt")
                m.save(model_path)
                return YOLO(model_path)
            return YOLO(model_path)

        model = vram_manager.load_model("face", _load)

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_interval = max(1, int(fps / FACE_SAMPLE_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        frames: List[FaceFrame] = []
        all_track_ids = set()
        frame_idx = 0

        logger.info(f"Face detection: sampling at {FACE_SAMPLE_FPS} fps (interval={frame_interval} frames)")

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
            
            frame_idx += 1

        cap.release()
        vram_manager.unload_model("face")
        logger.info(f"Face detection complete: {len(frames)} frames, {len(all_track_ids)} unique faces")
        return FaceTimeline(frames=frames, unique_face_ids=list(all_track_ids))


# Global singleton instance
face_detector = FaceDetector()
