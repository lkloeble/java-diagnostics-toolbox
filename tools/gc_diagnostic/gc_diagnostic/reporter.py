def generate_report(findings: dict, format: str = 'md') -> str:
    summary = findings['summary']
    growth = findings['retention_growth']

    if format == 'md':
        report = "# GC Diagnostic Report\n\n"
        report += f"**Summary:** {summary}  \n"  # Business: "Potential impact: downtime if unaddressed."
        if growth['detected']:
            report += "## Detected Issues\n- Retention / memory leak-like growth  \n"
            report += f"Confidence: {growth['confidence']}  \n"
            report += "## Evidence\n" + "\n".join(f"- Line {ln}" for ln in growth['evidence']) + "  \n"
            report += "## Next Low-Effort Data\n" + "\n".join(f"- {step}" for step in growth['next_steps'])
        else:
            report += "## No Detected Issues\nSuspected: None with high confidence."
    elif format == 'txt':
        report = "GC Diagnostic Report\n\n"
        report += f"Summary: {summary}\n"
        if growth['detected']:
            report += "Detected Issues:\n- Retention / memory leak-like growth\n"
            report += f"Confidence: {growth['confidence']}\n"
            report += "Evidence:\n" + "\n".join(f"- Line {ln}" for ln in growth['evidence']) + "\n"
            report += "Next Low-Effort Data:\n" + "\n".join(f"- {step}" for step in growth['next_steps'])
        else:
            report += "No Detected Issues\nSuspected: None with high confidence."
    else:
        raise ValueError("Invalid format")

    report += "\n\nBusiness Value: Fast triage to minimize incident impact."
    return report