"""Context builder for LLM director - assembles Stage 1 data into text log."""
from __future__ import annotations
import logging
from backend.schemas.moment_instruction import Stage1Context

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert viral video editor and content strategist analyzing Russian-language content.

Analyze the provided video context log and identify the most viral-worthy moments for short-form clips (TikTok, YouTube Shorts, Reels).

For each moment provide:
- Exact start/end timestamps
- A compelling hook (what grabs attention in the first 3 seconds)
- Virality score 0-100 based on: emotional peaks, surprising moments, strong reactions, quotable lines
- Content type: reaction/explanation/story/joke/argument
- Subtitle mode: ru_only (default), dual (if language switch detected), original (if already Russian)
- If the speaker switches to another language, provide Russian translation in translated_text
- Camera plan: list of keyframes with face_id to follow and crop center coordinates
- Brief reasoning why this moment is viral

RULES:
- Prefer moments with strong emotional reactions (audio peaks + face reactions)
- Hook must be in first 3 seconds — no slow builds
- Camera plan should follow the speaking person, switch on reactions
- Avoid moments that start/end mid-sentence (use silence segments as boundaries)
- If user instructions exist, prioritize them

Return JSON matching the DirectorOutput schema. Find 3-8 best moments."""


class ContextBuilder:
    """Assembles Stage 1 data into a structured text log for LLM consumption.
    
    Formats transcript, face timeline, and audio peaks into a readable context
    that fits within LLM token limits (~6000 tokens).
    """

    def build_log(self, ctx: Stage1Context, user_instructions: str = "") -> str:
        """Build structured context log from Stage 1 data.
        
        Args:
            ctx: Stage1Context with all assembled data
            user_instructions: Optional user-provided analysis instructions
            
        Returns:
            Structured text log for LLM consumption
        """
        lines = []
        lines.append(f"VIDEO DURATION: {ctx.video_duration:.1f}s")
        lines.append(f"AUDIO: avg_rms={ctx.audio_analysis.avg_rms:.4f}, max_rms={ctx.audio_analysis.max_rms:.4f}")
        lines.append("")

        lines.append("=== TRANSCRIPT ===")
        for seg in ctx.transcript:
            lines.append(f"[{seg.start:.1f}s-{seg.end:.1f}s][{seg.language}] {seg.text}")
        lines.append("")

        lines.append("=== AUDIO PEAKS ===")
        for peak in ctx.audio_analysis.peaks[:50]:  # top 50 peaks
            lines.append(f"[{peak.timestamp:.1f}s] {peak.peak_type} magnitude={peak.magnitude:.3f}")
        lines.append("")

        lines.append("=== FACE TIMELINE ===")
        lines.append(f"Unique speakers/faces: {len(ctx.face_timeline.unique_face_ids)}")
        for frame in ctx.face_timeline.frames[::5]:  # every 5th frame to reduce size
            if frame.faces:
                face_info = ", ".join([
                    f"id={f.track_id} conf={f.confidence:.2f} bbox={[round(x,2) for x in f.bbox]}"
                    for f in frame.faces
                ])
                lines.append(f"[{frame.timestamp:.1f}s] {face_info}")
        lines.append("")

        if user_instructions:
            lines.append("=== USER INSTRUCTIONS ===")
            lines.append(user_instructions)
            lines.append("")

        log = "\n".join(lines)
        token_count = len(log) // 4
        logger.info(f"📝 [Контекст] Собран контекст: {len(log)} символов, ~{token_count} токенов")
        return log


# Global singleton instance
context_builder = ContextBuilder()
