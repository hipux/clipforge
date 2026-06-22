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

    def build_chunks(
        self,
        ctx: Stage1Context,
        user_instructions: str = "",
        max_tokens_per_chunk: int = 6000
    ) -> list[str]:
        """Build dynamic time-based chunks for long videos.
        
        Divides video into time windows, each generating a chunk ≤ max_tokens_per_chunk.
        
        Args:
            ctx: Stage1Context with all assembled data
            user_instructions: Optional user-provided analysis instructions
            max_tokens_per_chunk: Maximum tokens per chunk (default 6000)
            
        Returns:
            List of context log strings, one per time chunk
        """
        TOKEN_CHARS = 4  # Approximate characters per token
        TOKENS_PER_MIN = 400  # Estimate: 400 tokens per minute of speech
        
        video_duration_min = ctx.video_duration / 60.0
        
        # Calculate chunk duration
        chunk_duration_min = max_tokens_per_chunk / TOKENS_PER_MIN
        num_chunks = max(1, int((video_duration_min / chunk_duration_min) + 0.5))  # Round up
        
        # Recalculate exact chunk duration to evenly divide video
        chunk_duration_sec = ctx.video_duration / num_chunks
        
        logger.info(f"📝 [Контекст] Видео {video_duration_min:.1f} мин → {num_chunks} чанков по {chunk_duration_sec/60:.1f} мин")
        logger.info(f"📝 [Контекст] Ожидаемо ~{max_tokens_per_chunk} токенов на чанк, макс {max_tokens_per_chunk}")
        
        chunks = []
        for i in range(num_chunks):
            chunk_start = i * chunk_duration_sec
            chunk_end = min((i + 1) * chunk_duration_sec, ctx.video_duration)
            
            chunk_log = self._build_chunk_log(
                ctx,
                chunk_start,
                chunk_end,
                i + 1,
                num_chunks,
                user_instructions,
                max_tokens_per_chunk
            )
            chunks.append(chunk_log)
            
            token_count = len(chunk_log) // TOKEN_CHARS
            logger.info(f"📝 [Контекст] Чанк {i+1}/{num_chunks} ({chunk_start/60:.1f}-{chunk_end/60:.1f} мин): {len(chunk_log)} символов, ~{token_count} токенов")
        
        return chunks

    def _build_chunk_log(
        self,
        ctx: Stage1Context,
        start_sec: float,
        end_sec: float,
        chunk_num: int,
        total_chunks: int,
        user_instructions: str,
        max_tokens: int
    ) -> str:
        """Build context log for a single time chunk.
        
        Args:
            ctx: Stage1Context with all data
            start_sec: Chunk start time (seconds)
            end_sec: Chunk end time (seconds)
            chunk_num: Current chunk number (1-indexed)
            total_chunks: Total number of chunks
            user_instructions: User instructions (included in all chunks)
            max_tokens: Maximum tokens for this chunk
            
        Returns:
            Context log string for this time window
        """
        TOKEN_CHARS = 4
        MAX_CHARS = max_tokens * TOKEN_CHARS
        
        lines = []
        lines.append(f"=== CHUNK {chunk_num}/{total_chunks} ===")
        lines.append(f"TIME WINDOW: {start_sec:.1f}s - {end_sec:.1f}s ({start_sec/60:.1f} - {end_sec/60:.1f} мин)")
        lines.append(f"VIDEO DURATION: {ctx.video_duration:.1f}s")
        lines.append(f"AUDIO: avg_rms={ctx.audio_analysis.avg_rms:.4f}, max_rms={ctx.audio_analysis.max_rms:.4f}")
        lines.append("")

        # Filter transcript segments in time window
        transcript_lines = ["=== TRANSCRIPT ==="]
        chunk_segments = [
            seg for seg in ctx.transcript
            if seg.start < end_sec and seg.end > start_sec
        ]
        
        if chunk_segments:
            for seg in chunk_segments:
                text = seg.text if len(seg.text) <= 300 else seg.text[:297] + "..."
                transcript_lines.append(f"[{seg.start:.1f}s-{seg.end:.1f}s][{seg.language}] {text}")
        else:
            transcript_lines.append("(No speech in this segment)")
        transcript_lines.append("")

        # Filter audio peaks in time window
        peaks_lines = ["=== AUDIO PEAKS ==="]
        chunk_peaks = [
            peak for peak in ctx.audio_analysis.peaks
            if start_sec <= peak.timestamp < end_sec
        ]
        
        if chunk_peaks:
            for peak in chunk_peaks[:50]:  # Max 50 peaks per chunk
                peaks_lines.append(f"[{peak.timestamp:.1f}s] {peak.peak_type} magnitude={peak.magnitude:.3f}")
        else:
            peaks_lines.append("(No significant audio activity)")
        peaks_lines.append("")

        # Filter face timeline in time window
        face_lines = ["=== FACE TIMELINE ==="]
        chunk_frames = [
            frame for frame in ctx.face_timeline.frames
            if start_sec <= frame.timestamp < end_sec
        ]
        
        if chunk_frames:
            # Sample to keep token count down
            sample_rate = max(1, len(chunk_frames) // 50)  # Max 50 frames per chunk
            for frame in chunk_frames[::sample_rate]:
                if frame.faces:
                    face_info = ", ".join([
                        f"id={f.track_id}"
                        for f in frame.faces[:3]
                    ])
                    face_lines.append(f"[{frame.timestamp:.1f}s] {face_info}")
        else:
            face_lines.append("(No faces detected in this segment)")
        face_lines.append("")

        # User instructions (same for all chunks)
        instructions_lines = []
        if user_instructions:
            instructions_lines = ["=== USER INSTRUCTIONS ===", user_instructions, ""]

        # Combine sections
        all_lines = lines + transcript_lines + peaks_lines + face_lines + instructions_lines
        log = "\n".join(all_lines)
        
        # Hard limit: if chunk still exceeds max_chars, trim transcript
        if len(log) > MAX_CHARS:
            logger.warning(f"📝 [Контекст] Чанк {chunk_num} слишком большой ({len(log)} символов), обрезаю транскрипт...")
            header = "\n".join(lines)
            peaks_text = "\n".join(peaks_lines)
            faces_text = "\n".join(face_lines)
            instructions_text = "\n".join(instructions_lines)
            
            reserved = len(header) + len(peaks_text) + len(faces_text) + len(instructions_text) + 100
            transcript_budget = MAX_CHARS - reserved
            
            transcript_text = "\n".join(transcript_lines)
            if len(transcript_text) > transcript_budget:
                transcript_text = transcript_text[:transcript_budget] + "\n... (transcript truncated to fit token limit)\n"
            
            log = f"{header}\n{transcript_text}\n{peaks_text}\n{faces_text}\n{instructions_text}"
        
        return log


# Global singleton instance
context_builder = ContextBuilder()
