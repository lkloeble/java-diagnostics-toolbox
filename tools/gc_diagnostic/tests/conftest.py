# tools/gc_diagnostic/tests/conftest.py
from pathlib import Path
import pytest

@pytest.fixture(scope="session")
def gc_fast_log_lines():
    repo_root = Path(__file__).resolve().parents[3]  # remonte à java-diagnostics-toolbox
    path = repo_root / "samples" / "gc-memoryleak-fast.log"
    if not path.is_file():
        pytest.skip(f"Sample file not found: {path}\nAdd it to /samples/ and commit.")
    return path.read_text(encoding="utf-8").splitlines()


@pytest.fixture
def valid_healthy_log_content():
    """Minimal healthy log content with stable memory (no leak)."""
    return """[2026-02-05T05:43:29.965+0200][0.004s][info][gc     ] Using G1
[2026-02-05T05:43:29.965+0200][0.005s][info][gc,init] Heap Max Capacity: 256M
[2026-02-05T05:43:29.965+0200][0.005s][info][gc,init] Heap Region Size: 1M
[2026-02-05T05:43:52.074+0200][60.0s][info][gc,heap     ] GC(0) Old regions: 0->50
[2026-02-05T05:43:52.074+0200][60.0s][info][gc,heap     ] GC(0) Humongous regions: 0->0
[2026-02-05T05:43:52.074+0200][60.0s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 22M->19M(256M) 8.657ms
[2026-02-05T05:44:52.074+0200][120.0s][info][gc,heap     ] GC(1) Old regions: 50->52
[2026-02-05T05:44:52.074+0200][120.0s][info][gc,heap     ] GC(1) Humongous regions: 0->0
[2026-02-05T05:44:52.074+0200][120.0s][info][gc          ] GC(1) Pause Young (Normal) (G1 Evacuation Pause) 50M->48M(256M) 7.5ms
[2026-02-05T05:45:52.074+0200][180.0s][info][gc,heap     ] GC(2) Old regions: 52->51
[2026-02-05T05:45:52.074+0200][180.0s][info][gc,heap     ] GC(2) Humongous regions: 0->0
[2026-02-05T05:45:52.074+0200][180.0s][info][gc          ] GC(2) Pause Young (Normal) (G1 Evacuation Pause) 52M->50M(256M) 8.0ms
[2026-02-05T05:46:52.074+0200][240.0s][info][gc,heap     ] GC(3) Old regions: 51->50
[2026-02-05T05:46:52.074+0200][240.0s][info][gc,heap     ] GC(3) Humongous regions: 0->0
[2026-02-05T05:46:52.074+0200][240.0s][info][gc          ] GC(3) Pause Young (Normal) (G1 Evacuation Pause) 51M->49M(256M) 7.8ms
"""


@pytest.fixture
def valid_leak_log_content():
    """Log content showing clear memory leak (growing old regions)."""
    return """[2026-02-05T05:43:29.965+0200][0.004s][info][gc     ] Using G1
[2026-02-05T05:43:29.965+0200][0.005s][info][gc,init] Heap Max Capacity: 256M
[2026-02-05T05:43:29.965+0200][0.005s][info][gc,init] Heap Region Size: 1M
[2026-02-05T05:43:52.074+0200][60.0s][info][gc,heap     ] GC(0) Old regions: 0->50
[2026-02-05T05:43:52.074+0200][60.0s][info][gc,heap     ] GC(0) Humongous regions: 0->0
[2026-02-05T05:43:52.074+0200][60.0s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 22M->19M(256M) 8.657ms
[2026-02-05T05:44:52.074+0200][120.0s][info][gc,heap     ] GC(1) Old regions: 50->100
[2026-02-05T05:44:52.074+0200][120.0s][info][gc,heap     ] GC(1) Humongous regions: 0->0
[2026-02-05T05:44:52.074+0200][120.0s][info][gc          ] GC(1) Pause Young (Normal) (G1 Evacuation Pause) 80M->75M(256M) 9.5ms
[2026-02-05T05:45:52.074+0200][180.0s][info][gc,heap     ] GC(2) Old regions: 100->150
[2026-02-05T05:45:52.074+0200][180.0s][info][gc,heap     ] GC(2) Humongous regions: 0->0
[2026-02-05T05:45:52.074+0200][180.0s][info][gc          ] GC(2) Pause Young (Normal) (G1 Evacuation Pause) 120M->115M(256M) 10.0ms
[2026-02-05T05:46:52.074+0200][240.0s][info][gc,heap     ] GC(3) Old regions: 150->200
[2026-02-05T05:46:52.074+0200][240.0s][info][gc,heap     ] GC(3) Humongous regions: 0->0
[2026-02-05T05:46:52.074+0200][240.0s][info][gc          ] GC(3) Pause Young (Normal) (G1 Evacuation Pause) 180M->175M(256M) 11.0ms
"""