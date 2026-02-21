# thread_diagnostic/reporter.py

from typing import Dict


# Severity levels and their indicators
SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_OK = "ok"

SEVERITY_EMOJI = {
    SEVERITY_CRITICAL: "🔴",
    SEVERITY_WARNING: "🟡",
    SEVERITY_OK: "🟢",
}


def compute_suspect_severity(suspect: Dict) -> str:
    """Compute severity based on suspect type and confidence."""
    if not suspect.get("detected"):
        return SEVERITY_OK

    suspect_type = suspect.get("type", "")
    confidence = suspect.get("confidence", "low")

    # Deadlock is always critical
    if suspect_type == "deadlock":
        return SEVERITY_CRITICAL

    # High confidence issues are critical
    if confidence == "high":
        return SEVERITY_CRITICAL

    return SEVERITY_WARNING


def generate_slack_summary(findings: Dict) -> str:
    """Generate one-liner for Slack/incident channels."""
    suspects = findings.get("suspects", [])
    detected = [s for s in suspects if s.get("detected")]
    thread_stats = findings.get("thread_stats", {})

    # Thread count suffix
    total = thread_stats.get("total_threads", 0)
    blocked = thread_stats.get("blocked", 0)
    threads_suffix = f"{total} threads"
    if blocked > 0:
        threads_suffix += f" ({blocked} blocked)"

    if not detected:
        return f"🟢 HEALTHY: No issues | {threads_suffix}"

    # Compute severity
    severities = [compute_suspect_severity(s) for s in detected]
    if SEVERITY_CRITICAL in severities:
        status = "CRITICAL"
        emoji = SEVERITY_EMOJI[SEVERITY_CRITICAL]
    else:
        status = "WARNING"
        emoji = SEVERITY_EMOJI[SEVERITY_WARNING]

    # Build issue list
    issues = []
    for s in detected:
        stype = s.get("type", "")
        if stype == "deadlock":
            issues.append("DEADLOCK")
        elif stype == "lock_contention":
            max_w = s.get("max_waiters", 0)
            issues.append(f"Lock contention ({max_w} waiters)")
        elif stype == "thread_pool_saturation":
            pools = s.get("saturated_pools", [])
            issues.append(f"Pool saturation ({len(pools)} pools)")
        elif stype == "stuck_threads":
            locs = s.get("locations", [])
            issues.append(f"Stuck threads ({len(locs)} locations)")

    return f"{emoji} {status}: {', '.join(issues)} | {threads_suffix}"


def generate_report(findings: Dict, format: str = "txt") -> str:
    """Generate full diagnostic report."""
    lines = []
    suspects = findings.get("suspects", [])
    detected = [s for s in suspects if s.get("detected")]
    detected_count = len(detected)
    thread_stats = findings.get("thread_stats", {})

    # Summary line
    if detected_count == 0:
        summary_line = f"{SEVERITY_EMOJI[SEVERITY_OK]} NO STRONG SIGNAL"
    else:
        severities = [compute_suspect_severity(s) for s in detected]
        max_sev = SEVERITY_CRITICAL if SEVERITY_CRITICAL in severities else SEVERITY_WARNING
        names = ", ".join(s["type"].replace("_", " ").title() for s in detected)
        summary_line = f"{SEVERITY_EMOJI[max_sev]} {detected_count} issues DETECTED → {names}"

    # Header
    if format == "md":
        lines.append("# Thread Dump Diagnostic Report")
        lines.append("")
        if findings.get("timestamp"):
            lines.append(f"**Timestamp:** {findings['timestamp']}")
        if findings.get("jvm_info"):
            lines.append(f"**JVM:** {findings['jvm_info']}")
        lines.append("")
        lines.append(f"**Summary:** {summary_line}")
        lines.append("")
    else:
        lines.append("=== Thread Dump Diagnostic Report ===")
        if findings.get("timestamp"):
            lines.append(f"Timestamp: {findings['timestamp']}")
        if findings.get("jvm_info"):
            lines.append(f"JVM: {findings['jvm_info']}")
        lines.append(f"Summary: {summary_line}")
        lines.append("")

    # Thread statistics
    if format == "md":
        lines.append("## Thread Statistics")
        lines.append(f"**Total threads:** {thread_stats.get('total_threads', 0)}")
        lines.append(f"**Daemon threads:** {thread_stats.get('daemon_threads', 0)}")
        lines.append("")
        lines.append("| State | Count |")
        lines.append("|-------|-------|")
        lines.append(f"| RUNNABLE | {thread_stats.get('runnable', 0)} |")
        lines.append(f"| WAITING | {thread_stats.get('waiting', 0)} |")
        lines.append(f"| TIMED_WAITING | {thread_stats.get('timed_waiting', 0)} |")
        lines.append(f"| BLOCKED | {thread_stats.get('blocked', 0)} |")
        lines.append("")
    else:
        lines.append("Thread Statistics")
        lines.append(f"  Total:         {thread_stats.get('total_threads', 0)}")
        lines.append(f"  Daemon:        {thread_stats.get('daemon_threads', 0)}")
        lines.append(f"  RUNNABLE:      {thread_stats.get('runnable', 0)}")
        lines.append(f"  WAITING:       {thread_stats.get('waiting', 0)}")
        lines.append(f"  TIMED_WAITING: {thread_stats.get('timed_waiting', 0)}")
        lines.append(f"  BLOCKED:       {thread_stats.get('blocked', 0)}")
        lines.append("")

    # Suspects
    for suspect in suspects:
        type_title = suspect["type"].replace("_", " ").title()
        status = "DETECTED" if suspect["detected"] else "NOT DETECTED"
        severity = compute_suspect_severity(suspect)
        emoji = SEVERITY_EMOJI[severity]

        if format == "md":
            lines.append(f"## {emoji} {type_title} - {status}")
            lines.append(f"**Confidence:** {suspect['confidence']}")
        else:
            lines.append(f"{emoji} {type_title.upper()} - {status}")
            lines.append(f"Confidence: {suspect['confidence']}")

        if suspect["detected"]:
            # Evidence
            if format == "md":
                lines.append("")
                lines.append("**Evidence:**")
            else:
                lines.append("\nEvidence:")
            for ev in suspect.get("evidence", []):
                lines.append(f"  - {ev}")

            # Business note
            if suspect.get("business_note"):
                if format == "md":
                    lines.append("")
                    lines.append("**Business note:**")
                else:
                    lines.append("\nBusiness note:")
                lines.append(suspect["business_note"])

            # Next steps
            if format == "md":
                lines.append("")
                lines.append("**Next data to collect:**")
            else:
                lines.append("\nNext data to collect:")
            for step in suspect.get("next_steps", []):
                lines.append(f"  - {step}")

        lines.append("")

    # Slack summary
    slack_line = generate_slack_summary(findings)
    lines.append("---")
    if format == "md":
        lines.append("**Slack summary (copy-paste):**")
        lines.append(f"```\n{slack_line}\n```")
    else:
        lines.append("Slack summary (copy-paste):")
        lines.append(slack_line)
    lines.append("")

    return "\n".join(lines)
