# async_profiler_diagnostic/parser.py

from dataclasses import dataclass, field
from typing import List


@dataclass
class StackEntry:
    """A single collapsed stack with its sample count.

    frames: [root_frame, ..., hot_leaf_frame]
    Leftmost = thread entry point, rightmost = hot frame (where CPU was at sample time).
    """
    frames: List[str]
    count: int


@dataclass
class ProfileData:
    """Parsed async-profiler collapsed stacks output."""
    stacks: List[StackEntry] = field(default_factory=list)
    total_samples: int = 0


def parse_collapsed(content: str) -> ProfileData:
    """
    Parse async-profiler collapsed stacks format into structured data.

    Each line: frame1;frame2;...;frameN count
    Lines starting with '#' are treated as comments and skipped.
    """
    profile = ProfileData()

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        last_space = line.rfind(' ')
        if last_space == -1:
            continue

        frames_part = line[:last_space]
        count_part = line[last_space + 1:]

        try:
            count = int(count_part)
        except ValueError:
            continue

        frames = [f for f in frames_part.split(';') if f]
        if frames:
            profile.stacks.append(StackEntry(frames=frames, count=count))
            profile.total_samples += count

    return profile


def validate_collapsed(content: str) -> bool:
    """
    Check if content looks like a valid collapsed stacks file.

    Returns True if at least one valid 'frames count' line is found.
    """
    if not content or len(content) < 5:
        return False

    for line in content.splitlines()[:20]:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.rsplit(' ', 1)
        if len(parts) == 2:
            try:
                int(parts[1])
                return True
            except ValueError:
                pass

    return False
