import pytest
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.parser import parse_log


def test_healthy_log_no_strong_signal(valid_healthy_log_content):  # Fixture from above.
    events = parse_log(valid_healthy_log_content.splitlines())
    findings = analyze_events(events, tail_window_min=None, old_trend_threshold=10)
    assert not findings['retention_growth']['detected']
    assert findings['retention_growth']['confidence'] == 'low'
    assert "NO STRONG SIGNAL" in findings['summary']


def test_leak_log_detects_growth(valid_leak_log_content):
    events = parse_log(valid_leak_log_content.splitlines())
    findings = analyze_events(events, tail_window_min=None, old_trend_threshold=10)
    assert findings['retention_growth']['detected']
    assert findings['retention_growth']['confidence'] == 'high'
    assert len(findings['retention_growth']['evidence']) > 0  # Line nums.
    assert "jcmd GC.class_histogram" in findings['retention_growth']['next_steps']


def test_tail_window_behavior(valid_leak_log_content):
    events = parse_log(valid_leak_log_content.splitlines())
    # Full: growth ~20MB/min (assuming 1 min between events).
    full_findings = analyze_events(events, tail_window_min=None, old_trend_threshold=10)
    assert full_findings['retention_growth']['detected']

    # Tail 1 min: only last event, no trend detectable.
    tail_findings = analyze_events(events, tail_window_min=1, old_trend_threshold=10)
    assert not tail_findings['retention_growth']['detected']