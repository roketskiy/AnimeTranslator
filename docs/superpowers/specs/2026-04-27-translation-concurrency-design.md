# Translation Concurrency Design

**Date:** 2026-04-27  
**Status:** Approved  
**Author:** Developer Agent  

## Overview

Convert the current serial translation API request pipeline to use concurrent requests via `ThreadPoolExecutor`, dramatically improving translation throughput.

**Current bottleneck:** `translate_batch()` in `core/translator.py` sends sub-batches one at a time, waiting for each API response before sending the next. For 300 subtitle entries split into 10 batches of 30, this means 10 sequential API calls.

**Goal:** Send up to `N` sub-batches in parallel, reducing wall-clock time by approximately `N`x.

## Approach: ThreadPoolExecutor Inside `translate_batch()`

**Rationale:** Concentrating concurrency in `core/translator.py` keeps changes localized. Callers (`main.py`, `core_cli.py`) only need minor simplifications (removing redundant outer batch loops).

**Why ThreadPoolExecutor over asyncio:**
- Translation API calls are I/O-bound (network waiting), where threads excel
- Minimal code changes — `requests` stays synchronous, no need for `aiohttp`
- `ThreadPoolExecutor` is built into Python stdlib, no new dependencies
- `_call_api()` already has per-request retry logic (exponential backoff), which remains unchanged

**Why context window is unaffected by concurrency:**
The context window (2 lines before + 2 lines after each batch) always sends **source-language** text, never translated text. Parallelizing does not impact context quality.

## Detailed Design

### 1. Configuration (`config.py`)

Add one new config entry:

```python
TRANSLATE_MAX_CONCURRENT = 5   # Max concurrent translation API requests
```

Existing `TRANSLATE_BATCH_SIZE=30` remains unchanged — it controls how many subtitle entries are packed into each API request. `TRANSLATE_MAX_CONCURRENT` controls how many API requests are in-flight simultaneously.

### 2. Core Translator (`core/translator.py`)

#### 2.1 Modified `translate_batch()`

**Before** (serial loop):
```python
for batch_start in range(0, len(items), batch_size):
    text = build_prompt(...)
    translated = _call_api(api_key, system_prompt, text)
    batch_results = _parse_anchored_output(translated, batch_items)
    results[batch_start:batch_end] = batch_results
```

**After** (concurrent):
```python
# Phase 1: Precompute all tasks (prompt texts)
tasks = []
for batch_start in range(0, len(items), batch_size):
    text = build_prompt(batch_items, ctx_before, ctx_after)
    tasks.append((batch_start, batch_items, text))

# Phase 2: Submit all tasks to ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    future_to_idx = {}
    for batch_start, batch_items, text in tasks:
        future = executor.submit(_call_api_and_parse, api_key, system_prompt, text, batch_items)
        future_to_idx[future] = batch_start

    # Phase 3: Collect results as they complete
    completed = 0
    for future in as_completed(future_to_idx):
        batch_start = future_to_idx[future]
        batch_results = future.result()
        for i, t in enumerate(batch_results):
            results[batch_start + i] = t
        completed += 1
        if progress_callback:
            progress_callback(completed, len(tasks))
```

#### 2.2 New helper: `_call_api_and_parse()`

```python
def _call_api_and_parse(api_key, system_prompt, text, batch_items):
    """Combine API call + output parsing for a single sub-batch."""
    raw = _call_api(api_key, system_prompt, text)
    return _parse_anchored_output(raw, batch_items)
```

This function is the unit-of-work submitted to the executor. It encapsulates the full "call API → parse response" pipeline for one sub-batch.

#### 2.3 New parameter: `progress_callback`

```python
def translate_batch(
    items: list[str],
    source_lang: str = "ja",
    target_lang: str = "zh",
    max_workers: int | None = None,
    progress_callback: callable[[int, int], None] | None = None,
) -> list[str]:
```

- `max_workers`: If `None`, reads from `config.TRANSLATE_MAX_CONCURRENT`
- `progress_callback(completed_count, total_count)`: Called after each sub-batch completes

