import re
from dataclasses import dataclass
from pathlib import Path

import pysrt
import pysubs2


@dataclass
class Subtitle:
    index: int
    start_ms: int
    end_ms: int
    text: str


def parse_srt(path: str) -> list[Subtitle]:
    subs = pysrt.open(path, encoding="utf-8")
    result = []
    for i, sub in enumerate(subs, 1):
        start_ms = sub.start.ordinal
        end_ms = sub.end.ordinal
        text = sub.text.replace("\n", " ").strip()
        if text:
            result.append(Subtitle(index=i, start_ms=start_ms, end_ms=end_ms, text=text))
    return result


def parse_ass(path: str) -> list[Subtitle]:
    subs = pysubs2.load(path, format_="ass", encoding="utf-8")
    entries = []
    for i, line in enumerate(subs, 1):
        text = line.text
        text = re.sub(r"\{[^}]*\}", "", text)
        text = text.replace("\\N", " ").replace("\\n", " ").replace("\\h", " ")
        text = text.replace("\n", " ").strip()
        if text:
            entries.append(Subtitle(
                index=i,
                start_ms=line.start,
                end_ms=line.end,
                text=text,
            ))
    return entries


def parse_subtitle_file(path: str) -> list[Subtitle]:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".srt":
        return parse_srt(path)
    if ext == ".ass":
        return parse_ass(path)
    raise ValueError(f"unsupported subtitle format: {ext}")
