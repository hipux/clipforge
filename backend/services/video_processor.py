"""Video processing pipeline using FFmpeg."""
import logging
import subprocess
import uuid
import asyncio
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from backend.config import OUTPUT_DIR, TEMP_DIR
from backend.models import EffectSettings
from backend.services.speech_scorer import generate_subtitles_file

logger = logging.getLogger(__name__)


def format_time(seconds: float) -> str:
    """Convert seconds to FFmpeg time format (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


async def extract_clip_segment(
    video_path: str,
    start: float,
    end: float,
    output_path: str,
) -> bool:
    """Extract a segment from video without re-encoding (fast)."""
    duration = end - start
    
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output
        '-ss', format_time(start),
        '-i', video_path,
        '-t', format_time(duration),
        '-c', 'copy',  # Copy codec (no re-encoding)
        output_path
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg extraction failed: {stderr.decode()}")
            return False
        
        return True
    
    except Exception as e:
        logger.error(f"Clip extraction error: {e}")
        return False


async def process_clip(
    input_path: str,
    moment_id: str,
    effects: EffectSettings,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Optional[str]:
    """
    Process a video clip with all requested effects.
    
    Args:
        input_path: Path to input clip
        moment_id: Moment ID for output naming
        effects: Effect settings
        progress_callback: Optional callback for progress updates
        
    Returns:
        Path to processed clip, or None on failure
    """
    clip_id = str(uuid.uuid4())
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{clip_id}.mp4"
    
    temp_dir = TEMP_DIR / clip_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Build FFmpeg filter chain
    filters = []
    
    # 1. Blur background (9:16 vertical format)
    if effects.blur_background:
        if progress_callback:
            progress_callback(0.1, "Applying blur background...")
        
        # Create dynamic blurred background:
        # - bg layer: scale up and blur heavily to fill 1080x1920
        # - fg layer: scale original to fit within 1080 width, maintaining aspect ratio
        # - overlay fg centered on bg
        filters.append(
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg];"
            "[0:v]scale=1080:-2[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v1]"
        )
    else:
        filters.append("[0:v]null[v1]")
    
    # 2. Mirror effect
    if effects.mirror:
        if progress_callback:
            progress_callback(0.3, "Applying mirror effect...")
        filters.append("[v1]hflip[v2]")
    else:
        filters.append("[v1]null[v2]")
    
    # 3. Color correction
    if effects.color_correction:
        if progress_callback:
            progress_callback(0.5, "Applying color correction...")
        filters.append("[v2]eq=brightness=0.01:contrast=1.01:saturation=1.02[v3]")
    else:
        filters.append("[v2]null[v3]")
    
    # 4. Subtitles (if enabled)
    subtitle_file = None
    if effects.subtitles:
        if progress_callback:
            progress_callback(0.2, "Generating subtitles...")
        
        subtitle_file = temp_dir / "subtitles.ass"
        success = generate_subtitles_file(input_path, str(subtitle_file))
        
        if success:
            # Escape path for FFmpeg filter
            subtitle_path_escaped = str(subtitle_file).replace('\\', '\\\\').replace(':', '\\:')
            # Modern Shorts/TikTok style: large bold white text, black outline, shadow
            # FontSize=72, Alignment=2 (bottom center), y position offset to bottom area
            filters.append(
                f"[v3]subtitles='{subtitle_path_escaped}':"
                f"force_style='FontName=Arial,FontSize=72,PrimaryColour=&HFFFFFF,"
                f"OutlineColour=&H000000,Outline=4,Shadow=2,Bold=-1,Alignment=2,MarginV=120'[vout]"
            )
        else:
            print("Subtitle generation failed, skipping subtitles")
            filters.append("[v3]null[vout]")
    else:
        filters.append("[v3]null[vout]")
    
    # Combine all filters
    filter_complex = ";".join(filters)
    
    if progress_callback:
        progress_callback(0.7, "Encoding video...")
    
    # Build FFmpeg command
    cmd = [
        'ffmpeg',
        '-y',
        '-i', input_path,
        '-filter_complex', filter_complex,
        '-map', '[vout]',
        '-map', '0:a',  # Copy audio
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        str(output_path)
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode()
            print(f"FFmpeg processing failed: {error_msg}")
            return None
        
        if progress_callback:
            progress_callback(1.0, "Processing complete")
        
        return str(output_path)
    
    except Exception as e:
        print(f"Video processing error: {e}")
        return None


async def process_moment_clip(
    source_video_path: str,
    moment_data: Dict[str, Any],
    effects: EffectSettings,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Process a complete moment: extract segment + apply effects.
    
    Args:
        source_video_path: Path to source video
        moment_data: Moment metadata (id, start, end, etc.)
        effects: Effect settings
        progress_callback: Progress callback
        
    Returns:
        Dict with clip info, or None on failure
    """
    moment_id = moment_data['id']
    start = moment_data['start']
    end = moment_data['end']
    
    # Step 1: Extract clip segment
    if progress_callback:
        progress_callback(0.0, "Extracting clip segment...")
    
    # Ensure temp directory exists
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_clip = TEMP_DIR / f"{moment_id}_raw.mp4"
    
    success = await extract_clip_segment(source_video_path, start, end, str(temp_clip))
    
    if not success:
        return None
    
    if progress_callback:
        progress_callback(0.2, "Segment extracted")
    
    # Step 2: Apply effects
    output_path = await process_clip(
        str(temp_clip),
        moment_id,
        effects,
        progress_callback=lambda p, msg: progress_callback(0.2 + p * 0.8, msg) if progress_callback else None
    )
    
    if output_path is None:
        return None
    
    # Clean up temp file
    try:
        temp_clip.unlink()
    except:
        pass
    
    clip_id = Path(output_path).stem
    # Return only the filename (not full path) for frontend URL construction
    filename = Path(output_path).name
    
    return {
        'id': clip_id,
        'moment_id': moment_id,
        'file_path': filename,  # Just the filename, e.g., "uuid.mp4"
        'status': 'completed',
    }