#### 2.4 Unchanged: `_call_api()` and `_parse_anchored_output()`

Both functions remain exactly as-is. `_call_api()` retains its 3-retry exponential backoff logic.

### 3. Caller Changes

#### 3.1 `main.py:do_translate()`

**Before:**
```python
results = []
for i in FancyProgressBar(range(0, len(texts), batch_size), ...):
    batch = texts[i : i + batch_size]
    translated = translate_batch(batch, source_lang=src, target_lang=dst)
    results.extend(translated)
```

**After:**
```python
total_batches = (len(texts) + config.TRANSLATE_BATCH_SIZE - 1) // config.TRANSLATE_BATCH_SIZE
with FancyProgressBar(total=total_batches, desc="翻译进度", unit="batch") as pbar:
    def on_batch_done(completed, total):
        pbar.update(1)
    results = translate_batch(texts, source_lang=src, target_lang=dst, progress_callback=on_batch_done)
```

The outer batch loop is removed — `translate_batch()` now handles all batching internally.

#### 3.2 `core_cli.py:_translate_texts()`

Same pattern as `do_translate()` — remove the manual loop, pass `progress_callback` instead.

### 4. Error Handling

| Scenario | Behavior |
|----------|----------|
| Single sub-batch fails (all retries exhausted) | Falls back to original text for that sub-batch. Does NOT abort other batches. |
| All sub-batches fail | Raises `RuntimeError("All translation batches failed")` |
| Thread safety | `results` list pre-allocated with `[None] * len(items)`. Each thread writes to non-overlapping index ranges. No race conditions. |
| Rate limiting (HTTP 429) | Handled by existing `_call_api` retry logic. If OpenRouter rate-limits, subsequent batches naturally stagger as earlier ones complete. |
| `max_workers > number_of_batches` | `ThreadPoolExecutor` caps workers at actual task count. No wasted threads. |

### 5. Progress Tracking

The `FancyProgressBar` (tqdm subclass) is managed by the caller. It is created with `total=total_batches` and updated via `pbar.update(1)` each time `progress_callback` fires.

**Note:** `FancyProgressBar`'s position manager and `tqdm.write()` may need attention — concurrent log messages from `_call_api` retries could interfere with the progress bar display. Mitigation: log retry warnings at `DEBUG` level instead of `WARNING` to avoid interleaving.

### 6. Files Modified (Summary)

| File | Changes |
|------|---------|
| `config.py` | +1 line: `TRANSLATE_MAX_CONCURRENT = 5` |
| `core/translator.py` | Refactor `translate_batch()` (~40 lines changed). Add `_call_api_and_parse()` (~8 lines). Import `concurrent.futures`. |
| `main.py` | Simplify `do_translate()` (~8 lines changed) |
| `core_cli.py` | Simplify `_translate_texts()` (~6 lines changed) |

**Files NOT modified:** `subtitle_parser.py`, `srt_generator.py`, `soft_subtitle.py`, `hard_subtitle.py`, `utils/*` — no changes needed.

### 7. Testing Strategy

1. **Unit test:** Mock `_call_api` to return a known numbered output. Verify `translate_batch()` returns results in correct order regardless of future completion order.
2. **Integration test:** Run on a small `.srt` file with real API, verify output SRT is valid and all entries are translated.
3. **Concurrency test:** Simulate diverse completion times (each `_call_api` mock with `time.sleep(random)`) and verify ordering correctness.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| OpenRouter rate-limiting concurrent requests | Configurable `max_workers` lets users tune to their API plan's limits |
| Increased memory for multiple in-flight requests | Bounded by `max_workers` — at most `N` requests' worth of prompt/response data in memory |
| Edge case: progress bar corruption from concurrent log output | Reduce retry log level; tqdm's `write()` handles buffered output |

## Backward Compatibility

Fully backward compatible:
- `translate_batch()` retains same signature (new params have defaults)
- All existing config values unchanged
- Output SRT format unchanged
- No new dependencies required
