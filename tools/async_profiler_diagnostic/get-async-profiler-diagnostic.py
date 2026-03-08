#!/usr/bin/env python3
"""
Async-Profiler Diagnostic - Reads collapsed stacks output and produces a structured summary.

Usage:
    python get-async-profiler-diagnostic.py profile.collapsed --app-prefix com.example.myapp
    asprof ... | python get-async-profiler-diagnostic.py - --app-prefix com/example/myapp
"""
import argparse
import sys
from pathlib import Path

from async_profiler_diagnostic.parser import parse_collapsed, validate_collapsed
from async_profiler_diagnostic.analyzer import analyze
from async_profiler_diagnostic.reporter import generate_report


def main():
    parser = argparse.ArgumentParser(
        description="Async-Profiler Diagnostic: structured summary of collapsed stacks output",
        epilog="Example: python get-async-profiler-diagnostic.py cpu.collapsed --app-prefix com.example.myapp"
    )
    parser.add_argument(
        "collapsed_file",
        type=str,
        help="Path to collapsed stacks file, or '-' to read from stdin"
    )
    parser.add_argument(
        "--app-prefix",
        default="",
        help="Package prefix of your application code (e.g. com.example.myapp or com/example/myapp). "
             "Used to distinguish your code from infrastructure layers in the distribution."
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of hot stacks to display (default: 10)"
    )
    parser.add_argument(
        "--format",
        choices=["txt", "md"],
        default="txt",
        help="Output format (default: txt)"
    )

    args = parser.parse_args()

    # Read input
    if args.collapsed_file == "-":
        content = sys.stdin.read()
        source_file = "<stdin>"
    else:
        collapsed_path = Path(args.collapsed_file)
        if not collapsed_path.is_file():
            print(f"Error: file not found: {collapsed_path}", file=sys.stderr)
            sys.exit(1)
        try:
            content = collapsed_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
        source_file = collapsed_path.name

    # Validate
    if not validate_collapsed(content):
        print("Error: Invalid format - expected async-profiler collapsed stacks", file=sys.stderr)
        sys.exit(1)

    # Parse
    profile = parse_collapsed(content)

    if profile.total_samples == 0:
        print("Warning: No samples found in file", file=sys.stderr)

    # Analyze
    analysis = analyze(profile, app_prefix=args.app_prefix, top_n=args.top)

    # Generate reports
    report_md = generate_report(analysis, fmt="md", source_file=source_file)
    report_txt = generate_report(analysis, fmt="txt", source_file=source_file)

    # Write output files
    md_path = Path("async-profiler-diagnostic.md")
    txt_path = Path("async-profiler-diagnostic.txt")
    md_path.write_text(report_md, encoding="utf-8")
    txt_path.write_text(report_txt, encoding="utf-8")

    # Print requested format
    if args.format == "md":
        print(report_md)
    else:
        print(report_txt)

    print(f"\nReports written to: {md_path.absolute()} and {txt_path.absolute()}")


if __name__ == "__main__":
    main()
