#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from gc_diagnostic.parser import parse_log
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.reporter import generate_report


def main():
    parser = argparse.ArgumentParser(
        description="GC Flu Test: quick triage of G1 GC logs for common issues",
        epilog="Example: python get-gc-diagnostic.py samples/gc-fast.log --tail-window 2 --format md"
    )
    parser.add_argument("log_file", type=str, help="Path to the GC log file")
    parser.add_argument("--tail-window", type=int, default=None, help="Analyze only last N minutes")
    parser.add_argument("--old-trend-threshold", type=float, default=30.0, help="Retention growth threshold (regions/min)")
    parser.add_argument("--format", choices=["md", "txt"], default="txt", help="Output format")
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.is_file():
        print(f"Erreur: fichier introuvable : {log_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with log_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Erreur lecture fichier : {e}", file=sys.stderr)
        sys.exit(1)

    try:
        events = parse_log(lines)
    except ValueError as e:
        print(f"Erreur format log : {e}", file=sys.stderr)
        sys.exit(1)

    if not events:
        print("Aucun événement GC pertinent trouvé.", file=sys.stderr)
        sys.exit(0)

    findings = analyze_events(
        events,
        tail_minutes=args.tail_window,
        old_trend_threshold=args.old_trend_threshold
    )

    report = generate_report(findings, format=args.format)
    print(report)


if __name__ == "__main__":
    main()