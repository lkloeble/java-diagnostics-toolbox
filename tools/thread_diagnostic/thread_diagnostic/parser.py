# thread_diagnostic/parser.py

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ThreadInfo:
    """Represents a single thread from a thread dump."""
    name: str
    tid: Optional[str] = None
    nid: Optional[str] = None
    state: Optional[str] = None  # RUNNABLE, WAITING, BLOCKED, TIMED_WAITING
    daemon: bool = False
    priority: Optional[int] = None
    stack_trace: List[str] = field(default_factory=list)
    locked_monitors: List[str] = field(default_factory=list)
    waiting_on: Optional[str] = None  # Lock/monitor this thread is waiting on
    holding_locks: List[str] = field(default_factory=list)


@dataclass
class ThreadDump:
    """Represents a complete thread dump."""
    timestamp: Optional[str] = None
    jvm_info: Optional[str] = None
    threads: List[ThreadInfo] = field(default_factory=list)
    deadlocks: List[Dict] = field(default_factory=list)


# Thread header pattern:
# "pool-1-thread-3" #15 daemon prio=5 os_prio=0 tid=0x00007f... nid=0x1234 waiting on condition
THREAD_HEADER_PATTERN = re.compile(
    r'^"([^"]+)"'  # Thread name in quotes
    r'\s+#(\d+)'   # Thread number
    r'(?:\s+(daemon))?'  # Optional daemon flag
    r'\s+prio=(\d+)'  # Priority
    r'(?:\s+os_prio=\d+)?'  # Optional OS priority
    r'(?:\s+cpu=[\d.]+ms)?'  # Optional CPU time
    r'(?:\s+elapsed=[\d.]+s)?'  # Optional elapsed time
    r'\s+tid=(0x[0-9a-fA-F]+)'  # Thread ID
    r'\s+nid=(0x[0-9a-fA-F]+|\d+)'  # Native ID
    r'\s+(.+)$'  # State description
)

# Thread state line: java.lang.Thread.State: WAITING (parking)
THREAD_STATE_PATTERN = re.compile(
    r'^\s+java\.lang\.Thread\.State:\s+(\w+)'
)

# Waiting on lock: - waiting on <0x00000000e1234567> (a java.util.concurrent.locks...)
WAITING_ON_PATTERN = re.compile(
    r'^\s+-\s+(?:waiting on|waiting to lock|parking to wait for)\s+<(0x[0-9a-fA-F]+)>'
)

# Holding lock: - locked <0x00000000e1234567> (a java.lang.Object)
LOCKED_PATTERN = re.compile(
    r'^\s+-\s+locked\s+<(0x[0-9a-fA-F]+)>'
)

# Deadlock detection header
DEADLOCK_PATTERN = re.compile(
    r'^Found (\d+) deadlock'
)


def parse_thread_dump(content: str) -> ThreadDump:
    """
    Parse a jstack thread dump into structured data.

    Args:
        content: Raw thread dump text (from jstack output)

    Returns:
        ThreadDump object with parsed threads and deadlock info
    """
    lines = content.splitlines()
    dump = ThreadDump()

    current_thread: Optional[ThreadInfo] = None
    in_stack_trace = False

    for i, line in enumerate(lines):
        # Check for timestamp (first line usually)
        if i == 0 and line.startswith("20"):
            dump.timestamp = line.strip()
            continue

        # Check for JVM info
        if "Full thread dump" in line:
            dump.jvm_info = line.strip()
            continue

        # Check for deadlock
        deadlock_match = DEADLOCK_PATTERN.search(line)
        if deadlock_match:
            # TODO: Parse deadlock details
            dump.deadlocks.append({"detected": True, "count": int(deadlock_match.group(1))})
            continue

        # Check for thread header
        header_match = THREAD_HEADER_PATTERN.match(line)
        if header_match:
            # Save previous thread if exists
            if current_thread:
                dump.threads.append(current_thread)

            current_thread = ThreadInfo(
                name=header_match.group(1),
                daemon=header_match.group(3) == "daemon",
                priority=int(header_match.group(4)),
                tid=header_match.group(5),
                nid=header_match.group(6),
            )
            in_stack_trace = True
            continue

        # If we're in a thread block, parse additional info
        if current_thread and in_stack_trace:
            # Thread state
            state_match = THREAD_STATE_PATTERN.match(line)
            if state_match:
                current_thread.state = state_match.group(1)
                continue

            # Waiting on lock
            waiting_match = WAITING_ON_PATTERN.match(line)
            if waiting_match:
                current_thread.waiting_on = waiting_match.group(1)
                continue

            # Holding lock
            locked_match = LOCKED_PATTERN.match(line)
            if locked_match:
                current_thread.holding_locks.append(locked_match.group(1))
                continue

            # Stack trace line
            if line.startswith("\tat ") or line.startswith("	at "):
                current_thread.stack_trace.append(line.strip())
                continue

            # Empty line = end of thread block
            if line.strip() == "":
                in_stack_trace = False
                continue

    # Don't forget last thread
    if current_thread:
        dump.threads.append(current_thread)

    return dump


def validate_thread_dump(content: str) -> bool:
    """
    Check if content looks like a valid thread dump.

    Returns True if it appears to be a jstack output.
    """
    if not content or len(content) < 100:
        return False

    # Must have "Full thread dump" or thread patterns
    if "Full thread dump" in content:
        return True

    # Or at least some thread headers
    if THREAD_HEADER_PATTERN.search(content):
        return True

    return False
