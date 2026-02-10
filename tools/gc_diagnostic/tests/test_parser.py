from pathlib import Path
import pytest
from gc_diagnostic.parser import (
    parse_log, validate_log_format, extract_heap_max_capacity,
    extract_heap_region_size, OLD_REGIONS_PATTERN, PAUSE_LINE_PATTERN,
    HUMONGOUS_REGIONS_PATTERN, EVACUATION_FAILURE_MARKER
)

def test_parses_real_fast_leak_log(gc_fast_log_lines):
    events = parse_log(gc_fast_log_lines)
    assert len(events) >= 5, f"Seulement {len(events)} events GC old regions détectés"
    old_afters = [e['old_after_regions'] for e in events]
    assert max(old_afters) > min(old_afters), "Pas de variation d'old regions"
    # Ajoute plus tard : assert croissance globale


def test_theregexp():
    test_line1 = "[2026-02-05T05:47:54.265+0200][264.303s][info][gc,heap     ] GC(10) Old regions: 214->227"
    match1 = OLD_REGIONS_PATTERN.search(test_line1)

    test_line2 = "[2026-02-05T05:47:40.131+0200][250.169s][info][gc,heap     ] GC(8) Old regions: 192->214"
    match2 = OLD_REGIONS_PATTERN.search(test_line2)

    test_line3 = "[2026-02-05T05:43:52.074+0200][22.113s][info][gc,heap     ] GC(0) Eden regions: 23->0(14)"
    match3 = OLD_REGIONS_PATTERN.search(test_line3)

    # Affichage pour debug
    if match1:
        print("MATCH line1 ! Groups:", match1.groups())
    else:
        print("NO MATCH line1 - line was:", repr(test_line1))

    if match2:
        print("MATCH line2 ! Groups:", match2.groups())
    else:
        print("NO MATCH line2 - line was:", repr(test_line2))

    if match3:
        print("MATCH line3 ! Groups:", match3.groups())
    else:
        print("NO MATCH line3 - line was:", repr(test_line3))


    # Assertions claires et idiomatiques
    assert match1 is not None, "Regex ne matche pas la ligne 1"
    assert match2 is not None, "Regex ne matche pas la ligne 2"
    assert match3 is None, "Regex ne matche pas la ligne 3"

    # Verify extracted groups (groups: timestamp, uptime, gc_num, before, after)
    assert match1.group(3) == '10'   # GC number
    assert match1.group(4) == '214'  # before
    assert match1.group(5) == '227'  # after
    assert match2.group(3) == '8'    # GC number
    assert match2.group(4) == '192'  # before
    assert match2.group(5) == '214'  # after


def test_parses_real_fast_leak_log(gc_fast_log_lines):
    events = parse_log(gc_fast_log_lines)
    print(f"Nombre d'événements old regions parsés : {len(events)}")

    if events:
        print("Premier event:", events[0])
        print("Dernier event:", events[-1])
        old_afters = [e['old_after_regions'] for e in events]
        print("Old after regions:", old_afters)
        print("Croissance totale:", max(old_afters) - min(old_afters))

    assert len(events) >= 5, f"Seulement {len(events)} events GC old regions détectés"
    old_afters = [e['old_after_regions'] for e in events]
    assert max(old_afters) > min(old_afters), "Pas de variation d'old regions"




# tests/test_parser.py

def test_extracts_heap_max_capacity():
    lines = [
        "[2026-02-06T07:02:03.195+0200][0.005s][info][gc,init] Heap Max Capacity: 256M",
        # autres lignes...
    ]
    max_capacity_mb = extract_heap_max_capacity(lines)
    assert max_capacity_mb == 256


def test_extracts_heap_region_size():
    lines = [
        "[2026-02-06T07:02:03.195+0200][0.005s][info][gc,init] Heap Region Size: 1M",
        # autres lignes...
    ]
    region_size_mb = extract_heap_region_size(lines)
    assert region_size_mb == 1


def test_extracts_both_from_init_block():
    init_block = [
        "[2026-02-06T07:02:03.195+0200][0.005s][info][gc,init] Some other info",
        "[2026-02-06T07:02:03.195+0200][0.005s][info][gc,init] Heap Max Capacity: 4G",
        "[2026-02-06T07:02:03.195+0200][0.005s][info][gc,init] Heap Region Size: 2M",
    ]
    max_mb = extract_heap_max_capacity(init_block)
    region_mb = extract_heap_region_size(init_block)
    assert max_mb == 4096   # 4G = 4096M
    assert region_mb == 2


def test_returns_none_if_not_found():
    lines = ["just random lines", "no init info"]
    assert extract_heap_max_capacity(lines) is None
    assert extract_heap_region_size(lines) is None


# === New parser feature tests ===

