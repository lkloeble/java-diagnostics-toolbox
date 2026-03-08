# async_profiler_diagnostic/reporter.py

from typing import Dict, Any, List

_MAX_DISPLAY_FRAMES = 4  # frames shown per hot stack (leaf end of the stack)


def _format_stack_path(frames: List[str], max_frames: int = _MAX_DISPLAY_FRAMES) -> str:
    """
    Show the hot end of a stack, truncating from the root if needed.

    Example (4 frames max, 12-frame stack):
      ... → UserService.findById → AbstractProducedQuery.list → ClientPreparedStatement.executeQuery → NativeSession.execSQL
    """
    if len(frames) <= max_frames:
        return " → ".join(frames)
    tail = frames[-max_frames:]
    return "... → " + " → ".join(tail)


def generate_report(analysis: Dict[str, Any], fmt: str = "txt", source_file: str = "") -> str:
    """Generate diagnostic report in txt or md format."""
    total = analysis.get("total_samples", 0)
    num_stacks = analysis.get("num_stacks", 0)
    app_prefix = analysis.get("app_prefix", "")
    layer_dist = analysis.get("layer_distribution", [])
    hot_stacks = analysis.get("hot_stacks", [])

    lines = []

    if fmt == "md":
        lines.append("# Async-Profiler Diagnostic")
        lines.append("")
        if source_file:
            lines.append(f"**File:** `{source_file}`")
        lines.append(f"**Total samples:** {total:,}  |  **Distinct stacks:** {num_stacks:,}")
        if app_prefix:
            lines.append(f"**App prefix:** `{app_prefix}`")
        lines.append("")

        lines.append("## Layer Distribution")
        lines.append("")
        lines.append("*Classified by the leaf (hot) frame of each stack.*")
        lines.append("")
        lines.append("| Layer | Samples | % |")
        lines.append("|:------|--------:|------:|")
        for entry in layer_dist:
            lines.append(f"| {entry['layer']} | {entry['samples']:,} | {entry['pct']:.1f}% |")
        lines.append("")

        lines.append(f"## Top {len(hot_stacks)} Hot Stacks")
        lines.append("")
        lines.append("*Frames shown left (context) → right (hot leaf). Long stacks truncated from the root.*")
        lines.append("")
        for s in hot_stacks:
            path = _format_stack_path(s["frames"])
            lines.append(f"**#{s['rank']}** [{s['count']:,} samples — {s['pct']:.1f}%] `{s['layer']}`")
            lines.append("")
            lines.append(f"```")
            lines.append(path)
            lines.append(f"```")
            lines.append("")

    else:  # txt
        SEP = "=" * 60
        sep = "-" * 60

        lines.append(SEP)
        lines.append("ASYNC-PROFILER DIAGNOSTIC")
        if source_file:
            lines.append(f"File   : {source_file}")
        lines.append(f"Samples: {total:,}  |  Stacks: {num_stacks:,}")
        if app_prefix:
            lines.append(f"Prefix : {app_prefix}")
        lines.append(SEP)
        lines.append("")

        # Layer distribution with ASCII bar chart
        lines.append("LAYER DISTRIBUTION  (by leaf / hot frame)")
        lines.append(sep)
        if layer_dist:
            max_pct = max(e["pct"] for e in layer_dist)
            bar_scale = 28.0 / max(max_pct, 1)
            for entry in layer_dist:
                bar = "█" * int(entry["pct"] * bar_scale)
                lines.append(
                    f"  {entry['layer']:<14}  {entry['samples']:>6,}  {entry['pct']:>5.1f}%  {bar}"
                )
        else:
            lines.append("  (no data)")
        lines.append("")

        # Hot stacks
        lines.append(f"TOP {len(hot_stacks)} HOT STACKS")
        lines.append(sep)
        if hot_stacks:
            for s in hot_stacks:
                lines.append(
                    f"#{s['rank']}  [{s['count']:,} samples — {s['pct']:.1f}%]  {s['layer']}"
                )
                path = _format_stack_path(s["frames"])
                lines.append(f"  {path}")
                lines.append("")
        else:
            lines.append("  (no data)")
            lines.append("")

    return "\n".join(lines)
