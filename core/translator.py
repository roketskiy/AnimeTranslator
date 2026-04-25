import re
import time
import logging
import requests
import config

log = logging.getLogger(__name__)


def translate_batch(
    items: list[str],
    source_lang: str = "ja",
    target_lang: str = "zh",
) -> list[str]:
    if not items:
        return []

    api_key = config.API_KEY
    if not api_key:
        raise RuntimeError("TRANSLATE_API_KEY not set. Set the env var or update config.py.")

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
        translated = _call_api(api_key, system_prompt, text)

        batch_translations = _parse_anchored_output(translated, batch_items)

        for i, t in enumerate(batch_translations):
            results[batch_start + i] = t

    return results


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