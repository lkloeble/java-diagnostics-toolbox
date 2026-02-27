# thread_diagnostic/analyzer.py

import re
from typing import List, Dict, Optional
from collections import Counter, defaultdict
from .parser import ThreadDump, ThreadInfo


def detect_deadlocks(dump: ThreadDump) -> Dict:
    """
    Detect deadlocks in thread dump.

    Deadlocks are often explicitly listed by jstack, but we also
    check for circular lock dependencies.
    """
    detected = len(dump.deadlocks) > 0
    evidence = []
    threads_involved = []

    if detected:
        for dl in dump.deadlocks:
            evidence.append(f"JVM reported {dl.get('count', 'N')} deadlock(s)")

    # Additional: check for circular wait patterns
    # Thread A holds lock X, waits for Y
    # Thread B holds lock Y, waits for X
    lock_holders = {}  # lock_id -> thread_name
    lock_waiters = {}  # lock_id -> [thread_names]

    for thread in dump.threads:
        for lock in thread.holding_locks:
            lock_holders[lock] = thread.name
        if thread.waiting_on:
            if thread.waiting_on not in lock_waiters:
                lock_waiters[thread.waiting_on] = []
            lock_waiters[thread.waiting_on].append(thread.name)

    # Find cycles (simplified: A waits for lock held by B, B waits for lock held by A)
    for thread in dump.threads:
        if thread.waiting_on and thread.waiting_on in lock_holders:
            holder = lock_holders[thread.waiting_on]
            # Skip if same thread (Object.wait() holds and waits on same monitor)
            if holder == thread.name:
                continue
            holder_thread = next((t for t in dump.threads if t.name == holder), None)
            if holder_thread and holder_thread.waiting_on:
                # Check if holder is waiting for a lock held by current thread
                for lock in thread.holding_locks:
                    if holder_thread.waiting_on == lock:
                        detected = True
                        evidence.append(f"Circular wait: {thread.name} <-> {holder}")
                        threads_involved.extend([thread.name, holder])

    return {
        "type": "deadlock",
        "detected": detected,
        "confidence": "high" if detected else "low",
        "evidence": evidence,
        "threads_involved": list(set(threads_involved)),
        "business_note": "DEADLOCK DETECTED: Application is frozen. Threads are waiting for each other in a circular dependency. Requires code fix or restart." if detected else "",
        "next_steps": [
            "Identify lock acquisition order in code",
            "Review synchronized blocks in stack traces",
            "Consider using tryLock with timeout",
        ] if detected else []
    }


def detect_lock_contention(dump: ThreadDump, threshold: int = 3) -> Dict:
    """
    Detect multiple threads blocked on the same lock.

    High contention = many threads waiting for the same resource.
    """
    # Group threads by what they're waiting on
    waiting_groups = defaultdict(list)
    for thread in dump.threads:
        if thread.waiting_on and thread.state == "BLOCKED":
            waiting_groups[thread.waiting_on].append(thread.name)

    # Find locks with multiple waiters
    contended_locks = {
        lock: waiters
        for lock, waiters in waiting_groups.items()
        if len(waiters) >= threshold
    }

    detected = len(contended_locks) > 0
    evidence = []
    max_contention = 0

    for lock, waiters in contended_locks.items():
        evidence.append(f"{len(waiters)} threads blocked on lock {lock}")
        max_contention = max(max_contention, len(waiters))

    # Find who holds the contended locks
    for lock in contended_locks:
        for thread in dump.threads:
            if lock in thread.holding_locks:
                evidence.append(f"Lock {lock} held by: {thread.name}")
                # Add top of stack trace
                if thread.stack_trace:
                    evidence.append(f"  at {thread.stack_trace[0]}")
                break

    confidence = "low"
    if max_contention >= 10:
        confidence = "high"
    elif max_contention >= threshold:
        confidence = "medium"

    return {
        "type": "lock_contention",
        "detected": detected,
        "confidence": confidence,
        "contended_locks": len(contended_locks),
        "max_waiters": max_contention,
        "evidence": evidence,
        "business_note": f"LOCK CONTENTION: {max_contention} threads competing for same lock. This serializes execution and kills throughput." if detected else "",
        "next_steps": [
            "Review synchronized blocks - can scope be reduced?",
            "Consider concurrent collections (ConcurrentHashMap vs synchronized Map)",
            "Check for lock held during I/O operations",
            "Profile with JFR to identify lock hotspots",
        ] if detected else []
    }


