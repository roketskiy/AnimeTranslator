from __future__ import annotations

import re
import time
import logging
import concurrent.futures
import requests
import config

log = logging.getLogger(__name__)


def translate_batch(
    items: list[str],
    source_lang: str = "ja",
    target_lang: str = "zh",
    max_workers: int | None = None,
    progress_callback: callable[[int, int], None] | None = None,
) -> list[str]:
    """
    Translate a list of strings from source_lang to target_lang.

    Sub-batches are submitted concurrently via ThreadPoolExecutor.
    Each sub-batch carries a context window of surrounding untranslated lines.

    Args:
        items: Source texts to translate.
        source_lang: Source language code (e.g. "ja", "en").
        target_lang: Target language code (e.g. "zh").
        max_workers: Max concurrent API requests. Reads config.TRANSLATE_MAX_CONCURRENT if None.
        progress_callback: Called as progress_callback(completed, total) after each
            sub-batch finishes (including fallback batches). ``completed`` counts futures
            resolved, not translation successes — check the return value for actual results.
            On partial failure, failed batches retain original text.

    Returns:
        Translated strings in the same order as *items*. Failed batches fall back to
        original source text.
    """
    if not items:
        return []

    api_key = config.API_KEY
    if not api_key:
        raise RuntimeError("TRANSLATE_API_KEY not set. Set the env var or update config.py.")

    if max_workers is None:
        max_workers = config.TRANSLATE_MAX_CONCURRENT
    if max_workers <= 0:
        raise ValueError(f"max_workers must be positive, got {max_workers}")

    system_prompt = (
        f"You are a professional translator. Translate the following "
        f"{source_lang} text to {target_lang}. "
        f"Output exactly one line per input line, prefixed with the same "
        f"line number in brackets like [1], [2], [3]. "
        f"Preserve the order and line count exactly. "
        f"Do not add any extra text or comments."
    )

    results: list[str | None] = [None] * len(items)
    batch_size = config.TRANSLATE_BATCH_SIZE
    context_size = config.TRANSLATE_CONTEXT_SIZE

    # Phase 1: build all sub-batch tasks (prompt text for each batch)
    tasks: list[tuple[int, list[str], str]] = []  # (batch_start, batch_items, prompt_text)

    for batch_start in range(0, len(items), batch_size):
        batch_end = min(batch_start + batch_size, len(items))
        ctx_start = max(0, batch_start - context_size)
        ctx_end = min(len(items), batch_end + context_size)

        ctx_before = items[ctx_start:batch_start]
        batch_items = items[batch_start:batch_end]
        ctx_after = items[batch_end:ctx_end]

        lines = []
        ctx_num = 1
        for t in ctx_before:
            lines.append(f"[ctx-{ctx_num}] {t}")
            ctx_num += 1
        for i, t in enumerate(batch_items):
            lines.append(f"[{i + 1}] {t}")
        ctx_num = 1
        for t in ctx_after:
            lines.append(f"[ctx-{ctx_num}] {t}")
            ctx_num += 1

        text = "\n".join(lines)
        tasks.append((batch_start, batch_items, text))

    total_tasks = len(tasks)
    failed_count = 0

    # Phase 2: execute all tasks concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_info: dict[concurrent.futures.Future, tuple[int, list[str]]] = {}
        for batch_start, batch_items, text in tasks:
            future = executor.submit(
                _call_api_and_parse, api_key, system_prompt, text, batch_items
            )
            future_info[future] = (batch_start, batch_items)

        # Phase 3: collect results as they complete
        completed = 0
        for future in concurrent.futures.as_completed(future_info):
            batch_start, batch_items = future_info[future]
            try:
                batch_translations = future.result()
            except (requests.RequestException, RuntimeError, ValueError) as e:
                log.warning("Batch starting at index %d failed; falling back to original text: %s", batch_start, e)
                batch_translations = batch_items
                failed_count += 1
            except Exception:
                log.error("Unexpected error in batch starting at index %d", batch_start, exc_info=True)
                batch_translations = batch_items
                failed_count += 1

            for i, t in enumerate(batch_translations):
                results[batch_start + i] = t

            completed += 1
            if progress_callback:
                progress_callback(completed, total_tasks)

    if failed_count == total_tasks:
        raise RuntimeError("All translation batches failed")

    if failed_count > 0:
        log.info("%d/%d sub-batches translated successfully; %d fell back to original text",
                 total_tasks - failed_count, total_tasks, failed_count)

    return results


def _call_api_and_parse(
    api_key: str,
    system_prompt: str,
    text: str,
    batch_items: list[str],
) -> list[str]:
    """Single-batch unit-of-work: call API + parse the numbered output."""
    raw = _call_api(api_key, system_prompt, text)
    return _parse_anchored_output(raw, batch_items)


def _parse_anchored_output(output: str, batch_items: list[str]) -> list[str]:
    """Parse numbered translation output and align with original batch items."""
    lines = output.strip().split("\n")
    results: dict[int, str] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[(\d+)\]\s*(.+)$", line)
        if m:
            idx = int(m.group(1)) - 1
            results[idx] = m.group(2).strip()

    return [results.get(i, batch_items[i]) for i in range(len(batch_items))]


def _call_api(api_key: str, system_prompt: str, text: str) -> str:
    url = f"{config.API_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.API_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }

    for attempt in range(1, config.TRANSLATE_RETRY_TIMES + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            log.warning("API call failed (attempt %d/%d): %s", attempt, config.TRANSLATE_RETRY_TIMES, e)
            if attempt < config.TRANSLATE_RETRY_TIMES:
                time.sleep(config.TRANSLATE_RETRY_DELAY * attempt)

    raise RuntimeError("API call failed after retries")
