import pytest
from thread_diagnostic.parser import (
    parse_thread_dump,
    validate_thread_dump,
    THREAD_HEADER_PATTERN,
)


def test_validate_thread_dump_valid(simple_thread_dump):
    """Valid dump should pass validation."""
    assert validate_thread_dump(simple_thread_dump) is True


def test_validate_thread_dump_invalid():
    """Random text should fail validation."""
    assert validate_thread_dump("This is not a thread dump") is False
    assert validate_thread_dump("") is False
    assert validate_thread_dump("short") is False


def test_parse_thread_dump_extracts_threads(simple_thread_dump):
    """Parser should extract all threads."""
    dump = parse_thread_dump(simple_thread_dump)
    assert len(dump.threads) >= 3
    assert dump.jvm_info is not None
    assert "OpenJDK" in dump.jvm_info


def test_parse_thread_dump_extracts_thread_info(simple_thread_dump):
    """Parser should extract thread details."""
    dump = parse_thread_dump(simple_thread_dump)
    main_thread = next((t for t in dump.threads if t.name == "main"), None)

    assert main_thread is not None
    assert main_thread.state == "RUNNABLE"
    assert main_thread.daemon is False
    assert len(main_thread.stack_trace) > 0


def test_parse_thread_dump_detects_daemon(simple_thread_dump):
    """Parser should detect daemon threads."""
    dump = parse_thread_dump(simple_thread_dump)
    gc_thread = next((t for t in dump.threads if "GC" in t.name), None)

    assert gc_thread is not None
    assert gc_thread.daemon is True


def test_parse_thread_dump_detects_deadlock(deadlock_thread_dump):
    """Parser should detect deadlock markers."""
    dump = parse_thread_dump(deadlock_thread_dump)
    assert len(dump.deadlocks) > 0


def test_parse_thread_dump_extracts_locks(deadlock_thread_dump):
    """Parser should extract lock information."""
    dump = parse_thread_dump(deadlock_thread_dump)

    thread1 = next((t for t in dump.threads if t.name == "Thread-1"), None)
    assert thread1 is not None
    assert thread1.waiting_on is not None
    assert len(thread1.holding_locks) > 0


def test_thread_header_pattern():
    """Test thread header regex pattern."""
    line = '"pool-1-thread-3" #15 daemon prio=5 os_prio=0 tid=0x00007f1234 nid=0x1a waiting on condition'
    match = THREAD_HEADER_PATTERN.match(line)

    assert match is not None
    assert match.group(1) == "pool-1-thread-3"
    assert match.group(3) == "daemon"
    assert match.group(4) == "5"  # priority