def detect_thread_pool_saturation(dump: ThreadDump, waiting_threshold_pct: float = 80.0) -> Dict:
    """
    Detect thread pools where most threads are waiting/blocked.

    Saturation = pool can't keep up with demand.
    """
    # Group threads by pool name pattern
    pool_pattern_prefixes = [
        "pool-", "http-", "tomcat-", "jetty-", "grpc-", "kafka-",
        "rabbitmq-", "worker-", "executor-", "scheduler-", "async-"
    ]

    pools = defaultdict(list)
    for thread in dump.threads:
        for prefix in pool_pattern_prefixes:
            if thread.name.lower().startswith(prefix):
                # Extract pool name (e.g., "pool-1" from "pool-1-thread-5")
                parts = thread.name.split("-thread-")
                pool_name = parts[0] if len(parts) > 1 else thread.name.rsplit("-", 1)[0]
                pools[pool_name].append(thread)
                break

    saturated_pools = []
    evidence = []

    for pool_name, threads in pools.items():
        if len(threads) < 2:
            continue

        waiting_count = sum(1 for t in threads if t.state in ("WAITING", "TIMED_WAITING", "BLOCKED"))
        waiting_pct = (waiting_count / len(threads)) * 100

        if waiting_pct >= waiting_threshold_pct:
            saturated_pools.append({
                "name": pool_name,
                "total": len(threads),
                "waiting": waiting_count,
                "waiting_pct": waiting_pct
            })
            evidence.append(f"{pool_name}: {waiting_count}/{len(threads)} threads waiting ({waiting_pct:.0f}%)")

    detected = len(saturated_pools) > 0
    confidence = "high" if any(p["waiting_pct"] >= 90 for p in saturated_pools) else "medium" if detected else "low"

    return {
        "type": "thread_pool_saturation",
        "detected": detected,
        "confidence": confidence,
        "saturated_pools": saturated_pools,
        "evidence": evidence,
        "business_note": "THREAD POOL SATURATION: Worker threads are starved. Requests are likely queuing up or timing out." if detected else "",
        "next_steps": [
            "Check pool queue size (may be full)",
            "Increase pool size if CPU/memory allows",
            "Look for blocking I/O in worker threads",
            "Check downstream dependencies (DB, external APIs)",
        ] if detected else []
    }


def detect_stuck_threads(dump: ThreadDump, min_same_location: int = 3) -> Dict:
    """
    Detect multiple threads stuck at the same location.

    Pattern: Many threads with identical top-of-stack = something blocking.
    """
    # Group by top of stack trace
    location_groups = defaultdict(list)
    for thread in dump.threads:
        if thread.stack_trace and thread.state in ("RUNNABLE", "BLOCKED", "WAITING"):
            # Use top 2 frames for grouping (more specific)
            top_frames = tuple(thread.stack_trace[:2])
            location_groups[top_frames].append(thread)

    stuck_locations = []
    evidence = []

    for location, threads in location_groups.items():
        if len(threads) >= min_same_location:
            stuck_locations.append({
                "location": location,
                "count": len(threads),
                "thread_names": [t.name for t in threads[:5]],  # Sample
                "state": threads[0].state
            })
            evidence.append(f"{len(threads)} threads at: {location[0] if location else 'unknown'}")

    detected = len(stuck_locations) > 0
    confidence = "high" if any(s["count"] >= 10 for s in stuck_locations) else "medium" if detected else "low"

    return {
        "type": "stuck_threads",
        "detected": detected,
        "confidence": confidence,
        "locations": stuck_locations,
        "evidence": evidence,
        "business_note": "STUCK THREADS: Multiple threads blocked at same code location. Likely a bottleneck or blocked resource." if detected else "",
        "next_steps": [
            "Check the common stack frame - what resource does it access?",
            "Look for socket reads, DB queries, file I/O at that location",
            "Compare multiple dumps to confirm threads aren't making progress",
        ] if detected else []
    }


