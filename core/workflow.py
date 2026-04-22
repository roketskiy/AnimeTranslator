"""Shared translation workflow logic for both CLI and TUI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import config
from core.subtitle_parser import parse_subtitle_file, Subtitle
from core.translator import translate_batch
from core.srt_generator import generate_srt, generate_bilingual_srt, generate_original_srt

log = logging.getLogger(__name__)


def check_api_key() -> bool:
    """Check if API key is configured."""
    return bool(config.API_KEY)


def do_translate(
    subtitles: list[Subtitle],
    src: str,
    dst: str,
    output_path: str,
    original_path: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Translate subtitles and generate output files.
    
    Args:
        subtitles: List of subtitle entries
        src: Source language code
        dst: Target language code
        output_path: Path for translated output
        original_path: Optional path for original subtitle output
        progress_callback: Optional callback(current, total) for progress updates
    """
    texts = [s.text for s in subtitles]
    batch_size = config.TRANSLATE_BATCH_SIZE
    total = len(texts)
    
    results = []
    for i in range(0, total, batch_size):
        batch = texts[i : i + batch_size]
        translated = translate_batch(batch, source_lang=src, target_lang=dst)
        results.extend(translated)
        if progress_callback:
            progress_callback(min(i + batch_size, total), total)

    generate_srt(subtitles, results, output_path)

    if original_path:
        generate_original_srt(subtitles, original_path)


def translate_subtitle_file(
    path: str,
    src: str = "ja",
    dst: str = "zh",
    keep_original: bool = True,
    output_path: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Translate a subtitle file (.srt/.ass).
    
    Returns:
        dict with keys: subtitles_count, output_path, original_path (if applicable)
    """
    p = Path(path)
    if output_path is None:
        output_path = str(p.with_suffix(f".{dst}.srt"))
    
    original_path = str(p.with_suffix(f".{src}.srt")) if keep_original else None
    
    subtitles = parse_subtitle_file(path)
    do_translate(subtitles, src, dst, output_path, original_path, progress_callback)
    
    return {
        "subtitles_count": len(subtitles),
        "output_path": output_path,
        "original_path": original_path,
    }


def translate_soft_subtitle(
    path: str,
    track_index: int | None = None,
    src: str = "ja",
    dst: str = "zh",
    keep_original: bool = True,
    output_path: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Extract and translate soft subtitles from a video file.
    
    Returns:
        dict with keys: subtitles_count, output_path, original_path (if applicable)
    """
    from core.soft_subtitle import extract_soft_subtitle
    
    p = Path(path)
    if output_path is None:
        output_path = str(p.with_suffix(f".{dst}.srt"))
    
    original_path = str(p.with_suffix(f".{src}.srt")) if keep_original else None
    
    subtitles = extract_soft_subtitle(path, track_index=track_index)
    do_translate(subtitles, src, dst, output_path, original_path, progress_callback)
    
    return {
        "subtitles_count": len(subtitles),
        "output_path": output_path,
        "original_path": original_path,
    }


def get_soft_subtitle_tracks(path: str) -> list[dict]:
    """Get list of subtitle tracks from a video file."""
    from core.soft_subtitle import get_subtitle_tracks
    return get_subtitle_tracks(path)


def translate_hard_subtitle(
    path: str,
    src: str = "ja",
    dst: str = "zh",
    output_path: str | None = None,
    bilingual: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Extract hard subtitles via OCR and translate.
    
    Returns:
        dict with keys: subtitles_count, output_path
    """
    from core.hard_subtitle import extract_hard_subtitle
    
    p = Path(path)
    if output_path is None:
        output_path = str(p.with_suffix(".zh.srt"))
    
    subtitles = extract_hard_subtitle(path)
    texts = [s.text for s in subtitles]
    batch_size = config.TRANSLATE_BATCH_SIZE
    total = len(texts)
    
    results = []
    for i in range(0, total, batch_size):
        batch = texts[i : i + batch_size]
        translated = translate_batch(batch, source_lang=src, target_lang=dst)
        results.extend(translated)
        if progress_callback:
            progress_callback(min(i + batch_size, total), total)
    
    if bilingual:
        generate_bilingual_srt(subtitles, results, output_path)
    else:
        generate_srt(subtitles, results, output_path)
    
    return {
        "subtitles_count": len(subtitles),
        "output_path": output_path,
    }


def get_video_info(path: str) -> dict:
    """Get basic video file information."""
    from utils.video import get_video_info as _get_video_info
    
    p = Path(path)
    info = {
        "name": p.name,
        "size": p.stat().st_size if p.exists() else 0,
        "duration": None,
    }
    
    try:
        video_data = _get_video_info(path)
        duration = video_data.get("duration", 0)
        if duration:
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            info["duration"] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        pass
    
    return info


def get_subtitle_info(path: str) -> dict:
    """Get basic subtitle file information."""
    p = Path(path)
    info = {
        "name": p.name,
        "size": p.stat().st_size if p.exists() else 0,
        "format": p.suffix.lower(),
        "encoding": "utf-8",
    }
    
    try:
        subtitles = parse_subtitle_file(path)
        info["count"] = len(subtitles)
    except Exception:
        info["count"] = 0
    
    return info
