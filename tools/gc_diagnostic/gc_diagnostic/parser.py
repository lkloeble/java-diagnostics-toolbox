import re

def validate_log_format(lines: list[str]) -> None:
    if not lines:
        raise ValueError("Empty log file")
    if "Using G1" not in lines[0]:
        raise ValueError("Invalid log format: Must be Java 9+ unified logging with G1")
    # Check first event line pattern.
    pattern = re.compile(r'\[\d{4}-\d{2}-\d{2}T.*\]\[\d+\.\d+s\]\[info\]\[gc.*\]')
    if not pattern.match(lines[1]):
        raise ValueError("Invalid log format: Does not match expected unified pattern")

def parse_log(lines: list[str]) -> list[dict]:
    validate_log_format(lines)
    events = []
    for i, line in enumerate(lines[1:], start=1):  # Skip first "Using G1".
        if '[gc,heap]' not in line:
            continue
        # Mock parse: [ts][up][info][gc,heap] GC#N Heap: before->after (max) Old: before->after
        parts = re.search(r'\[(\d+\.\d+)s\].*Old: (\d+)M->(\d+)M', line)
        if parts:
            events.append({
                'line_num': i + 1,  # 1-indexed.
                'uptime': float(parts.group(1)),
                'old_after': int(parts.group(3))
            })
    return events