_IO_STALL_FRAMES = [
    "SocketDispatcher.read0",       # NIO socket read (Java 11+)
    "SocketInputStream.read",       # Classic blocking socket read
    "SocketInputStream.socketRead0", # Older Java
    "FileDispatcher.read0",         # NIO file read
    "FileInputStream.read0",        # Classic file read
]

_JDK_FRAME_PREFIXES = ("at java.", "at javax.", "at sun.", "at jdk.", "at com.sun.")


def _is_io_stall_frame(frame: str) -> bool:
    return any(p in frame for p in _IO_STALL_FRAMES)


def _find_app_frame(stack_trace: List[str]) -> Optional[str]:
    """Return the first user (non-JDK) frame below the I/O stall frame."""
    io_found = False
    for frame in stack_trace:
        if not io_found:
            if _is_io_stall_frame(frame):
                io_found = True
            continue
        if frame.startswith("at ") and not any(frame.startswith(p) for p in _JDK_FRAME_PREFIXES):
            return frame
    return None


def detect_io_stalls(dump: ThreadDump, min_stalled: int = 3) -> Dict:
    """
    Detect threads blocked on network or file I/O.

    These threads appear RUNNABLE in the dump (they are in a native blocking
    call) but are not making progress — they are waiting for data from a
    socket or file that is not responding.
    """
    stalled = []
    for thread in dump.threads:
        if thread.state == "RUNNABLE" and thread.stack_trace:
            if any(_is_io_stall_frame(f) for f in thread.stack_trace):
                stalled.append(thread)

    detected = len(stalled) >= min_stalled

    # Group by application frame to show where in the code the stall originates
    app_groups: Dict[str, list] = defaultdict(list)
    for thread in stalled:
        app_frame = _find_app_frame(thread.stack_trace) or "unknown"
        app_groups[app_frame].append(thread.name)

    evidence = []
    if detected:
        evidence.append(f"{len(stalled)} threads blocked on network/file I/O")
        for app_frame, names in sorted(app_groups.items(), key=lambda x: -len(x[1])):
            evidence.append(f"{len(names)} threads at: {app_frame}")

    confidence = "high" if len(stalled) >= 10 else "medium" if detected else "low"

    return {
        "type": "io_stalls",
        "detected": detected,
        "confidence": confidence,
        "stalled_count": len(stalled),
        "evidence": evidence,
        "business_note": (
            f"I/O STALL: {len(stalled)} threads blocked waiting for network or file data. "
            "Likely a slow/unresponsive downstream dependency (DB, external API, filesystem)."
        ) if detected else "",
        "next_steps": [
            "Identify the downstream target from the stack trace (DB host, API endpoint, file path)",
            "Check latency/availability of that dependency",
            "Look for connection pool exhaustion or missing read timeout configuration",
            "Compare multiple dumps to confirm threads are not making progress",
        ] if detected else [],
    }


