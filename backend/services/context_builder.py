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
            Structured text log for LLM consumption (truncated to ~6000 tokens)
        """
        MAX_TOKENS = 6000  # Target ~6000 tokens to leave room for system prompt + response
        TOKEN_CHARS = 4  # Approximate characters per token
        MAX_CHARS = MAX_TOKENS * TOKEN_CHARS

        lines = []
        lines.append(f"VIDEO DURATION: {ctx.video_duration:.1f}s")
        lines.append(f"AUDIO: avg_rms={ctx.audio_analysis.avg_rms:.4f}, max_rms={ctx.audio_analysis.max_rms:.4f}")
        lines.append("")

        # Build transcript section (with smart truncation)
        transcript_lines = ["=== TRANSCRIPT ==="]
        total_segments = len(ctx.transcript)
        
        # For long transcripts (>500 segments), sample intelligently
        if total_segments > 500:
            # Keep first 100, last 100, and sample middle 300
            sampled = [
                *ctx.transcript[:100],
                *ctx.transcript[100:-100:max(1, (total_segments - 200) // 300)],
                *ctx.transcript[-100:]
            ]
            transcript_lines.append(f"(Showing {len(sampled)}/{total_segments} segments - sampled for brevity)")
            for seg in sampled:
                transcript_lines.append(f"[{seg.start:.1f}s-{seg.end:.1f}s][{seg.language}] {seg.text[:200]}")
        else:
            for seg in ctx.transcript:
                # Truncate very long text to 300 chars per segment
                text = seg.text if len(seg.text) <= 300 else seg.text[:297] + "..."
                transcript_lines.append(f"[{seg.start:.1f}s-{seg.end:.1f}s][{seg.language}] {text}")
        transcript_lines.append("")

        # Audio peaks - top 50 only
        peaks_lines = ["=== AUDIO PEAKS ==="]
        for peak in ctx.audio_analysis.peaks[:50]:
            peaks_lines.append(f"[{peak.timestamp:.1f}s] {peak.peak_type} magnitude={peak.magnitude:.3f}")
        peaks_lines.append("")

        # Face timeline - significantly reduced sampling
        face_lines = ["=== FACE TIMELINE ==="]
        face_lines.append(f"Unique speakers/faces: {len(ctx.face_timeline.unique_face_ids)}")
        # Sample every 20th frame instead of every 5th for very long videos
        sample_rate = 20 if len(ctx.face_timeline.frames) > 1000 else 5
        for frame in ctx.face_timeline.frames[::sample_rate]:
            if frame.faces:
                face_info = ", ".join([
                    f"id={f.track_id}"
                    for f in frame.faces[:3]  # Max 3 faces per frame
                ])
                face_lines.append(f"[{frame.timestamp:.1f}s] {face_info}")
        face_lines.append("")

        # User instructions
        instructions_lines = []
        if user_instructions:
            instructions_lines = ["=== USER INSTRUCTIONS ===", user_instructions, ""]

        # Combine all sections
        all_lines = lines + transcript_lines + peaks_lines + face_lines + instructions_lines
        log = "\n".join(all_lines)
        
        # Final truncation if still too long
        if len(log) > MAX_CHARS:
            logger.warning(f"📝 [Контекст] Контекст слишком большой ({len(log)} символов), обрезаю транскрипт...")
            # Keep header + peaks + faces, truncate transcript
            header = "\n".join(lines)
            peaks_text = "\n".join(peaks_lines)
            faces_text = "\n".join(face_lines)
            instructions_text = "\n".join(instructions_lines)
            
            reserved = len(header) + len(peaks_text) + len(faces_text) + len(instructions_text) + 100
            transcript_budget = MAX_CHARS - reserved
            
            # Rebuild transcript with budget
            transcript_text = "\n".join(transcript_lines)
            if len(transcript_text) > transcript_budget:
                transcript_text = transcript_text[:transcript_budget] + "\n... (transcript truncated)\n"
            
            log = f"{header}\n{transcript_text}\n{peaks_text}\n{faces_text}\n{instructions_text}"
        
        token_count = len(log) // TOKEN_CHARS
        logger.info(f"📝 [Контекст] Собран контекст: {len(log)} символов, ~{token_count} токенов")
        return log


# Global singleton instance
context_builder = ContextBuilder()
