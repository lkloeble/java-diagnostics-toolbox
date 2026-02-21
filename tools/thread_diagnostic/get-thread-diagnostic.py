#!/usr/bin/env python3
"""
Thread Dump Diagnostic Tool - Quick triage of jstack thread dumps.

Usage:
    python get-thread-diagnostic.py thread.dump
    jstack <pid> | python get-thread-diagnostic.py -
"""
import argparse
import sys
from pathlib import Path

from thread_diagnostic.parser import parse_thread_dump, validate_thread_dump
from thread_diagnostic.analyzer import analyze_thread_dump
from thread_diagnostic.reporter import generate_report

# Exit codes
EXIT_HEALTHY = 0   # No issues detected
EXIT_WARNING = 1   # Issues detected (investigation recommended)
EXIT_CRITICAL = 2  # Critical issues (immediate action required)


def compute_exit_code(findings: dict) -> int:
    """
    Compute exit code based on findings severity.

    EXIT_CRITICAL (2): Deadlock or high-confidence issues
    EXIT_WARNING (1): Any detected issue
    EXIT_HEALTHY (0): No issues
    """
    suspects = findings.get("suspects", [])
    detected = [s for s in suspects if s.get("detected")]

    if not detected:
        return EXIT_HEALTHY

    for s in detected:
        # Deadlock is always critical
        if s.get("type") == "deadlock":
            return EXIT_CRITICAL
        # High confidence issues are critical
        if s.get("confidence") == "high":
            return EXIT_CRITICAL

    return EXIT_WARNING


def main():
    parser = argparse.ArgumentParser(
        description="Thread Dump Diagnostic: quick triage of jstack dumps for common issues",
        epilog="Example: jstack <pid> | python get-thread-diagnostic.py -"
    )
    parser.add_argument(
        "dump_file",
        type=str,
        help="Path to thread dump file, or '-' to read from stdin"
    )
    parser.add_argument(
        "--format",
        choices=["md", "txt"],
        default="txt",
        help="Output format (default: txt)"
    )

    args = parser.parse_args()

    # Read input
    if args.dump_file == "-":
        content = sys.stdin.read()
    else:
        dump_path = Path(args.dump_file)
        if not dump_path.is_file():
            print(f"Error: file not found: {dump_path}", file=sys.stderr)
            sys.exit(1)
        try:
            content = dump_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)

    # Validate
    if not validate_thread_dump(content):
        print("Error: Invalid format - expected jstack thread dump", file=sys.stderr)
        sys.exit(1)

    # Parse
    dump = parse_thread_dump(content)

    if not dump.threads:
        print("Warning: No threads found in dump", file=sys.stderr)

    # Analyze
    findings = analyze_thread_dump(dump)

    # Generate reports
    report_md = generate_report(findings, format="md")
    report_txt = generate_report(findings, format="txt")

    # Write output files
    md_path = Path("thread-diagnostic.md")
    txt_path = Path("thread-diagnostic.txt")
    md_path.write_text(report_md, encoding="utf-8")
    txt_path.write_text(report_txt, encoding="utf-8")

    # Print requested format
    if args.format == "md":
        print(report_md)
    else:
        print(report_txt)

    print(f"\nReports written to: {md_path.absolute()} and {txt_path.absolute()}")

    # Exit code
    exit_code = compute_exit_code(findings)
    exit_labels = {EXIT_HEALTHY: "HEALTHY", EXIT_WARNING: "WARNING", EXIT_CRITICAL: "CRITICAL"}
    print(f"Exit code: {exit_code} ({exit_labels[exit_code]})")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
