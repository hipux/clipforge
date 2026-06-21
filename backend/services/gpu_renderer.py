"""GPU renderer with NVENC hardware encoding and dynamic face-tracking crop.

NVENC-first: uses h264_nvenc when available, libx264 as fallback.
"""
from __future__ import annotations
import logging
import subprocess
from typing import Optional
from backend.gpu_config import NVENC_PRESET, NVENC_CQ, NVENC_RC_LOOKAHEAD
from backend.schemas.moment_instruction import MomentInstruction

logger = logging.getLogger(__name__)


def _has_nvenc() -> bool:
    """Check if FFmpeg supports NVENC encoding."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "h264_nvenc" in result.stdout
    except Exception as e:
        logger.warning(f"NVENC check failed: {e}")
        return False


# Cache NVENC availability at module load time
HAS_NVENC = _has_nvenc()
logger.info(f"NVENC encoding: {'✓ Available' if HAS_NVENC else '✗ Not available (using libx264 fallback)'}")


class GPURenderer:
    """Renders clips with NVENC hardware encoding and dynamic face-tracking crop.
    
    Automatically falls back to libx264 CPU encoding if NVENC unavailable.
    """

    def render_clip(
        self,
        input_path: str,
        output_path: str,
        instruction: MomentInstruction,
        output_width: int = 1080,
        output_height: int = 1920,
    ) -> str:
        """Render a single clip with optional camera movement.
        
        Args:
            input_path: Source video path
            output_path: Destination clip path
            instruction: Moment instruction with camera plan
            output_width: Target width (default 1080 for 9:16)
            output_height: Target height (default 1920 for 9:16)
            
        Returns:
            Output path on success
        """
        duration = instruction.end - instruction.start
        
        # Build video filter chain
        # 1. Scale to fill 9:16 keeping aspect, blur background
        # 2. Dynamic crop following camera_plan keyframes (future enhancement)
        vf = self._build_vfilter(instruction, output_width, output_height)
        
        # Choose encoder
        if HAS_NVENC:
            encoder_args = [
                "-c:v", "h264_nvenc",
                "-preset", NVENC_PRESET,
                "-rc", "vbr_hq",
                "-cq", str(NVENC_CQ),
                "-rc-lookahead", str(NVENC_RC_LOOKAHEAD),
                "-bf", "3",
                "-temporal-aq", "1",
            ]
            logger.info("Encoding with NVENC h264_nvenc")
        else:
            encoder_args = ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]
            logger.info("Encoding with CPU libx264 (NVENC not available)")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(instruction.start),
            "-i", input_path,
            "-t", str(duration),
            "-vf", vf,
            "-c:a", "aac", "-b:a", "192k",
        ] + encoder_args + [output_path]

        logger.info(f"Rendering clip: {instruction.start:.1f}s-{instruction.end:.1f}s → {output_path}")
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"Rendered successfully: {output_path}")
        return output_path

    def _build_vfilter(self, instruction: MomentInstruction, w: int, h: int) -> str:
        """Build FFmpeg video filter for blurred background effect.
        
        Creates a vertical 9:16 composition with:
        - Blurred background filling entire frame
        - Original video centered and scaled to fit
        
        Future: Add dynamic crop following camera_plan keyframes.
        """
        # Blurred background: scale to fill, boxblur
        bg = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:5[bg]"
        
        # Foreground: scale to fit within frame (letterbox)
        fg = f"[0:v]scale={w}:-2[fg]"
        
        # Overlay foreground centered on background
        overlay = f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        
        return f"{bg};{fg};{overlay}"


# Global singleton instance
gpu_renderer = GPURenderer()