def test_pause_line_pattern_normal():
    """Test parsing of normal Young GC pause line."""
    line = "[2026-02-05T05:43:52.074+0200][22.113s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 22M->19M(256M) 8.657ms"
    match = PAUSE_LINE_PATTERN.search(line)

    assert match is not None
    assert match.group(1) == "2026-02-05T05:43:52.074+0200"  # timestamp
    assert match.group(2) == "22.113"  # uptime
    assert match.group(3) == "0"  # GC number
    assert "Pause Young" in match.group(4)  # GC type
    assert match.group(5) == "22"  # heap before
    assert match.group(6) == "M"   # heap before unit
    assert match.group(7) == "19"  # heap after
    assert match.group(9) == "256" # heap total
    assert match.group(11) == "8.657"  # pause ms


def test_pause_line_pattern_mixed_with_evacuation_failure():
    """Test parsing of Mixed GC with Evacuation Failure."""
    line = "[2026-02-10T10:45:18.503+0200][9950.264s][info][gc          ] GC(1074) Pause Young (Mixed) (G1 Evacuation Pause) (Evacuation Failure) 766M->766M(1024M) 3.510ms"
    match = PAUSE_LINE_PATTERN.search(line)

    assert match is not None
    assert match.group(3) == "1074"  # GC number
    assert "Mixed" in match.group(4)  # GC type contains Mixed
    assert match.group(11) == "3.510"  # pause ms
    assert EVACUATION_FAILURE_MARKER in line


def test_humongous_regions_pattern():
    """Test parsing of humongous regions line."""
    line = "[2026-02-05T05:43:52.074+0200][22.113s][info][gc,heap     ] GC(0) Humongous regions: 5->3"
    match = HUMONGOUS_REGIONS_PATTERN.search(line)

    assert match is not None
    assert match.group(3) == "0"  # GC number
    assert match.group(4) == "5"  # before
    assert match.group(5) == "3"  # after


def test_parse_log_extracts_gc_type_and_pause():
    """Test full parsing extracts GC type and pause time from real log."""
    lines = [
        "[2026-02-05T05:43:29.965+0200][0.004s][info][gc     ] Using G1",
        "[2026-02-05T05:43:52.074+0200][22.113s][info][gc,heap     ] GC(0) Old regions: 0->17",
        "[2026-02-05T05:43:52.074+0200][22.113s][info][gc,heap     ] GC(0) Humongous regions: 0->0",
        "[2026-02-05T05:43:52.074+0200][22.113s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 22M->19M(256M) 8.657ms",
    ]
    events = parse_log(lines)

    assert len(events) == 1
    event = events[0]
    assert event['gc_number'] == 0
    assert event['old_before_regions'] == 0
    assert event['old_after_regions'] == 17
    assert event['humongous_before'] == 0
    assert event['humongous_after'] == 0
    assert event['gc_type'] is not None
    assert "Pause Young" in event['gc_type']
    assert event['pause_ms'] == 8.657
    assert event['heap_before_mb'] == 22
    assert event['heap_after_mb'] == 19
    assert event['heap_total_mb'] == 256
    assert event['evacuation_failure'] is False


def test_parse_log_detects_evacuation_failure():
    """Test that evacuation failure flag is correctly detected."""
    lines = [
        "[2026-02-05T05:43:29.965+0200][0.004s][info][gc     ] Using G1",
        "[2026-02-10T10:45:18.503+0200][9950.264s][info][gc,heap     ] GC(1074) Old regions: 1023->1024",
        "[2026-02-10T10:45:18.503+0200][9950.264s][info][gc          ] GC(1074) Pause Young (Mixed) (G1 Evacuation Pause) (Evacuation Failure) 766M->766M(1024M) 3.510ms",
    ]
    events = parse_log(lines)

    assert len(events) == 1
    event = events[0]
    assert event['gc_number'] == 1074
    assert event['evacuation_failure'] is True
    assert event['old_after_regions'] == 1024


def test_parse_log_real_file_has_new_fields(gc_fast_log_lines):
    """Test that real log parsing populates new fields."""
    events = parse_log(gc_fast_log_lines)

    assert len(events) >= 5

    # Check first event has expected new fields
    first = events[0]
    assert 'gc_type' in first
    assert 'pause_ms' in first
    assert 'humongous_before' in first
    assert 'humongous_after' in first
    assert 'evacuation_failure' in first

    # At least some events should have GC type parsed
    events_with_gc_type = [e for e in events if e['gc_type'] is not None]
    assert len(events_with_gc_type) > 0, "Expected some events to have gc_type parsed"

    # At least some events should have pause_ms parsed
    events_with_pause = [e for e in events if e['pause_ms'] is not None]
    assert len(events_with_pause) > 0, "Expected some events to have pause_ms parsed"