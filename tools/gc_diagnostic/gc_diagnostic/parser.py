import re
from typing import List, Dict

OLD_REGIONS_PATTERN = re.compile(
    r'\[([^\]]+)\]'                     # timestamp
    r'\[([\d.]+)s\]'                    # uptime
    r'\[info\]\[gc,heap[^]]*\]'         # [gc,heap     ] ou n'importe quoi entre crochets
    r'\s*GC\(\d+\)'                     # GC(10)
    r'.*Old\s+regions:\s*(\d+)\s*->\s*(\d+)'  # Old regions: 214 -> 227 (espaces partout)
)

def validate_log_format(lines: List[str]) -> None:
    if not lines:
        raise ValueError("Log file is empty")
    # Vérification minimale : présence d'au moins un GC event + G1 mentionné quelque part
    has_g1 = any("G1" in line for line in lines[:10])
    has_heap_event = any("gc,heap" in line for line in lines)
    if not (has_g1 and has_heap_event):
        raise ValueError("Invalid format: expected G1 unified logging with gc,heap events")


def parse_log(lines: List[str]) -> List[Dict]:
    validate_log_format(lines)
    events: List[Dict] = []

    for line_num, line in enumerate(lines, start=1):
        match = OLD_REGIONS_PATTERN.search(line)
        if match:
            timestamp, uptime_str, before_str, after_str = match.groups()
            events.append({
                'line_num': line_num,
                'timestamp': timestamp,
                'uptime_sec': float(uptime_str),
                'old_before_regions': int(before_str),
                'old_after_regions': int(after_str),
            })

    return events