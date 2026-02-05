#!/usr/bin/env python
import sys
from gc_diagnostic.parser import parse_log
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.reporter import generate_report


def detect_retention_growth(events: list[dict], threshold_mb_per_min: float = 10.0) -> dict:
    if len(events) < 3:  # Au moins 3 points pour une tendance fiable
        return {
            'detected': False,
            'confidence': 'low',
            'reason': 'insufficient GC events in window',
            'trend_per_min': 0.0,
            'evidence': []
        }

    # Trier par uptime (normalement déjà ordonné, mais sécurité)
    events = sorted(events, key=lambda e: e['uptime_sec'])

    times_min = [e['uptime_sec'] / 60 for e in events]
    old_after = [e['old_after_regions'] for e in events]

    # Trend simple : (dernier - premier) / durée
    duration_min = times_min[-1] - times_min[0]
    if duration_min <= 0:
        return {'detected': False, 'confidence': 'low'}

    delta_regions = old_after[-1] - old_after[0]
    trend_regions_per_min = delta_regions / duration_min

    # Pour l'instant on utilise regions (pas MB), mais on pourra convertir plus tard si besoin
    detected = trend_regions_per_min > 2.0  # À calibrer ! (ex. >2 regions/min = suspect)

    # Confidence : regarder si monotone croissante (pas de gros drop)
    is_monotone_up = all(old_after[i] <= old_after[i + 1] for i in range(len(old_after) - 1))
    confidence = 'high' if detected and is_monotone_up and len(events) >= 5 else 'medium' if detected else 'low'

    evidence_lines = [
        f"Line {e['line_num']}: Old regions after GC = {e['old_after_regions']} at {e['uptime_sec'] / 60:.1f} min"
        for e in events
    ]

    return {
        'detected': detected,
        'confidence': confidence,
        'trend_regions_per_min': round(trend_regions_per_min, 2),
        'evidence': evidence_lines,
        'next_steps': ["jcmd GC.class_histogram", "heap dump + MAT"] if detected else []
    }

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