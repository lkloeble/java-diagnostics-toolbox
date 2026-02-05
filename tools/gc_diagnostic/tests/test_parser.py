import pytest
from gc_diagnostic.parser import parse_log, validate_log_format

@pytest.fixture
def invalid_log_content():
    return """
[2023-01-01T00:00:00] Not a valid format
    """.strip()

@pytest.fixture
def valid_healthy_log_content():
    # Mock a minimal healthy log (unified format, G1 events).
    # In reality, expand with your harness outputs, but keep small for tests.
    return """
[2026-02-05T10:00:00.000+0000][0.100s][info][gc] Using G1
[2026-02-05T10:00:01.000+0000][1.100s][info][gc,heap] GC#1 Heap: 100M->50M (1024M) Old: 20M->10M
[2026-02-05T10:00:02.000+0000][2.100s][info][gc,heap] GC#2 Heap: 50M->40M (1024M) Old: 10M->10M
    """.strip()

@pytest.fixture
def valid_leak_log_content():
    # Mock leak-like: old gen growing.
    return """
[2026-02-05T10:00:00.000+0000][0.100s][info][gc] Using G1
[2026-02-05T10:00:01.000+0000][1.100s][info][gc,heap] GC#1 Heap: 100M->90M (1024M) Old: 20M->30M
[2026-02-05T10:00:02.000+0000][2.100s][info][gc,heap] GC#2 Heap: 90M->100M (1024M) Old: 30M->50M
    """.strip()

def test_rejects_invalid_log_format(invalid_log_content):
    with pytest.raises(ValueError) as exc:
        validate_log_format(invalid_log_content.splitlines())
    assert "Invalid log format" in str(exc.value)  # Specific msg: not unified, no G1, etc.

def test_parses_valid_healthy_log(valid_healthy_log_content):
    events = parse_log(valid_healthy_log_content.splitlines())
    assert len(events) == 2  # Two GC events.
    assert events[0]['uptime'] == 1.100
    assert events[0]['old_after'] == 10  # In MB, parsed.

# Similar for leak log.
def test_parses_valid_leak_log(valid_leak_log_content):
    events = parse_log(valid_leak_log_content.splitlines())
    assert len(events) == 2
    assert events[1]['old_after'] == 50