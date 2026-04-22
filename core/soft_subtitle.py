from __future__ import annotations

import subprocess
import json
import re
from pathlib import Path

from core.subtitle_parser import Subtitle


def get_subtitle_tracks(video_path: str) -> list[dict]:
    info = _ffprobe(video_path)
    tracks = []
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "subtitle":
            tracks.append({
                "index": stream["index"],
                "codec": stream.get("codec_name", "unknown"),
                "language": stream.get("tags", {}).get("language", "und"),
                "title": stream.get("tags", {}).get("title", ""),
            })
    return tracks


def extract_soft_subtitle(video_path: str, track_index: int | None = None) -> list[Subtitle]:
    tracks = get_subtitle_tracks(video_path)
    if not tracks:
        raise RuntimeError(f"No subtitle tracks found in {video_path}")

    if track_index is not None:
        chosen = None
        for t in tracks:
            if t["index"] == track_index:
                chosen = t
                break
        if chosen is None:
            raise ValueError(f"Track index {track_index} not found. Available: {tracks}")
    else:
        chosen = _pick_best_track(video_path, tracks)

    import tempfile
    import os

    ext = ".srt" if chosen["codec"] in ("subrip", "srt") else ".ass"
    if chosen["codec"] == "ass":
        ext = ".ass"

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, f"sub{ext}")
        _extract_track(video_path, chosen["index"], out_path)

        if chosen["codec"] in ("subrip", "srt"):
            from core.subtitle_parser import parse_srt
            subs = parse_srt(out_path)
        elif chosen["codec"] in ("ass", "ssa"):
            from core.subtitle_parser import parse_ass
            subs = parse_ass(out_path)
        else:
            out_srt = os.path.join(tmpdir, "sub.srt")
            _convert_to_srt(video_path, chosen["index"], out_srt)
            from core.subtitle_parser import parse_srt
            subs = parse_srt(out_srt)

    return subs


def _pick_best_track(video_path: str, tracks: list[dict]) -> dict:
    for lang in ("jpn", "ja", "eng", "en"):
        for t in tracks:
            if t["language"].lower().startswith(lang[:2]):
                return t
    return tracks[0]


def _extract_track(video_path: str, stream_index: int, out_path: str) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-map", f"0:{stream_index}",
        "-f", _format_for_path(out_path),
        out_path,
    ]
    _run_ffmpeg(cmd)


def _convert_to_srt(video_path: str, stream_index: int, out_path: str) -> None:
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-map", f"0:{stream_index}",
        "-f", "srt",
        out_path,
    ]
    _run_ffmpeg(cmd)


def _ffprobe(video_path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")


def _format_for_path(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".ass":
        return "ass"
    return "srt"