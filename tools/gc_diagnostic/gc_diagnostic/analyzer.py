def compute_old_gen_trend(events: list[dict]) -> float:
    if len(events) < 2:
        return 0.0
    start_time, end_time = events[0]['uptime'], events[-1]['uptime']
    start_old, end_old = events[0]['old_after'], events[-1]['old_after']
    time_delta_min = (end_time - start_time) / 60
    if time_delta_min == 0:
        return 0.0
    return (end_old - start_old) / time_delta_min  # Simple linear mb/min.


def analyze_events(events: list[dict], tail_window_min: int | None, old_trend_threshold: int) -> dict:
    if tail_window_min:
        max_uptime = max(e['uptime'] for e in events) if events else 0
        events = [e for e in events if e['uptime'] >= max_uptime - (tail_window_min * 60)]

    if not events:
        return {'summary': 'NO STRONG SIGNAL',
                'retention_growth': {'detected': False, 'confidence': 'low', 'evidence': [], 'next_steps': []}}

    trend = compute_old_gen_trend(events)
    detected = trend > old_trend_threshold
    confidence = 'high' if len(events) > 1 and detected else 'low'
    evidence = [e['line_num'] for e in events] if detected else []
    next_steps = ['jcmd GC.class_histogram', 'heap dump + MAT', 'short JFR capture'] if detected else []

    return {
        'summary': 'DETECTED: Retention growth' if detected else 'NO STRONG SIGNAL',
        'retention_growth': {'detected': detected, 'confidence': confidence, 'evidence': evidence,
                             'next_steps': next_steps}
    }