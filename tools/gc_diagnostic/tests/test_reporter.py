import pytest
from gc_diagnostic.reporter import generate_report
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.parser import parse_log

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
