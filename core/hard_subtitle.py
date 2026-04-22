from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass

from core.subtitle_parser import Subtitle
from utils.video import get_frames, get_video_info
from utils.preprocess import preprocess_frames
import config

log = logging.getLogger(__name__)

_ocr_instance = None
_ocr_lang = None


def _get_ocr():
    global _ocr_instance, _ocr_lang

    if _ocr_instance is not None and _ocr_lang == config.OCR_LANG:
        return _ocr_instance

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        raise RuntimeError(
            "PaddleOCR is required for hard subtitle extraction. "
            "Install it with: pip install paddleocr"
        )

    _ocr_instance = PaddleOCR(
        use_angle_cls=True,
        lang=config.OCR_LANG,
        use_gpu=config.OCR_USE_GPU,
        show_log=False,
    )
    _ocr_lang = config.OCR_LANG
    return _ocr_instance


def extract_hard_subtitle(video_path: str) -> list[Subtitle]:
    info = get_video_info(video_path)
    fps = config.OCR_SAMPLE_FPS
    region = config.SUBTITLE_REGION

    log.info("Sampling frames from %s at %d fps, region=%s", video_path, fps, region)

    frame_paths, output_dir = get_frames(video_path, fps=fps, region=region, output_dir=None)
    log.info("Sampled %d frames", len(frame_paths))

    if not frame_paths:
        return []

    ocr_frame_paths, preproc_dir = preprocess_frames(frame_paths)
    log.info("Preprocessing %s", "enabled" if config.OCR_PREPROCESS else "disabled")

    ocr_results = _run_ocr(ocr_frame_paths)
    ocr_results = _filter_watermarks(ocr_results, total_frames=len(frame_paths))
    duration_ms = int(info["duration"] * 1000)

    subtitles = _align_timestamps(ocr_results, fps, duration_ms)
    log.info("Aligned %d subtitle entries", len(subtitles))

    shutil.rmtree(output_dir, ignore_errors=True)
    if preproc_dir:
        shutil.rmtree(preproc_dir, ignore_errors=True)

    return subtitles


@dataclass
class _OCRResult:
    frame_idx: int
    text: str
    text_lines: list[str]
    confidence: float


def _run_ocr(frame_paths: list[str]) -> list[_OCRResult]:
    ocr = _get_ocr()
    min_conf = config.OCR_MIN_CONFIDENCE
    min_len = config.OCR_MIN_TEXT_LENGTH

    results: list[_OCRResult] = []
    total = len(frame_paths)

    for i, path in enumerate(frame_paths):
        if i % 50 == 0:
            log.info("OCR progress: %d/%d", i, total)

        ocr_out = ocr.ocr(path, cls=True)
        texts: list[str] = []
        confs: list[float] = []

        if ocr_out and ocr_out[0]:
            for line in ocr_out[0]:
                text = line[1][0].strip()
                conf = line[1][1]
                if text and conf >= min_conf and len(text) >= min_len:
                    texts.append(text)
                    confs.append(conf)
                elif text:
                    log.debug("Dropped text '%s' (conf=%.2f, len=%d)", text, conf, len(text))

        combined_lines = "\n".join(texts)
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        if texts:
            results.append(_OCRResult(
                frame_idx=i,
                text=combined_lines,
                text_lines=texts,
                confidence=avg_conf,
            ))
        elif ocr_out is None or (ocr_out and not ocr_out[0]):
            log.warning("OCR returned no result for frame %d", i)

    return results


def _filter_watermarks(results: list[_OCRResult], total_frames: int) -> list[_OCRResult]:
    if not results or config.OCR_WATERMARK_RATIO <= 0:
        return results

    line_counts: dict[str, int] = {}
    for r in results:
        for line in r.text_lines:
            norm = line.strip().lower()
            if len(norm) <= 5:
                line_counts[norm] = line_counts.get(norm, 0) + 1

    threshold = total_frames * config.OCR_WATERMARK_RATIO
    watermarks = {text for text, count in line_counts.items() if count >= threshold}

    if watermarks:
        log.info("Detected watermark text: %s", watermarks)

    if not watermarks:
        return results

    filtered: list[_OCRResult] = []
    for r in results:
        keep_lines = [l for l in r.text_lines if l.strip().lower() not in watermarks]
        if keep_lines:
            keep_confs = []
            for l in keep_lines:
                idx = r.text_lines.index(l)
                keep_confs.append(r.confidence)
            avg_conf = r.confidence
            filtered.append(_OCRResult(
                frame_idx=r.frame_idx,
                text="\n".join(keep_lines),
                text_lines=keep_lines,
                confidence=avg_conf,
            ))
        else:
            log.debug("Frame %d entirely watermark, dropped", r.frame_idx)

    return filtered


def _align_timestamps(ocr_results: list[_OCRResult], fps: float, duration_ms: int) -> list[Subtitle]:
    if not ocr_results:
        return []

    frame_ms = 1000.0 / fps if fps > 0 else 1000.0

    grouped = _group_by_text_change(ocr_results)

    subtitles = []
    for idx, group in enumerate(grouped, 1):
        start_frame = group[0].frame_idx
        end_frame = group[-1].frame_idx

        start_ms = int(start_frame * frame_ms)
        end_ms = min(int((end_frame + 1) * frame_ms), duration_ms)

        best = max(group, key=lambda r: (r.confidence, len(r.text)))
        text = best.text

        subtitles.append(Subtitle(
            index=idx,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text,
        ))

    return subtitles


def _group_by_text_change(results: list[_OCRResult]) -> list[list[_OCRResult]]:
    if not results:
        return []

    groups: list[list[_OCRResult]] = []
    current_group: list[_OCRResult] = [results[0]]

    for r in results[1:]:
        if r.text == current_group[-1].text or _is_similar(r.text, current_group[-1].text):
            current_group.append(r)
        else:
            groups.append(current_group)
            current_group = [r]

    groups.append(current_group)
    return groups


def _is_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False

    norm_a = a.replace(" ", "").lower()
    norm_b = b.replace(" ", "").lower()
    if norm_a == norm_b:
        return True

    shorter_len = min(len(norm_a), len(norm_b))
    if shorter_len == 0:
        return False

    if shorter_len <= 5:
        threshold = 0.8
    elif shorter_len <= 15:
        threshold = 0.7
    else:
        threshold = 0.6

    longer_len = max(len(norm_a), len(norm_b))

    max_matches = 0
    for i in range(len(norm_a) - shorter_len + 1):
        matches = sum(1 for j in range(shorter_len) if i + j < len(norm_a) and norm_a[i + j] == norm_b[j])
        max_matches = max(max_matches, matches)

    return (max_matches / longer_len) >= threshold if longer_len > 0 else False
