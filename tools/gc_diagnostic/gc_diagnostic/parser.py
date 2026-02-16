import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class GCEvent:
    """Represents a single GC event with all extracted data."""
    gc_number: int
    timestamp: str
    uptime_sec: float
    line_num: int = 0
    # GC type info
    gc_type: Optional[str] = None           # "Young (Normal)", "Young (Mixed)", "Full", etc.
    # Old generation
    old_before_regions: Optional[int] = None
    old_after_regions: Optional[int] = None
    # Humongous
    humongous_before: Optional[int] = None
    humongous_after: Optional[int] = None
    # Heap totals (in MB)
    heap_before_mb: Optional[int] = None
    heap_after_mb: Optional[int] = None
    heap_total_mb: Optional[int] = None
    # Metaspace (in KB for precision)
    metaspace_used_kb: Optional[int] = None
    metaspace_committed_kb: Optional[int] = None
    # TLAB stats (requires -Xlog:gc+tlab=debug)
    tlab_thrds: Optional[int] = None        # Number of threads with TLAB
    tlab_refills: Optional[int] = None      # Total TLAB refills
    tlab_slow_allocs: Optional[int] = None  # Slow path allocations (TLAB exhaustion)
    tlab_waste_pct: Optional[float] = None  # TLAB waste percentage
    # Pause
    pause_ms: Optional[float] = None
    # Flags
    evacuation_failure: bool = False
    metadata_gc_threshold: bool = False  # GC triggered by Metaspace pressure

    def to_dict(self) -> Dict:
        """Convert to dict for backward compatibility."""
        return {
            'gc_number': self.gc_number,
            'line_num': self.line_num,
            'timestamp': self.timestamp,
            'uptime_sec': self.uptime_sec,
            'gc_type': self.gc_type,
            'old_before_regions': self.old_before_regions,
            'old_after_regions': self.old_after_regions,
            'humongous_before': self.humongous_before,
            'humongous_after': self.humongous_after,
            'heap_before_mb': self.heap_before_mb,
            'heap_after_mb': self.heap_after_mb,
            'heap_total_mb': self.heap_total_mb,
            'metaspace_used_kb': self.metaspace_used_kb,
            'metaspace_committed_kb': self.metaspace_committed_kb,
            'tlab_thrds': self.tlab_thrds,
            'tlab_refills': self.tlab_refills,
            'tlab_slow_allocs': self.tlab_slow_allocs,
            'tlab_waste_pct': self.tlab_waste_pct,
            'pause_ms': self.pause_ms,
            'evacuation_failure': self.evacuation_failure,
            'metadata_gc_threshold': self.metadata_gc_threshold,
        }


# Old regions pattern (gc,heap tag)
# Example: [2026-02-05T05:43:52.074+0200][22.113s][info][gc,heap     ] GC(0) Old regions: 0->17
OLD_REGIONS_PATTERN = re.compile(
    r'\[([^\]]+)\]'                     # group 1: timestamp
    r'\[([\d.]+)s\]'                    # group 2: uptime
    r'\[info\]\[gc,heap[^]]*\]'         # [gc,heap     ]
    r'\s*GC\((\d+)\)'                   # group 3: GC number
    r'.*Old\s+regions:\s*(\d+)\s*->\s*(\d+)'  # group 4,5: before->after
)

# Humongous regions pattern (gc,heap tag)
# Example: [2026-02-05T05:43:52.074+0200][22.113s][info][gc,heap     ] GC(0) Humongous regions: 0->0
HUMONGOUS_REGIONS_PATTERN = re.compile(
    r'\[([^\]]+)\]'                     # group 1: timestamp
    r'\[([\d.]+)s\]'                    # group 2: uptime
    r'\[info\]\[gc,heap[^]]*\]'         # [gc,heap     ]
    r'\s*GC\((\d+)\)'                   # group 3: GC number
    r'.*Humongous\s+regions:\s*(\d+)\s*->\s*(\d+)'  # group 4,5: before->after
)

# Main pause line pattern (gc tag only, not gc,heap)
# Example: [2026-02-05T05:43:52.074+0200][22.113s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 22M->19M(256M) 8.657ms
# Example with evacuation failure: GC(1074) Pause Young (Mixed) (G1 Evacuation Pause) (Evacuation Failure) 766M->766M(1024M) 3.510ms
PAUSE_LINE_PATTERN = re.compile(
    r'\[([^\]]+)\]'                     # group 1: timestamp
    r'\[([\d.]+)s\]'                    # group 2: uptime
    r'\[info\]\[gc\s*\]'                # [gc] or [gc          ] (NOT gc,heap)
    r'\s*GC\((\d+)\)'                   # group 3: GC number
    r'\s+(Pause\s+\S+(?:\s+\([^)]+\))?)'  # group 4: GC type (Pause Young (Normal), Pause Full, etc.)
    r'.*?'                              # skip intermediate content
    r'(\d+)([KMG]?)->(\d+)([KMG]?)\((\d+)([KMG]?)\)'  # groups 5-10: heap before->after(total)
    r'\s+([\d.]+)ms'                    # group 11: pause time
)

