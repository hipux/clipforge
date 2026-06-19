"""Video download service using yt-dlp."""
import logging
import yt_dlp
import uuid
import asyncio
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from backend.config import DOWNLOADS_DIR, TEMP_DIR
from backend.models import VideoInfo

logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    """Detect video platform from URL."""
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "rutube.ru" in url:
        return "rutube"
    elif "vk.com" in url or "vkvideo.ru" in url:
        return "vk"
    elif "twitch.tv" in url:
        return "twitch"
    else:
        raise ValueError(f"Unsupported platform. URL: {url}")


async def download_video(
    url: str, 
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> VideoInfo:
    """
    Download video using yt-dlp with progress updates.
    
    Args:
        url: Video URL from YouTube, Rutube, or VK Video
        progress_callback: Optional callback function for progress updates
        
    Returns:
        VideoInfo object with video metadata
    """
    platform = detect_platform(url)
    video_id = str(uuid.uuid4())
    output_dir = DOWNLOADS_DIR / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_template = str(output_dir / "source.%(ext)s")
    
    def progress_hook(d: Dict[str, Any]):
        """Hook for yt-dlp progress updates."""
        if progress_callback:
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)  # bytes/sec
                eta = d.get('eta', 0)  # seconds
                fragment_index = d.get('fragment_index')
                fragment_count = d.get('fragment_count')
                filename = d.get('filename', '')
                
                percent = (downloaded / total * 100) if total > 0 else 0
                
                # Format speed as human-readable string
                speed_str = ''
                if speed and speed > 0:
                    if speed > 1024 * 1024:  # MiB/s
                        speed_str = f"{speed / (1024 * 1024):.2f} MiB/s"
                    elif speed > 1024:  # KiB/s
                        speed_str = f"{speed / 1024:.2f} KiB/s"
                    else:
                        speed_str = f"{speed:.0f} B/s"
                
                # Format ETA as MM:SS
                eta_str = ''
                if eta and eta > 0:
                    minutes = int(eta // 60)
                    seconds = int(eta % 60)
                    eta_str = f"{minutes:02d}:{seconds:02d}"
                
                progress_callback({
                    'status': 'downloading',
                    'percent': round(percent, 2),
                    'speed': speed_str,
                    'eta': eta_str,
                    'downloaded_bytes': downloaded,
                    'total_bytes': total,
                    'fragment_index': fragment_index,
                    'fragment_count': fragment_count,
                    'filename': filename,
                })
            elif d['status'] == 'finished':
                progress_callback({
                    'status': 'processing',
                    'message': 'Download complete, extracting metadata...'
                })
    
    ydl_opts = {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        'outtmpl': output_template,
        'progress_hooks': [progress_hook],
        'quiet': False,
        'no_warnings': False,
        'extract_flat': False,
        'writethumbnail': True,
        'writesubtitles': False,
    }
    
    # Run yt-dlp in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    
    def download_sync():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info
    
    info = await loop.run_in_executor(None, download_sync)
    
    # Find downloaded video file
    video_files = list(output_dir.glob("source.*"))
    video_file = next((f for f in video_files if f.suffix in ['.mp4', '.mkv', '.webm']), None)
    
    if not video_file:
        raise RuntimeError(f"Video file not found after download in {output_dir}")
    
    # Find thumbnail
    thumbnail_files = list(output_dir.glob("source.*.jpg")) + list(output_dir.glob("source.*.webp"))
    thumbnail_url = f"/files/{video_id}/{thumbnail_files[0].name}" if thumbnail_files else ""
    
    video_info = VideoInfo(
        id=video_id,
        title=info.get('title', 'Unknown Title'),
        duration=float(info.get('duration', 0)),
        thumbnail_url=thumbnail_url,
        file_path=str(video_file),
        platform=platform,
    )
    
    return video_info
