from __future__ import annotations

import os
import shutil
import subprocess
import json
import tempfile
from pathlib import Path


def _check_ffmpeg() -> None:
    """Check if ffmpeg/ffprobe are available, raise friendly error if not."""
    for cmd in ("ffmpeg", "ffprobe"):
        result = subprocess.run(
            ["where", cmd] if os.name == "nt" else ["which", cmd],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{cmd} not found. Please install FFmpeg and add it to PATH. "
                f"Download: https://www.gyan.dev/ffmpeg/builds/"
            )


def get_video_info(video_path: str) -> dict:
    _check_ffmpeg()
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    return {
        "duration": float(fmt.get("duration", 0)),
        "streams": data.get("streams", []),
    }


def get_frames(video_path: str, fps: float = 1.0, region: tuple | None = None, output_dir: str | None = None) -> tuple[list[str], str]:
    _check_ffmpeg()
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="animetrans_frames_")

    vf_parts = [f"fps={fps}"]
    if region:
        x0, y0, x1, y1 = region
        crop_w = f"iw*{x1 - x0:.2f}"
        crop_h = f"ih*{y1 - y0:.2f}"
        crop_x = f"iw*{x0:.2f}"
        crop_y = f"ih*{y0:.2f}"
        vf_parts.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")

    vf = ",".join(vf_parts)
    out_pattern = os.path.join(output_dir, "frame_%06d.png")

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", vf,
        out_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed: {result.stderr}")

    frames = sorted(Path(output_dir).glob("frame_*.png"))
    return [str(f) for f in frames], output_dir


def list_subtitle_tracks(video_path: str) -> list[dict]:
    from core.soft_subtitle import get_subtitle_tracks
    return get_subtitle_tracks(video_path)