# Evacuation Failure detection (simple substring check is faster)
EVACUATION_FAILURE_MARKER = '(Evacuation Failure)'

# Metadata GC Threshold detection (GC triggered by Metaspace pressure)
METADATA_GC_THRESHOLD_MARKER = '(Metadata GC Threshold)'

# Metaspace pattern (gc,metaspace tag)
# Example: [2026-02-15T07:06:43.878+0200][1.216s][info][gc,metaspace] GC(0) Metaspace: 15817K(16384K)->15817K(16384K) NonClass: ...
METASPACE_PATTERN = re.compile(
    r'\[([^\]]+)\]'                     # group 1: timestamp
    r'\[([\d.]+)s\]'                    # group 2: uptime
    r'\[info\]\[gc,metaspace\]'         # [gc,metaspace]
    r'\s*GC\((\d+)\)'                   # group 3: GC number
    r'\s*Metaspace:\s*(\d+)K\((\d+)K\)' # groups 4,5: used(committed) before
    r'\s*->\s*(\d+)K\((\d+)K\)'         # groups 6,7: used(committed) after
)

# TLAB pattern (gc,tlab tag - requires -Xlog:gc+tlab=debug)
# Example: [2026-02-16T05:21:12.890+0200][0.075s][debug][gc,tlab] GC(0) TLAB totals: thrds: 20  refills: 59 max: 5 slow allocs: 19 max 4 waste: 23.0% ...
TLAB_PATTERN = re.compile(
    r'\[([^\]]+)\]'                     # group 1: timestamp
    r'\[([\d.]+)s\]'                    # group 2: uptime
    r'\[debug\]\[gc,tlab\]'             # [gc,tlab] at debug level
    r'\s*GC\((\d+)\)'                   # group 3: GC number
    r'\s*TLAB totals:'
    r'\s*thrds:\s*(\d+)'                # group 4: number of threads
    r'\s+refills:\s*(\d+)'              # group 5: total refills
    r'\s+max:\s*\d+'                    # skip max refills per thread
    r'\s+slow allocs:\s*(\d+)'          # group 6: slow allocations
    r'\s+max\s+\d+'                     # skip max slow allocs per thread
    r'\s+waste:\s*([0-9.]+)%'           # group 7: waste percentage
)


# Regex pour Heap Max Capacity
HEAP_MAX_PATTERN = re.compile(
    r'\[gc,init\].*Heap Max Capacity:\s*(\d+)([KMG]?)',
    re.IGNORECASE
)

# Regex pour Heap Region Size
HEAP_REGION_PATTERN = re.compile(
    r'\[gc,init\].*Heap Region Size:\s*(\d+)([KMG]?)',
    re.IGNORECASE
)

# Collector type pattern
# Example: [2026-02-05T05:43:29.965+0200][0.004s][info][gc     ] Using G1
# Possible values: G1, Serial, Parallel, ZGC, Shenandoah
COLLECTOR_PATTERN = re.compile(
    r'\[info\]\[gc\s*\]\s*Using\s+(G1|Serial|Parallel|ZGC|Shenandoah)',
    re.IGNORECASE
)


def _parse_size(value: str, unit: str) -> int:
    """Convert size with unit to MB."""
    num = int(value)
    unit = unit.upper() if unit else ''
    if unit == 'K':
        return num // 1024
    elif unit == 'M' or unit == '':
        return num
    elif unit == 'G':
        return num * 1024
    return num


def _parse_size_mb(value: str, unit: str) -> int:
    """Convert heap size to MB. Wrapper for clarity."""
    return _parse_size(value, unit)


def extract_heap_max_capacity(lines: list[str]) -> Optional[int]:
    """
    Recherche la capacité max de la heap (en Mo).
    Retourne None si non trouvée.
    """
    for line in lines[:20]:  # on cherche dans les 20 premières lignes
        match = HEAP_MAX_PATTERN.search(line)
        if match:
            value, unit = match.groups()
            return _parse_size(value, unit)
    return None


def extract_heap_region_size(lines: list[str]) -> Optional[int]:
    """
    Recherche la taille d'une region G1 (en Mo).
    Retourne None si non trouvée.
    """
    for line in lines[:20]:
        match = HEAP_REGION_PATTERN.search(line)
        if match:
            value, unit = match.groups()
            return _parse_size(value, unit)
    return None


def extract_collector_type(lines: list[str]) -> Optional[str]:
    """
    Recherche le type de collector GC utilisé.
    Retourne: 'G1', 'Serial', 'Parallel', 'ZGC', 'Shenandoah', ou None si non trouvé.
    """
    for line in lines[:20]:
        match = COLLECTOR_PATTERN.search(line)
        if match:
            return match.group(1)
    return None