def detect_cpu_storm(dump: ThreadDump, runnable_threshold_pct: float = 50.0, min_cluster: int = 3) -> Dict:
    """
    Detect high RUNNABLE ratio combined with thread clustering at the same stack location.

    A high RUNNABLE % alone is normal for CPU-bound apps. The signal is
    RUNNABLE threads piling up at the same frame — hot loop or spinlock.
    """
    threads_with_state = [t for t in dump.threads if t.state]
    if not threads_with_state:
        return {
            "type": "cpu_storm",
            "detected": False,
            "confidence": "low",
            "runnable_pct": 0.0,
            "hot_locations": [],
            "evidence": [],
            "business_note": "",
            "next_steps": [],
        }

    runnable_threads = [t for t in threads_with_state if t.state == "RUNNABLE" and t.stack_trace]
    runnable_count = sum(1 for t in threads_with_state if t.state == "RUNNABLE")
    runnable_pct = (runnable_count / len(threads_with_state)) * 100

    # Group RUNNABLE threads by top stack frame
    location_groups: Dict[str, list] = defaultdict(list)
    for thread in runnable_threads:
        location_groups[thread.stack_trace[0]].append(thread)

    hot_locations = sorted(
        [
            {
                "location": loc,
                "count": len(threads),
                "thread_names": [t.name for t in threads[:5]],
            }
            for loc, threads in location_groups.items()
            if len(threads) >= min_cluster
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    detected = runnable_pct >= runnable_threshold_pct and len(hot_locations) > 0
    confidence = "high" if runnable_pct >= 70 and hot_locations else "medium" if detected else "low"

    evidence = []
    if detected:
        evidence.append(
            f"{runnable_pct:.0f}% of threads RUNNABLE ({runnable_count}/{len(threads_with_state)})"
        )
    for loc in hot_locations:
        evidence.append(f"{loc['count']} RUNNABLE threads at: {loc['location']}")

    return {
        "type": "cpu_storm",
        "detected": detected,
        "confidence": confidence,
        "runnable_pct": round(runnable_pct, 1),
        "hot_locations": hot_locations,
        "evidence": evidence,
        "business_note": (
            f"CPU STORM: {runnable_pct:.0f}% of threads are RUNNABLE and clustering at the same location. "
            "Likely a hot loop, spinlock, or runaway computation exhausting CPU."
        ) if detected else "",
        "next_steps": [
            "Take a CPU profile (async-profiler, JFR) to confirm the hot method",
            "Check if the clustering frame is a tight loop or busy-wait",
            "Compare CPU% in top/jstat — high CPU confirms active spinning",
            "Take multiple dumps 5s apart to confirm threads are not making progress",
        ] if detected else [],
    }


def compute_thread_state_summary(dump: ThreadDump) -> Dict:
    """
    Compute summary statistics on thread states.
    """
    state_counts = Counter(t.state for t in dump.threads if t.state)
    daemon_count = sum(1 for t in dump.threads if t.daemon)

    return {
        "total_threads": len(dump.threads),
        "daemon_threads": daemon_count,
        "states": dict(state_counts),
        "runnable": state_counts.get("RUNNABLE", 0),
        "waiting": state_counts.get("WAITING", 0),
        "timed_waiting": state_counts.get("TIMED_WAITING", 0),
        "blocked": state_counts.get("BLOCKED", 0),
    }


def _thread_group_key(name: str) -> str:
    """Strip trailing index to get logical group name."""
    # Handle -N and #N patterns (e.g. worker-3, GC Thread#0)
    stripped = re.sub(r'[-#]\d+$', '', name).strip()
    if stripped and stripped != name:
        return stripped
    # Handle trailing digits without separator (e.g. C2 CompilerThread0)
    stripped = re.sub(r'\d+$', '', name).strip()
    if stripped and len(stripped) >= 3:
        return stripped
    return name


def compute_thread_group_inventory(dump: ThreadDump) -> List[Dict]:
    """
    Group threads by logical name prefix, sorted by count descending.

    Strips trailing -N / #N indices to identify groups (e.g. worker-1..4 → worker).
    Useful for spotting unusual thread counts vs. nominal baseline.
    """
    groups: Dict[str, list] = defaultdict(list)
    for thread in dump.threads:
        key = _thread_group_key(thread.name)
        groups[key].append(thread)

    result = []
    for name, threads in groups.items():
        state_counts = Counter(t.state for t in threads if t.state)
        result.append({
            "name": name,
            "count": len(threads),
            "runnable": state_counts.get("RUNNABLE", 0),
            "waiting": state_counts.get("WAITING", 0),
            "timed_waiting": state_counts.get("TIMED_WAITING", 0),
            "blocked": state_counts.get("BLOCKED", 0),
        })

    return sorted(result, key=lambda g: g["count"], reverse=True)


def analyze_thread_dump(dump: ThreadDump) -> Dict:
    """
    Main analysis orchestrator - runs all detectors and builds findings.
    """
    suspects = [
        detect_deadlocks(dump),
        detect_lock_contention(dump),
        detect_thread_pool_saturation(dump),
        detect_stuck_threads(dump),
        detect_cpu_storm(dump),
        detect_io_stalls(dump),
    ]

    thread_stats = compute_thread_state_summary(dump)
    thread_groups = compute_thread_group_inventory(dump)
    detected_count = sum(1 for s in suspects if s["detected"])
    summary = f"{detected_count} issues DETECTED" if detected_count > 0 else "NO STRONG SIGNAL"

    return {
        "summary": summary,
        "suspects": suspects,
        "thread_stats": thread_stats,
        "thread_groups": thread_groups,
        "jvm_info": dump.jvm_info,
        "timestamp": dump.timestamp,
    }
