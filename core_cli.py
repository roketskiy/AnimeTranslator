from __future__ import annotations

import logging
from pathlib import Path

import click
import config
from utils.progress import FancyProgressBar
from core.subtitle_parser import parse_subtitle_file
from core.translator import translate_batch
from core.srt_generator import generate_srt, generate_bilingual_srt, generate_original_srt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@cli.command()
@click.option("-i", "--input", "input_path", required=True, help="subtitle file (.srt/.ass)")
@click.option("-o", "--output", "output_path", default=None, help="output translated .srt file")
@click.option("--src", default="ja", help="source language code (default: ja)")
@click.option("--dst", default="zh", help="target language code (default: zh)")
@click.option("--no-original", "no_original", is_flag=True, help="skip original subtitle output")
def file(input_path, output_path, src, dst, no_original):
    if not config.API_KEY:
        raise click.ClickException("TRANSLATE_API_KEY not set.")

    p = Path(input_path)
    if output_path is None:
        output_path = str(p.with_suffix(f".{dst}.srt"))

    log.info("Parsing %s", input_path)
    subtitles = parse_subtitle_file(input_path)
    log.info("Found %d subtitle entries", len(subtitles))

    texts = [s.text for s in subtitles]
    results = _translate_texts(texts, src, dst)

    generate_srt(subtitles, results, output_path)

    if not no_original:
        original_path = str(p.with_suffix(f".{src}.srt"))
        generate_original_srt(subtitles, original_path)
        log.info("Output written to %s + %s", output_path, original_path)
    else:
        log.info("Output written to %s", output_path)


@cli.command()
@click.option("-i", "--input", "input_path", required=True, help="video file with soft subtitles")
@click.option("-o", "--output", "output_path", default=None, help="output translated .srt file")
@click.option("--track", default=None, type=int, help="subtitle track index")
@click.option("--list-tracks", "list_tracks", is_flag=True, help="list available subtitle tracks")
@click.option("--src", default="ja", help="source language code (default: ja)")
@click.option("--dst", default="zh", help="target language code (default: zh)")
@click.option("--no-original", "no_original", is_flag=True, help="skip original subtitle output")
def soft(input_path, output_path, track, list_tracks, src, dst, no_original):
    if not config.API_KEY:
        raise click.ClickException("TRANSLATE_API_KEY not set.")

    from core.soft_subtitle import get_subtitle_tracks, extract_soft_subtitle

    if list_tracks:
        tracks = get_subtitle_tracks(input_path)
        if not tracks:
            click.echo("No subtitle tracks found.")
            return
        for t in tracks:
            click.echo(f"  Index: {t['index']}  Codec: {t['codec']}  Lang: {t['language']}  Title: {t['title']}")
        return

    subtitles = extract_soft_subtitle(input_path, track_index=track)
    log.info("Extracted %d subtitle entries", len(subtitles))

    p = Path(input_path)
    if output_path is None:
        output_path = str(p.with_suffix(f".{dst}.srt"))

    texts = [s.text for s in subtitles]
    results = _translate_texts(texts, src, dst)

    generate_srt(subtitles, results, output_path)

    if not no_original:
        original_path = str(p.with_suffix(f".{src}.srt"))
        generate_original_srt(subtitles, original_path)
        log.info("Output written to %s + %s", output_path, original_path)
    else:
        log.info("Output written to %s", output_path)


@cli.command()
@click.option("-i", "--input", "input_path", required=True, help="video file with hard-burned subtitles")
@click.option("-o", "--output", "output_path", default=None, help="output .srt file")
@click.option("--src", default="ja", help="source language code (default: ja)")
@click.option("--dst", default="zh", help="target language code (default: zh)")
@click.option("--bilingual", is_flag=True, help="output bilingual srt")
def hard(input_path, output_path, src, dst, bilingual):
    if not config.API_KEY:
        raise click.ClickException("TRANSLATE_API_KEY not set.")

    from core.hard_subtitle import extract_hard_subtitle

    subtitles = extract_hard_subtitle(input_path)
    log.info("OCR found %d subtitle entries", len(subtitles))

    if output_path is None:
        p = Path(input_path)
        output_path = str(p.with_suffix(".zh.srt"))

    texts = [s.text for s in subtitles]
    results = _translate_texts(texts, src, dst)

    if bilingual:
        generate_bilingual_srt(subtitles, results, output_path)
    else:
        generate_srt(subtitles, results, output_path)

    log.info("Output written to %s", output_path)


def _translate_texts(texts, src, dst):
    results = []
    batch_size = config.TRANSLATE_BATCH_SIZE
    for i in FancyProgressBar(range(0, len(texts), batch_size), desc="Translating"):
        batch = texts[i : i + batch_size]
        translated = translate_batch(batch, source_lang=src, target_lang=dst)
        results.extend(translated)
    return results