from __future__ import annotations

import config
from core.subtitle_parser import Subtitle


def generate_srt(subtitles: list[Subtitle], translations: list[str], output_path: str) -> None:
    lines: list[str] = []
    for i, sub in enumerate(subtitles):
        start = _ms_to_srt_time(sub.start_ms)
        end = _ms_to_srt_time(sub.end_ms)
        text = translations[i] if i < len(translations) else sub.text
        lines.append(str(i + 1))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")

    with open(output_path, "w", encoding=config.OUTPUT_ENCODING) as f:
        f.write("\n".join(lines))


def generate_bilingual_srt(subtitles: list[Subtitle], translations: list[str], output_path: str) -> None:
    lines: list[str] = []
    for i, sub in enumerate(subtitles):
        start = _ms_to_srt_time(sub.start_ms)
        end = _ms_to_srt_time(sub.end_ms)
        text = translations[i] if i < len(translations) else sub.text
        lines.append(str(i + 1))
        lines.append(f"{start} --> {end}")
        lines.append(f"{sub.text}\n{text}")
        lines.append("")

    with open(output_path, "w", encoding=config.OUTPUT_ENCODING) as f:
        f.write("\n".join(lines))


def generate_original_srt(subtitles: list[Subtitle], output_path: str) -> None:
    lines: list[str] = []
    for i, sub in enumerate(subtitles):
        start = _ms_to_srt_time(sub.start_ms)
        end = _ms_to_srt_time(sub.end_ms)
        lines.append(str(i + 1))
        lines.append(f"{start} --> {end}")
        lines.append(sub.text)
        lines.append("")

    with open(output_path, "w", encoding=config.OUTPUT_ENCODING) as f:
        f.write("\n".join(lines))


def _ms_to_srt_time(ms: int) -> str:
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"