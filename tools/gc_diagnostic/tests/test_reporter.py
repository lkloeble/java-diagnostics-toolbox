import pytest
from gc_diagnostic.reporter import (
    generate_report,
    generate_slack_summary,
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


# === Slack summary tests ===

def test_slack_summary_healthy():
    """Healthy findings should show green HEALTHY."""
    findings = {"suspects": [{"detected": False, "type": "retention_growth"}]}
    result = generate_slack_summary(findings)
    assert "🟢 HEALTHY" in result
    assert "No GC issues" in result


def test_slack_summary_retention():
    """Retention with trend should show metrics."""
    findings = {
        "suspects": [{
            "detected": True,
            "type": "retention_growth",
            "confidence": "medium",
            "trend_regions_per_min": 25,
            "last_old_regions": 200,
            "max_heap_mb": 256,
        }],
        "region_size_mb": 1
    }
    result = generate_slack_summary(findings)
    assert "🟡 WARNING" in result
    assert "Retention (+25 reg/min)" in result
    assert "heap" in result


def test_slack_summary_critical_collector():
    """Serial collector should show red CRITICAL."""
    findings = {
        "suspects": [{
            "detected": True,
            "type": "collector_choice",
            "collector": "Serial",
            "confidence": "high"
        }]
    }
    result = generate_slack_summary(findings)
    assert "🔴 CRITICAL" in result
    assert "Serial collector" in result


def test_slack_summary_multiple_issues():
    """Multiple issues should be listed."""
    findings = {
        "suspects": [
            {"detected": True, "type": "retention_growth", "confidence": "medium", "trend_regions_per_min": 10},
            {"detected": True, "type": "long_stw_pauses", "confidence": "medium", "max_pause_ms": 1500},
        ]
    }
    result = generate_slack_summary(findings)
    assert "Retention" in result
    assert "Long STW" in result
    assert "1500ms" in result


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
