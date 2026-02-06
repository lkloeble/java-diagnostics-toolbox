# gc_diagnostic/reporter.py

from typing import Dict


def generate_report(findings: Dict, format: str = "txt") -> str:
    lines = []

    # Calcul du summary intelligent
    detected_suspects = [s for s in findings["suspects"] if s["detected"]]
    detected_count = len(detected_suspects)

    if detected_count == 0:
        summary_line = "NO STRONG SIGNAL"
    elif detected_count == 1:
        s = detected_suspects[0]
        type_name = s["type"].replace("_", " ").title()
        summary_line = f"DETECTED - {type_name} ({s['confidence']} confidence)"
    else:
        names = ", ".join(s["type"].replace("_", " ").title() for s in detected_suspects)
        summary_line = f"{detected_count} issues DETECTED → {names}"

    # Header
    if format == "md":
        lines.append("# GC Flu Test Report")
        lines.append("")
        lines.append(f"**Summary:** {summary_line}")
        lines.append("")
    else:
        lines.append("=== GC Flu Test Report ===")
        lines.append(f"Summary: {summary_line}")
        lines.append("")

    # Détails par suspect
    for suspect in findings["suspects"]:
        type_title = suspect["type"].replace("_", " ").title()
        status = "DETECTED" if suspect["detected"] else "NOT DETECTED"

        if format == "md":
            lines.append(f"## {type_title} - {status}")
            lines.append(f"**Confidence:** {suspect['confidence']}")
        else:
            lines.append(f"{type_title.upper()} - {status}")
            lines.append(f"Confidence: {suspect['confidence']}")

        if suspect["detected"]:
            # Détails spécifiques au suspect
            if "trend_regions_per_min" in suspect:
                lines.append(f"Trend: {suspect['trend_regions_per_min']} regions/min")
            if "delta_regions" in suspect:
                lines.append(f"Delta: +{suspect['delta_regions']} regions over {suspect['duration_min']} min")
            if "events_count" in suspect:
                lines.append(f"Events analyzed: {suspect['events_count']}")

            if format == "md":
                lines.append("")
                lines.append("**Evidence:**")
            else:
                lines.append("\nEvidence:")
            for ev in suspect.get("evidence", []):
                lines.append(f"  - {ev}")

            if "business_note" in suspect and suspect["business_note"]:
                if format == "md":
                    lines.append("")
                    lines.append("**Business note:**")
                else:
                    lines.append("\nBusiness note:")
                lines.append(suspect["business_note"])

            if format == "md":
                lines.append("")
                lines.append("**Next low-effort data:**")
            else:
                lines.append("\nNext low-effort data:")
            for step in suspect.get("next_steps", []):
                lines.append(f"  - {step}")

        lines.append("")

    return "\n".join(lines)