import pytest
from gc_diagnostic.reporter import (
    generate_report,
    compute_suspect_severity,
    SEVERITY_CRITICAL,
    SEVERITY_WARNING,
    SEVERITY_OK,
)
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.parser import parse_log


# === Severity computation tests ===

def test_severity_not_detected():
    """Not detected suspects should return OK."""
    suspect = {"detected": False, "type": "retention_growth", "confidence": "high"}
    assert compute_suspect_severity(suspect) == SEVERITY_OK


def test_severity_serial_collector():
    """Serial collector should be CRITICAL."""
    suspect = {"detected": True, "type": "collector_choice", "collector": "Serial", "confidence": "high"}
    assert compute_suspect_severity(suspect) == SEVERITY_CRITICAL


def test_severity_parallel_collector():
    """Parallel collector should be CRITICAL."""
    suspect = {"detected": True, "type": "collector_choice", "collector": "Parallel", "confidence": "high"}
    assert compute_suspect_severity(suspect) == SEVERITY_CRITICAL


def test_severity_retention_high_confidence():
    """High confidence retention should be CRITICAL."""
    suspect = {"detected": True, "type": "retention_growth", "confidence": "high"}
    assert compute_suspect_severity(suspect) == SEVERITY_CRITICAL


def test_severity_retention_medium_confidence():
    """Medium confidence retention should be WARNING."""
    suspect = {"detected": True, "type": "retention_growth", "confidence": "medium"}
    assert compute_suspect_severity(suspect) == SEVERITY_WARNING


def test_severity_heap_over_90_pct():
    """Heap over 90% should be CRITICAL even with medium confidence."""
    suspect = {"detected": True, "type": "retention_growth", "confidence": "medium", "heap_occupation_pct": 92}
    assert compute_suspect_severity(suspect) == SEVERITY_CRITICAL


def test_severity_other_detection():
    """Other detected issues should be WARNING."""
    suspect = {"detected": True, "type": "long_stw_pauses", "confidence": "medium"}
    assert compute_suspect_severity(suspect) == SEVERITY_WARNING


# === Report generation tests ===

def test_report_for_healthy_md(valid_healthy_log_content):
    events = parse_log(valid_healthy_log_content.splitlines())
    findings = analyze_events(events, None, old_trend_threshold=30.0)
    report = generate_report(findings, format='md')
    assert "# GC Flu Test Report" in report
    assert "NO STRONG SIGNAL" in report


def test_report_for_leak_txt(valid_leak_log_content):
    events = parse_log(valid_leak_log_content.splitlines())
    findings = analyze_events(events, None, old_trend_threshold=30.0)
    report = generate_report(findings, format='txt')
    assert "RETENTION GROWTH - DETECTED" in report
    assert "Confidence:" in report
