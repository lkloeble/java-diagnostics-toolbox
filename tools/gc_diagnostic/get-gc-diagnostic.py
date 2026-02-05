#!/usr/bin/env python
import sys
from gc_diagnostic.parser import parse_log
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.reporter import generate_report


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: get-gc-diagnostic.py /path/to/gc.log [--tail-window <min>] [--old-trend-mb-per-min <int>] [--format md|txt]",
            file=sys.stderr)
        sys.exit(1)

    log_path = sys.argv[1]
    tail_window = None
    threshold = 10
    fmt = 'md'

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--tail-window':
            tail_window = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--old-trend-mb-per-min':
            threshold = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--format':
            fmt = sys.argv[i + 1]
            if fmt not in ('md', 'txt'):
                print("Invalid format", file=sys.stderr)
                sys.exit(1)
            i += 2
        else:
            print("Unknown option", file=sys.stderr)
            sys.exit(1)

    try:
        with open(log_path, 'r') as f:
            lines = f.read().strip().splitlines()
        events = parse_log(lines)
        findings = analyze_events(events, tail_window, threshold)
        report = generate_report(findings, fmt)
        print(report)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()