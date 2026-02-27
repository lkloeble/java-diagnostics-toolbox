import pytest
from pathlib import Path
from thread_diagnostic.parser import parse_thread_dump
from thread_diagnostic.analyzer import (
    analyze_thread_dump,
    detect_deadlocks,
    detect_lock_contention,
    detect_thread_pool_saturation,
    detect_stuck_threads,
    detect_cpu_storm,
    compute_thread_state_summary,
    compute_thread_group_inventory,
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


@pytest.fixture
def real_deadlock_dump():
    """Load real deadlock dump from samples."""
    path = Path(__file__).parents[3] / "samples" / "dump_deadlock.txt"
    if not path.exists():
        pytest.skip(f"Sample not found: {path}")
    return path.read_text()


@pytest.fixture
def real_pool_saturated_dump():
    """Load real pool saturated dump from samples."""
    path = Path(__file__).parents[3] / "samples" / "dump_pool_saturated.txt"
    if not path.exists():
        pytest.skip(f"Sample not found: {path}")
    return path.read_text()


def test_real_deadlock_dump(real_deadlock_dump):
    """Real deadlock dump should detect deadlock."""
    dump = parse_thread_dump(real_deadlock_dump)
    findings = analyze_thread_dump(dump)

    deadlock = next(s for s in findings["suspects"] if s["type"] == "deadlock")
    assert deadlock["detected"] is True
    assert deadlock["confidence"] == "high"
    assert len(deadlock["evidence"]) > 0


@pytest.fixture
def real_cpu_storm_dump():
    """Load real cpu storm dump from samples."""
    path = Path(__file__).parents[3] / "samples" / "dump_cpu_storm.txt"
    if not path.exists():
        pytest.skip(f"Sample not found: {path}")
    return path.read_text()


def test_real_cpu_storm_dump(real_cpu_storm_dump):
    """Real cpu storm dump should detect cpu_storm with high confidence."""
    dump = parse_thread_dump(real_cpu_storm_dump)
    findings = analyze_thread_dump(dump)

    cpu_storm = next(s for s in findings["suspects"] if s["type"] == "cpu_storm")
    assert cpu_storm["detected"] is True
    assert cpu_storm["confidence"] == "high"
    assert cpu_storm["runnable_pct"] >= 50.0
    assert len(cpu_storm["hot_locations"]) > 0
    assert cpu_storm["hot_locations"][0]["count"] == 14


def test_real_pool_saturated_dump(real_pool_saturated_dump):
    """Real pool saturated dump should detect saturation."""
    dump = parse_thread_dump(real_pool_saturated_dump)
    findings = analyze_thread_dump(dump)

    saturation = next(s for s in findings["suspects"] if s["type"] == "thread_pool_saturation")
    assert saturation["detected"] is True
    assert saturation["confidence"] == "high"
    assert len(saturation["saturated_pools"]) > 0


def test_real_pool_saturated_dump_group_inventory(real_pool_saturated_dump):
    """pool-sat-worker threads should form a single group of 28."""
    dump = parse_thread_dump(real_pool_saturated_dump)
    findings = analyze_thread_dump(dump)

    groups = findings["thread_groups"]
    worker_group = next((g for g in groups if g["name"] == "pool-sat-worker"), None)
    assert worker_group is not None, "Expected a 'pool-sat-worker' group"
    assert worker_group["count"] == 28
    assert worker_group["waiting"] == 28


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


def test_detect_cpu_storm(cpu_storm_thread_dump):
    """CPU storm should be detected when many RUNNABLE threads cluster at the same location."""
    dump = parse_thread_dump(cpu_storm_thread_dump)
    result = detect_cpu_storm(dump)

    assert result["detected"] is True
    assert result["confidence"] == "high"
    assert result["runnable_pct"] >= 50.0
    assert len(result["hot_locations"]) > 0
    assert result["hot_locations"][0]["count"] >= 3


def test_detect_no_cpu_storm(simple_thread_dump):
    """Healthy dump with no dominant RUNNABLE cluster should not trigger cpu_storm."""
    dump = parse_thread_dump(simple_thread_dump)
    result = detect_cpu_storm(dump)

    assert result["detected"] is False


def test_thread_group_inventory_groups_by_prefix(contention_thread_dump):
    """worker-1..4 should be grouped as a single 'worker' group."""
    dump = parse_thread_dump(contention_thread_dump)
    groups = compute_thread_group_inventory(dump)

    worker_group = next((g for g in groups if g["name"] == "worker"), None)
    assert worker_group is not None, "Expected a 'worker' group"
    assert worker_group["count"] == 4
    assert worker_group["runnable"] == 1
    assert worker_group["blocked"] == 3


def test_thread_group_inventory_in_findings(simple_thread_dump):
    """analyze_thread_dump should include thread_groups in findings."""
    dump = parse_thread_dump(simple_thread_dump)
    findings = analyze_thread_dump(dump)

    assert "thread_groups" in findings
    groups = findings["thread_groups"]
    assert len(groups) > 0

    # http-nio-8080-exec-1..4 should collapse into one group
    http_group = next((g for g in groups if "http-nio-8080-exec" in g["name"]), None)
    assert http_group is not None
    assert http_group["count"] == 4

    # Groups sorted by count descending
    counts = [g["count"] for g in groups]
    assert counts == sorted(counts, reverse=True)


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
