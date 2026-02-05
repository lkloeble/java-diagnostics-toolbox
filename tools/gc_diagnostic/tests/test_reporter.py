import pytest
from gc_diagnostic.reporter import generate_report
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.parser import parse_log

def test_report_for_healthy_md(valid_healthy_log_content):
    events = parse_log(valid_healthy_log_content.splitlines())
    findings = analyze_events(events, None, 10)
    report = generate_report(findings, format='md')
    assert "# GC Diagnostic Report" in report
    assert "NO STRONG SIGNAL" in report
    assert "Evidence (line 2)" in report  # Deterministic.

def test_report_for_leak_txt(valid_leak_log_content):
    events = parse_log(valid_leak_log_content.splitlines())
    findings = analyze_events(events, None, 10)
    report = generate_report(findings, format='txt')
    assert "Detected: Retention / memory leak-like growth" in report
    assert "Confidence: high" in report
    assert "Next low-effort data: heap dump + MAT" in report
    # Assert readable as plain text (no broken MD artifacts).