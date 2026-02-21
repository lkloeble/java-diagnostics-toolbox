import pytest
from pathlib import Path
from thread_diagnostic.parser import parse_thread_dump
from thread_diagnostic.analyzer import (
    analyze_thread_dump,
    detect_deadlocks,
    detect_lock_contention,
    detect_thread_pool_saturation,
    detect_stuck_threads,
    compute_thread_state_summary,
)


# === Real file tests ===

@pytest.fixture
def real_normal_dump():
    """Load real normal dump from samples."""
    path = Path(__file__).parents[3] / "samples" / "dump_normal.txt"
    if not path.exists():
        pytest.skip(f"Sample not found: {path}")
    return path.read_text()


@pytest.fixture
def real_blocked_dump():
    """Load real blocked dump from samples."""
    path = Path(__file__).parents[3] / "samples" / "dump_blocked.txt"
    if not path.exists():
        pytest.skip(f"Sample not found: {path}")
    return path.read_text()


def test_real_normal_dump_is_healthy(real_normal_dump):
    """Real normal dump should show no issues."""
    dump = parse_thread_dump(real_normal_dump)
    findings = analyze_thread_dump(dump)

    assert "NO STRONG SIGNAL" in findings["summary"]
    detected = [s for s in findings["suspects"] if s["detected"]]
    assert len(detected) == 0


def test_real_blocked_dump_detects_contention(real_blocked_dump):
    """Real blocked dump should detect lock contention."""
    dump = parse_thread_dump(real_blocked_dump)
    findings = analyze_thread_dump(dump)

    contention = next(s for s in findings["suspects"] if s["type"] == "lock_contention")
    assert contention["detected"] is True
    assert contention["max_waiters"] >= 20

    # Should NOT detect deadlock (it's contention, not deadlock)
    deadlock = next(s for s in findings["suspects"] if s["type"] == "deadlock")
    assert deadlock["detected"] is False


def test_analyze_healthy_dump(simple_thread_dump):
    """Healthy dump should return no strong signal."""
    dump = parse_thread_dump(simple_thread_dump)
    findings = analyze_thread_dump(dump)

    assert "NO STRONG SIGNAL" in findings["summary"]
    assert findings["thread_stats"]["total_threads"] >= 3


def test_detect_deadlock(deadlock_thread_dump):
    """Deadlock should be detected."""
    dump = parse_thread_dump(deadlock_thread_dump)
    result = detect_deadlocks(dump)

    assert result["detected"] is True
    assert result["confidence"] == "high"
    assert result["type"] == "deadlock"


def test_detect_no_deadlock(simple_thread_dump):
    """Healthy dump should have no deadlock."""
    dump = parse_thread_dump(simple_thread_dump)
    result = detect_deadlocks(dump)

    assert result["detected"] is False


def test_detect_lock_contention(contention_thread_dump):
    """Lock contention should be detected when multiple threads wait on same lock."""
    dump = parse_thread_dump(contention_thread_dump)
    result = detect_lock_contention(dump, threshold=3)

    assert result["detected"] is True
    assert result["max_waiters"] >= 3


def test_detect_no_lock_contention(simple_thread_dump):
    """Healthy dump should have no lock contention."""
    dump = parse_thread_dump(simple_thread_dump)
    result = detect_lock_contention(dump)

    assert result["detected"] is False


def test_compute_thread_state_summary(simple_thread_dump):
    """Thread state summary should count states correctly."""
    dump = parse_thread_dump(simple_thread_dump)
    stats = compute_thread_state_summary(dump)

    assert stats["total_threads"] >= 3
    assert "runnable" in stats
    assert "waiting" in stats
    assert "blocked" in stats


def test_analyze_deadlock_is_critical(deadlock_thread_dump):
    """Deadlock findings should trigger critical status."""
    dump = parse_thread_dump(deadlock_thread_dump)
    findings = analyze_thread_dump(dump)

    deadlock_suspect = next(
        (s for s in findings["suspects"] if s["type"] == "deadlock"),
        None
    )
    assert deadlock_suspect is not None
    assert deadlock_suspect["detected"] is True
    assert deadlock_suspect["confidence"] == "high"