def validate_log_format(lines: List[str]) -> None:
    if not lines:
        raise ValueError("Log file is empty")
    # Vérification minimale : présence d'au moins un GC event + G1 mentionné quelque part
    has_g1 = any("G1" in line for line in lines[:10])
    has_heap_event = any("gc,heap" in line for line in lines)
    if not (has_g1 and has_heap_event):
        raise ValueError("Invalid format: expected G1 unified logging with gc,heap events")


def parse_log(lines: List[str]) -> List[Dict]:
    """
    Parse G1 GC log lines and extract structured events.

    Correlates data from multiple lines (pause line, old regions, humongous)
    by GC number to build complete events.

    Returns list of dicts for backward compatibility.
    """
    validate_log_format(lines)

    # Dict to accumulate event data by GC number
    events_by_gc: Dict[int, GCEvent] = {}

    for line_num, line in enumerate(lines, start=1):
        # Try pause line first (main GC info)
        match = PAUSE_LINE_PATTERN.search(line)
        if match:
            timestamp, uptime_str, gc_num_str, gc_type = match.group(1, 2, 3, 4)
            heap_before, heap_before_unit = match.group(5, 6)
            heap_after, heap_after_unit = match.group(7, 8)
            heap_total, heap_total_unit = match.group(9, 10)
            pause_ms_str = match.group(11)

            gc_num = int(gc_num_str)

            if gc_num not in events_by_gc:
                events_by_gc[gc_num] = GCEvent(
                    gc_number=gc_num,
                    timestamp=timestamp,
                    uptime_sec=float(uptime_str),
                )

            event = events_by_gc[gc_num]
            event.line_num = line_num
            event.gc_type = gc_type.strip()
            event.heap_before_mb = _parse_size_mb(heap_before, heap_before_unit)
            event.heap_after_mb = _parse_size_mb(heap_after, heap_after_unit)
            event.heap_total_mb = _parse_size_mb(heap_total, heap_total_unit)
            event.pause_ms = float(pause_ms_str)
            event.evacuation_failure = EVACUATION_FAILURE_MARKER in line
            event.metadata_gc_threshold = METADATA_GC_THRESHOLD_MARKER in line
            continue

        # Try old regions pattern
        match = OLD_REGIONS_PATTERN.search(line)
        if match:
            timestamp, uptime_str, gc_num_str, before_str, after_str = match.groups()
            gc_num = int(gc_num_str)

            if gc_num not in events_by_gc:
                events_by_gc[gc_num] = GCEvent(
                    gc_number=gc_num,
                    timestamp=timestamp,
                    uptime_sec=float(uptime_str),
                )

            event = events_by_gc[gc_num]
            event.old_before_regions = int(before_str)
            event.old_after_regions = int(after_str)
            if event.line_num == 0:
                event.line_num = line_num
            continue

        # Try humongous regions pattern
        match = HUMONGOUS_REGIONS_PATTERN.search(line)
        if match:
            timestamp, uptime_str, gc_num_str, before_str, after_str = match.groups()
            gc_num = int(gc_num_str)

            if gc_num not in events_by_gc:
                events_by_gc[gc_num] = GCEvent(
                    gc_number=gc_num,
                    timestamp=timestamp,
                    uptime_sec=float(uptime_str),
                )

            event = events_by_gc[gc_num]
            event.humongous_before = int(before_str)
            event.humongous_after = int(after_str)
            continue

        # Try metaspace pattern
        match = METASPACE_PATTERN.search(line)
        if match:
            timestamp, uptime_str, gc_num_str = match.group(1, 2, 3)
            # We take the "after" values (groups 6,7) as current state
            metaspace_used_after = match.group(6)
            metaspace_committed_after = match.group(7)
            gc_num = int(gc_num_str)

            if gc_num not in events_by_gc:
                events_by_gc[gc_num] = GCEvent(
                    gc_number=gc_num,
                    timestamp=timestamp,
                    uptime_sec=float(uptime_str),
                )

            event = events_by_gc[gc_num]
            event.metaspace_used_kb = int(metaspace_used_after)
            event.metaspace_committed_kb = int(metaspace_committed_after)
            continue

        # Try TLAB pattern (requires -Xlog:gc+tlab=debug)
        match = TLAB_PATTERN.search(line)
        if match:
            timestamp, uptime_str, gc_num_str = match.group(1, 2, 3)
            thrds = match.group(4)
            refills = match.group(5)
            slow_allocs = match.group(6)
            waste_pct = match.group(7)
            gc_num = int(gc_num_str)

            if gc_num not in events_by_gc:
                events_by_gc[gc_num] = GCEvent(
                    gc_number=gc_num,
                    timestamp=timestamp,
                    uptime_sec=float(uptime_str),
                )

            event = events_by_gc[gc_num]
            event.tlab_thrds = int(thrds)
            event.tlab_refills = int(refills)
            event.tlab_slow_allocs = int(slow_allocs)
            event.tlab_waste_pct = float(waste_pct)
            continue

    # Convert to list, filter events that have old regions data, sort by uptime
    events = [
        e.to_dict() for e in events_by_gc.values()
        if e.old_after_regions is not None
    ]
    events.sort(key=lambda e: e['uptime_sec'])

    return events