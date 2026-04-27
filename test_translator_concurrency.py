"""Quick concurrency test for translate_batch."""
import re
import time
import random
from unittest.mock import patch
import config
from core.translator import translate_batch


def mock_call_api(api_key, system_prompt, text):
    """Fake API that returns numbered translations with random delay."""
    lines = [l for l in text.strip().split("\n") if l.strip()]
    # Match same pattern as _parse_anchored_output: [N] at line start
    count = len([l for l in lines if re.match(r"^\[\d+\]\s", l)])
    delay = random.uniform(0.1, 0.5)
    time.sleep(delay)
    result_lines = [f"[{i+1}] TRANSLATED_{i+1}" for i in range(count)]
    return "\n".join(result_lines)


def test_concurrency_correctness():
    """Verify results are in correct order despite random completion order."""
    with patch("core.translator._call_api", mock_call_api):
        items = [f"text_{i}" for i in range(150)]
        completed = []

        def progress(comp, total):
            completed.append(comp)

        results = translate_batch(items, max_workers=5, progress_callback=progress)
        
        assert len(results) == 150, f"Expected 150, got {len(results)}"
        assert all("TRANSLATED" in r for r in results), "Not all items translated"
        # Each batch independently numbers 1..batch_size
        batch_size = config.TRANSLATE_BATCH_SIZE
        batch_results = [f"TRANSLATED_{i+1}" for i in range(batch_size)]
        num_batches = 150 // batch_size
        expected = batch_results * num_batches
        assert results == expected, f"Order mismatch"
        assert len(completed) == num_batches, f"Expected {num_batches} progress calls, got {len(completed)}"
        assert completed == [1, 2, 3, 4, 5], f"Progress sequence wrong: {completed}"
        print("✓ All concurrency tests passed")


def test_empty():
    """Translate empty list returns empty."""
    assert translate_batch([], max_workers=3) == []
    print("✓ Empty test passed")


def test_single_batch():
    """Single batch (fewer than batch_size items)."""
    with patch("core.translator._call_api", lambda *a, **kw: "[1] HI\n[2] BYE"):
        assert translate_batch(["hello", "world"], max_workers=3) == ["HI", "BYE"]
    print("✓ Single batch test passed")


def test_batch_failure_fallback():
    """One batch fails -> falls back to original text."""
    call_count = [0]
    
    def flaky_api(api_key, system_prompt, text):
        call_count[0] += 1
        if call_count[0] <= 1:
            raise RuntimeError("Simulated failure")
        lines = [l for l in text.strip().split("\n") if l.strip()]
        count = sum(1 for l in lines if l.strip().startswith("[") and l.split("]")[0][1:].isdigit())
        return "\n".join([f"[{i+1}] TRANSLATED_{i+1}" for i in range(count)])

    with patch("core.translator._call_api", flaky_api):
        items = [f"text_{i}" for i in range(60)]  # 2 batches of 30
        results = translate_batch(items, max_workers=3)
        
        # First batch failed -> original text, second batch translated
        assert len(results) == 60
        assert results[0] == "text_0"  # first batch fallback to original
        assert results[30] == "TRANSLATED_1"  # second batch's [1] TRANSLATED_1
    print("✓ Failure fallback test passed")


if __name__ == "__main__":
    test_empty()
    test_single_batch()
    test_concurrency_correctness()
    test_batch_failure_fallback()
    print("\n🎉 All tests passed!")
