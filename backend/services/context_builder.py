"""Context builder for LLM director - assembles Stage 1 data into text log."""
from __future__ import annotations
import logging
from backend.schemas.moment_instruction import Stage1Context

logger = logging.getLogger(__name__)


def build_system_prompt(min_duration: int, max_duration: int, max_moments: int, user_instructions: str = "") -> str:
    """Build the LLM system prompt, injecting the user's Detection Settings
    (clip duration range + max moments) and optional AI instructions."""
    instr = (user_instructions or "").strip()
    instr_block = (
        f"\nUSER INSTRUCTIONS (highest priority):\n{instr}\n" if instr else ""
    )
    return (
        "You are an expert viral video editor and content strategist analyzing Russian-language content.\n\n"
        "Analyze the provided video context log and identify the most viral-worthy moments for "
        "short-form clips (TikTok, YouTube Shorts, Reels).\n\n"
        "RULES:\n"
        f"- Each moment MUST be a self-contained clip lasting between {min_duration} and {max_duration} seconds "
        f"(end - start >= {min_duration}). Never output moments shorter than {min_duration}s or longer than {max_duration}s.\n"
        "- start and end are ABSOLUTE seconds in the source video (use the [12.3s-45.6s] timestamps shown in the TRANSCRIPT section).\n"
        "- Hook must be in the first 3 seconds - no slow builds.\n"
        "- Do not start/end mid-sentence; align to silence/segment boundaries.\n"
        "- virality_score is REQUIRED for every moment: an integer 0-100 reflecting real viral potential (vary it, do not output a flat 50).\n"
        "- THINK FIRST inside the \"reasoning\" field (it MUST be the first field): identify the self-contained idea, its hook and resolution, then derive start/end/virality_score from that analysis. This reasoning is what makes the selection good - do not skip it.\n"
        "- A clip must make sense WITHOUT prior context: it should open by establishing who/what is happening so a cold viewer understands within the first seconds.\n"
        "- camera_plan should follow the speaking person and switch on reactions.\n"
        + instr_block +
        "\nReturn ONLY valid JSON matching this exact schema (use these EXACT field names):\n"
        '{\n'
        '  "moments": [\n'
        '    {\n'
        '      "reasoning": "FIRST analyze: what is the self-contained idea/story, where is its hook, why would a viewer stop scrolling? Decide start/end/score FROM this.",\n'
        '      "hook": "short attention-grabbing description",\n'
        '      "start": 12.5,\n'
        '      "end": 34.0,\n'
        '      "virality_score": 82,\n'
        '      "content_type": "reaction|explanation|story|joke|argument",\n'
        '      "subtitle_mode": "ru_only",\n'
        '      "translated_text": null,\n'
        '      "camera_plan": [\n'
        '        {"time": 0.0, "target_face_id": 1, "crop_center_x": 0.5, "crop_center_y": 0.4, "transition": "smooth"}\n'
        '      ]\n'
        '    }\n'
        '  ],\n'
        '  "total_analyzed": 8,\n'
        '  "language_detected": "ru"\n'
        '}\n'
        f"\nFind UP TO {max_moments} genuinely viral moments, best first. "
        "QUALITY OVER QUANTITY: do NOT pad the list to reach the maximum. "
        "It is far better to return 3 excellent moments than many mediocre ones. "
        "Only include a moment if it can stand alone as a compelling short clip."
    )


class ContextBuilder:
    """Assembles Stage 1 data into a structured text log for LLM consumption.
    
    Formats transcript, face timeline, and audio peaks into a readable context
    that fits within LLM token limits (~6000 tokens).
    """

    def build_chunks(
        self,
        ctx: Stage1Context,
        user_instructions: str = "",
        max_tokens_per_chunk: int = 4000
    ) -> list[str]:
        """Build content-aware chunks for long videos.

        Chunks are sized by ACTUAL transcript density, not by a fixed time
        estimate. We greedily pack transcript segments until the next one would
        exceed the per-chunk token budget, then start a new chunk at a segment
        boundary. Dense speech simply produces MORE chunks instead of having its
        transcript truncated (which silently dropped content and moments).

        Args:
            ctx: Stage1Context with all assembled data
            user_instructions: Optional user-provided analysis instructions
            max_tokens_per_chunk: Maximum tokens per chunk (default 4000)

        Returns:
            List of context log strings, one per chunk
        """
        TOKEN_CHARS = 2  # Cyrillic-safe (see notes below)
        MAX_CHARS = max_tokens_per_chunk * TOKEN_CHARS
        # Reserve room for the non-transcript sections (header, audio peaks,
        # face timeline, user instructions) so the transcript itself never
        # overflows the budget and triggers truncation.
        RESERVE_CHARS = 2600 + (len(user_instructions) if user_instructions else 0)
        transcript_budget = max(1000, MAX_CHARS - RESERVE_CHARS)

        segs = sorted(ctx.transcript, key=lambda s: s.start)

        # Compute time boundaries by packing transcript lines up to the budget.
        boundaries: list[tuple[float, float]] = []
        if not segs:
            boundaries = [(0.0, ctx.video_duration)]
        else:
            cur_start = 0.0
            cur_chars = 0
            for seg in segs:
                text = seg.text if len(seg.text) <= 300 else seg.text[:297] + "..."
                line_len = len(f"[{seg.start:.1f}s-{seg.end:.1f}s][{seg.language}] {text}") + 1
                if cur_chars + line_len > transcript_budget and cur_chars > 0:
                    boundaries.append((cur_start, seg.start))
                    cur_start = seg.start
                    cur_chars = 0
                cur_chars += line_len
            boundaries.append((cur_start, ctx.video_duration))

        num_chunks = len(boundaries)
        video_duration_min = ctx.video_duration / 60.0
        logger.info(f"📝 [Контекст] Видео {video_duration_min:.1f} мин → {num_chunks} чанков (по плотности речи)")
        logger.info(f"📝 [Контекст] Бюджет транскрипта: ~{transcript_budget // TOKEN_CHARS} токенов/чанк (макс {max_tokens_per_chunk})")

        chunks = []
        for i, (chunk_start, chunk_end) in enumerate(boundaries):
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
        TOKEN_CHARS = 2  # Cyrillic-safe (see build_chunks)
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
            for peak in chunk_peaks[:25]:  # Max 25 peaks per chunk (keep token budget for transcript)
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
            sample_rate = max(1, len(chunk_frames) // 25)  # Max 25 frames per chunk
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
        
        # Hard limit: TRANSCRIPT is the most important signal and must never be
        # cut. If the chunk is still too large, trim the less-critical peaks and
        # face sections instead.
        if len(log) > MAX_CHARS:
            logger.warning(f"📝 [Контекст] Чанк {chunk_num} великоват ({len(log)} символов), сжимаю пики/лица (транскрипт сохраняю)...")
            header = "\n".join(lines)
            transcript_text = "\n".join(transcript_lines)
            instructions_text = "\n".join(instructions_lines)
            peaks_text = "\n".join(peaks_lines)
            faces_text = "\n".join(face_lines)
            budget_left = MAX_CHARS - len(header) - len(transcript_text) - len(instructions_text) - 100
            if budget_left < 0:
                budget_left = 0
            half = budget_left // 2
            if len(peaks_text) > half:
                peaks_text = peaks_text[:half] + "\n... (пики обрезаны)\n"
            if len(faces_text) > half:
                faces_text = faces_text[:half] + "\n... (лица обрезаны)\n"
            log = f"{header}\n{transcript_text}\n{peaks_text}\n{faces_text}\n{instructions_text}"
        
        return log


# Global singleton instance
context_builder = ContextBuilder()