"""YOLOv8n-face detector with batched GPU inference + greedy-IoU tracking.

GPU-first: runs on CUDA when available, CPU as fallback. Frames are sampled and
run through YOLO in batches (high GPU throughput) instead of one-frame-at-a-time
stateful tracking; identities are recovered with a cheap IoU tracker.

The big bug-fix vs the old code: people walking in and out of frame used to
get a brand-new `track_id` every ~2 seconds because `MAX_TRACK_GAP=4` was
too aggressive. With ~30 people orbiting across a movie, that produced
150+ unique track IDs which then broke the face-identity clusterer
(face_identity.py) on the #5 feature. The two filters below
(MIN_BBOX_AREA + MIN_DETECTIONS_PER_TRACK) drop poster/watermark
artifacts and one-frame ghosts, and the raised MAX_TRACK_GAP keeps
real identities stable across short occlusions.
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import List, Dict
from backend.gpu_config import (
    FACE_MODEL_PATH, FACE_SAMPLE_FPS, FACE_CONFIDENCE_THRESHOLD,
    MIN_BBOX_AREA, MIN_DETECTIONS_PER_TRACK,
)
from backend.services.vram_manager import vram_manager
from backend.schemas.moment_instruction import FaceDetection, FaceFrame, FaceTimeline, FacePresenceSegment

logger = logging.getLogger(__name__)

# Filtering constants — kept as module-level defaults the operator CAN
# still override via env vars above.
# MIN_TRACK_FRAMES is now duration-based instead of frame-count: at the
# default 1fps sample rate this means a face must persist for 7 seconds
# before it counts; at 2fps that would be 3.5s. A talking-head clip has
# most speakers visible for tens of seconds, so 7s is a safe floor that
# still kills frame-ghost artefacts.
MIN_TRACK_SECONDS = 7.0
MIN_FACE_HEIGHT_RATIO = 0.05  # face must be >=5% of frame height — eliminates tiny background faces
MAX_UNIQUE_FACES = 8  # cap to prevent CGI over-detection in films like Avatar.
                          # 8 is the practical upper bound for ANY foot-pointing video
                          # (panel shows, talk shows, movies); the clusterer handles the rest.

# ── Batched-inference tuning ────────────────────────────────────────────────
# The detector previously called model.track() one frame at a time (batch=1),
# which keeps the GPU mostly idle while CPU runs BYTETrack + per-call overhead.
# We now run YOLO in BATCHED detect mode and recover identities with a cheap
# greedy-IoU tracker, which is far more GPU-efficient.
FACE_IMGSZ = 480        # < YOLO's 640 default; faces are large -> ~2x faster
FACE_BATCH = 32         # frames per GPU inference call (throughput, not latency)
FACE_IOU_MATCH = 0.4    # bumped from 0.3 — looser thresholds leak transient
                        # detections into wrong tracks (yields 150+ IDs).
                        # 0.4 = "almost the same bbox size + location".
MAX_TRACK_GAP = 12      # bumped from 4 (~2s) → ~12s on overshoot, so a face
                        # briefly hidden by a passing object or camera cut
                        # keeps its identity instead of minting a new one.


def _iou(a, b) -> float:
    """Intersection-over-union of two (x1, y1, x2, y2) boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class FaceDetector:
    """YOLOv8n-face with batched inference + greedy-IoU tracking.
    
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
        import subprocess as _sp
        import numpy as _np

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

        # ── Probe metadata with OpenCV (cheap), then decode via ffmpeg/NVDEC ──
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()  # frames are decoded by ffmpeg (NVDEC), not OpenCV
        duration = total_frames / fps if fps > 0 else 0
        sampled_frames_count = max(1, int(duration * FACE_SAMPLE_FPS))

        logger.info(f"👤 [YOLO] Анализирую кадры ({sampled_frames_count} кадров, каждые {1/FACE_SAMPLE_FPS:.1f}с)...")
        
        detect_start = time.time()
        frames: List[FaceFrame] = []
        all_track_ids = set()
        raw_tracks: Dict[int, List[FaceDetection]] = {}  # track_id -> detections

        use_half = str(device).startswith("cuda")

        # ── Cheap greedy-IoU tracker (replaces per-frame BYTETrack) ──────────
        active_tracks: List[dict] = []  # {id, bbox, last_sample}
        next_track_id = 1

        def assign_tracks(boxes, sample_no):
            nonlocal next_track_id
            assigned = []
            used = set()
            for bbox in boxes:
                best_iou, best_j = 0.0, -1
                for j, tr in enumerate(active_tracks):
                    if j in used:
                        continue
                    iou = _iou(bbox, tr["bbox"])
                    if iou > best_iou:
                        best_iou, best_j = iou, j
                if best_j >= 0 and best_iou >= FACE_IOU_MATCH:
                    tr = active_tracks[best_j]
                    tr["bbox"] = bbox
                    tr["last_sample"] = sample_no
                    used.add(best_j)
                    assigned.append(tr["id"])
                else:
                    tid = next_track_id
                    next_track_id += 1
                    active_tracks.append({"id": tid, "bbox": bbox, "last_sample": sample_no})
                    used.add(len(active_tracks) - 1)
                    assigned.append(tid)
            # Drop stale tracks so IDs don't bleed across scene cuts.
            active_tracks[:] = [t for t in active_tracks
                                if sample_no - t["last_sample"] <= MAX_TRACK_GAP]
            return assigned

        batch_frames: list = []
        batch_meta: list = []  # (timestamp, h, w)
        sample_no = 0
        last_log_percent = 0

        def run_batch():
            nonlocal sample_no, last_log_percent, _t_infer
            if not batch_frames:
                return
            _t0 = time.perf_counter()
            results = model.predict(
                batch_frames,
                conf=FACE_CONFIDENCE_THRESHOLD,
                imgsz=FACE_IMGSZ,
                half=use_half,
                device=device,
                verbose=False,
            )
            _t_infer += time.perf_counter() - _t0
            for res, (timestamp, h, w) in zip(results, batch_meta):
                boxes_norm = []
                if res.boxes is not None:
                    for box in res.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        bw = (x2 - x1) / w
                        bh = (y2 - y1) / h
                        # Drop tiny boxes — usually logos, watermarks,
                        # and animations artefacts that YOLO fires on at
                        # conf 0.55+. Real faces in a talking-head clip occupy
                        # >=3% of the frame, almost always >1%.
                        if bw * bh < MIN_BBOX_AREA:
                            continue
                        boxes_norm.append(
                            (x1 / w, y1 / h, x2 / w, y2 / h, float(box.conf[0]))
                        )
                ids = assign_tracks([b[:4] for b in boxes_norm], sample_no)
                face_detections: List[FaceDetection] = []
                for bx, tid in zip(boxes_norm, ids):
                    detection = FaceDetection(
                        bbox=[bx[0], bx[1], bx[2], bx[3]],
                        confidence=bx[4],
                        track_id=tid,
                    )
                    face_detections.append(detection)
                    all_track_ids.add(tid)
                    raw_tracks.setdefault(tid, []).append(detection)
                frames.append(FaceFrame(timestamp=timestamp, faces=face_detections))
                sample_no += 1
            batch_frames.clear()
            batch_meta.clear()
            progress_percent = int((sample_no / max(1, sampled_frames_count)) * 100)
            if progress_percent >= last_log_percent + 25:
                logger.info(
                    f"👤 [YOLO] Прогресс: {progress_percent}% "
                    f"({sample_no}/{sampled_frames_count} кадров)"
                )
                last_log_percent = progress_percent

        _t_decode = 0.0
        _t_infer = 0.0
        frame_bytes = width * height * 3

        def _build_ffmpeg_cmd(use_gpu):
            cmd = ["ffmpeg", "-nostdin", "-loglevel", "error"]
            if use_gpu:
                cmd += ["-hwaccel", "cuda"]
            cmd += [
                "-i", video_path,
                "-vf", f"fps={FACE_SAMPLE_FPS}",
                "-pix_fmt", "bgr24",
                "-f", "rawvideo",
                "pipe:1",
            ]
            return cmd

        def _iter_frames():
            # GPU(NVDEC) decode first; fall back to CPU ffmpeg if it yields nothing.
            nonlocal _t_decode
            use_gpu_first = str(device).startswith("cuda")
            for attempt, use_gpu in enumerate((use_gpu_first, False)):
                if attempt == 1 and not use_gpu_first:
                    pass  # CPU already tried as first attempt; skip duplicate
                proc = _sp.Popen(
                    _build_ffmpeg_cmd(use_gpu),
                    stdout=_sp.PIPE, stderr=_sp.PIPE,
                    stdin=_sp.DEVNULL, bufsize=frame_bytes * 4,
                )
                got_any = False
                try:
                    while True:
                        _t0 = time.perf_counter()
                        buf = proc.stdout.read(frame_bytes)
                        _t_decode += time.perf_counter() - _t0
                        if not buf or len(buf) < frame_bytes:
                            break
                        got_any = True
                        # writable copy so YOLO preprocessing won't complain
                        yield _np.frombuffer(buf, _np.uint8).reshape(
                            (height, width, 3)
                        ).copy()
                finally:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait()
                if got_any:
                    return
                if use_gpu:
                    logger.warning("👤 [YOLO] NVDEC-декод не дал кадров, фолбэк на CPU ffmpeg")
            raise RuntimeError(f"ffmpeg failed to decode frames from {video_path}")

        sample_index = 0
        for frame in _iter_frames():
            timestamp = sample_index / FACE_SAMPLE_FPS
            batch_frames.append(frame)
            batch_meta.append((timestamp, height, width))
            if len(batch_frames) >= FACE_BATCH:
                run_batch()
            sample_index += 1

        run_batch()  # flush remaining frames
        detect_time = time.time() - detect_start
        logger.info(f"⏱️ [YOLO] Декод видео: {_t_decode:.1f}с | Инференс YOLO: {_t_infer:.1f}с | Общее: {detect_time:.1f}с")
        
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
        """Filter face tracks to remove noise and limit total count.

        Filters (in order):
          1. MIN_DETECTIONS_PER_TRACK  — drop one-frame ghosts (a bbox the
             model only fires on once or twice is almost certainly noise).
          2. Min duration  — track must span at least MIN_TRACK_SECONDS
             (default 7 s), calibrated against FACE_SAMPLE_FPS so it works
             at any sample rate without further tuning.
          3. Min bbox height — drop tracks whose faces are <5% of frame
             height (background/posters that pass step 1 by accident).
          4. Top-N by frequency — cap at MAX_UNIQUE_FACES (default 8). Most
             visible tracks; the face-identity clusterer merges siblings.

        Args:
            tracks: Dict mapping track_id to list of FaceDetection

        Returns:
            Filtered dict with only valid tracks
        """
        valid_tracks = {}

        # Each sampled frame is ~1/FACE_SAMPLE_FPS seconds apart. Compute a
        # frame-count equivalent of MIN_TRACK_SECONDS.
        min_frames_for_min_seconds = max(
            1, int(MIN_TRACK_SECONDS * FACE_SAMPLE_FPS)
        )
        min_frames_to_keep = max(MIN_DETECTIONS_PER_TRACK,
                                 min_frames_for_min_seconds)

        for track_id, detections in tracks.items():
            # Filter 1: minimum number of detections across the video.
            if len(detections) < MIN_DETECTIONS_PER_TRACK:
                continue
            # Filter 2: persistence across enough seconds (a talking head
            # gets re-detected every sample for the duration; an artefact
            # fires once or twice).
            if len(detections) < min_frames_to_keep:
                continue

            # Filter 3: drop detections whose face is too small (relative to
            # frame area) — background extras that passed the model threshold
            # by sheer luck.
            large_detections = []
            for det in detections:
                x1, y1, x2, y2 = det.bbox
                face_height = y2 - y1
                if face_height >= MIN_FACE_HEIGHT_RATIO:
                    large_detections.append(det)

            if not large_detections:
                continue
            valid_tracks[track_id] = large_detections

        # Filter 4: cap to the MAX_UNIQUE_FACES most-frequent tracks so the
        # downstream identity clusterer has a sane upper bound on cluster
        # candidates (a 31-min movie with 200 extras will otherwise run
        # face_identity for hours).
        if len(valid_tracks) > MAX_UNIQUE_FACES:
            sorted_by_freq = sorted(
                valid_tracks.items(),
                key=lambda x: len(x[1]),
                reverse=True,
            )
            logger.info(
                f"[YOLO] Capping face tracks from {len(sorted_by_freq)} "
                f"to {MAX_UNIQUE_FACES} (kept the most-persistent ones)."
            )
            valid_tracks = dict(sorted_by_freq[:MAX_UNIQUE_FACES])

        return valid_tracks
        
        return valid_tracks


# Global singleton instance
face_detector = FaceDetector()