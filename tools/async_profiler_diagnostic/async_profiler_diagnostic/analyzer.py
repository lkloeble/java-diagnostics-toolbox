# async_profiler_diagnostic/analyzer.py

from typing import List, Dict, Any

from .parser import ProfileData


# Layer classification rules — order matters, first match wins.
# Prefixes use slash notation (JVM bytecode style).
LAYER_RULES: List[tuple] = [
    ("Spring",    ["org/springframework", "org/spring"]),
    ("Hibernate", ["org/hibernate", "jakarta/persistence", "javax/persistence"]),
    ("JDBC",      ["java/sql", "javax/sql", "com/mysql", "org/postgresql", "oracle/jdbc", "com/zaxxer", "org/h2"]),
    ("JDK",       ["java/", "javax/", "jdk/", "sun/", "com/sun/"]),
    # JVM/Native is the fallback for frames with no '/' (C/C++ symbols, OS frames)
]


def classify_frame(frame: str, app_prefix: str) -> str:
    """
    Classify a single frame into a layer.

    app_prefix accepts both dot notation (com.example.myapp)
    and slash notation (com/example/myapp) — normalised internally.
    """
    norm = frame.replace('.', '/')
    app_norm = app_prefix.replace('.', '/') if app_prefix else ""

    if app_norm and norm.startswith(app_norm):
        return "App"

    for layer, prefixes in LAYER_RULES:
        for prefix in prefixes:
            if norm.startswith(prefix):
                return layer

    # Native/JVM frames: no '/' in the frame (C/C++ symbols, OS calls, JVM internals)
    if '/' not in frame:
        return "JVM/Native"

    return "Other"


def analyze(profile: ProfileData, app_prefix: str = "", top_n: int = 10) -> Dict[str, Any]:
    """
    Analyze a parsed profile:
      - Layer distribution by leaf (hot) frame
      - Top N hot stacks sorted by sample count
    """
    if not profile.stacks or profile.total_samples == 0:
        return {
            "total_samples": 0,
            "num_stacks": 0,
            "app_prefix": app_prefix,
            "layer_distribution": [],
            "hot_stacks": [],
        }

    # Layer distribution: classify by the rightmost (hot leaf) frame of each stack
    layer_counts: Dict[str, int] = {}
    for stack in profile.stacks:
        if not stack.frames:
            continue
        leaf = stack.frames[-1]
        layer = classify_frame(leaf, app_prefix)
        layer_counts[layer] = layer_counts.get(layer, 0) + stack.count

    layer_distribution = sorted(
        [
            {
                "layer": layer,
                "samples": count,
                "pct": round(100.0 * count / profile.total_samples, 1),
            }
            for layer, count in layer_counts.items()
        ],
        key=lambda x: -x["samples"],
    )

    # Top N hot stacks by sample count
    sorted_stacks = sorted(profile.stacks, key=lambda s: -s.count)[:top_n]
    hot_stacks = []
    for rank, stack in enumerate(sorted_stacks, 1):
        leaf = stack.frames[-1] if stack.frames else ""
        layer = classify_frame(leaf, app_prefix)
        hot_stacks.append({
            "rank": rank,
            "count": stack.count,
            "pct": round(100.0 * stack.count / profile.total_samples, 1),
            "frames": stack.frames,
            "leaf": leaf,
            "layer": layer,
        })

    return {
        "total_samples": profile.total_samples,
        "num_stacks": len(profile.stacks),
        "app_prefix": app_prefix,
        "layer_distribution": layer_distribution,
        "hot_stacks": hot_stacks,
    }
