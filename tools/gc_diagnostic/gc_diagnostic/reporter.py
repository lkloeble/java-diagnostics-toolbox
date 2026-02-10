# gc_diagnostic/reporter.py

from typing import Dict, Optional, List


# gc_diagnostic/reporter.py

from typing import Dict, Optional, List


def generate_report(findings: Dict, format: str = "txt", debug: bool = False) -> str:
    lines = []

    # Calcul du summary intelligent
    detected_suspects = [s for s in findings.get("suspects", []) if s["detected"]]
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

    # On récupère les données utiles une seule fois (globales)
    filtered_events = findings.get("filtered_events", [])
    stable_events = findings.get("stable_events", [])  # version nettoyée (sans crash final)
    region_size_mb = findings.get("region_size_mb", 1)

    # === MODE DEBUG ===
    if debug:
        lines.append("=== DEBUG MODE ACTIVATED ===")
        lines.append(f"Total suspects analyzed: {len(findings.get('suspects', []))}")
        lines.append(f"Detected suspects: {detected_count}")
        lines.append("")

        # Infos sur la fenêtre filtrée
        lines.append(f"Events after tail-window (brut): {len(filtered_events)}")
        lines.append(f"Stable events (sans crash final): {len(stable_events)}")
        if filtered_events:
            min_up = min(e['uptime_sec'] for e in filtered_events) / 60
            max_up = max(e['uptime_sec'] for e in filtered_events) / 60
            lines.append(f"Filtered uptime range (brut): {min_up:.1f} min to {max_up:.1f} min")

        # Liste brute → priorise stable_events, fallback filtered si vide
        display_events = stable_events if stable_events else filtered_events
        display_label = "stable events" if stable_events else "filtered events (fallback)"
        if display_events:
            lines.append(f"DEBUG - Raw data ({display_label}, Time (min) → Old Heap (MB)):")
            for e in display_events:
                mb = e['old_after_regions'] * region_size_mb
                lines.append(f"  {e['uptime_sec']/60:6.1f} min  →  {mb:6.0f} MB")
            lines.append("")

        # Graphe ASCII → priorise stable_events
        if stable_events and region_size_mb:
            graph = render_ascii_graph(stable_events, region_size_mb)
            lines.append(f"DEBUG - ASCII Graph ({display_label}, Old Heap in MB over time):")
            lines.append("```")
            lines.append(graph)
            lines.append("```")
        elif filtered_events and region_size_mb:
            graph = render_ascii_graph(filtered_events, region_size_mb)
            lines.append("DEBUG - ASCII Graph (filtered events fallback):")
            lines.append("```")
            lines.append(graph)
            lines.append("```")
        else:
            lines.append("DEBUG - No graph available (missing events or region_size_mb)")
        lines.append("")

    # Détails par suspect
    for suspect in findings.get("suspects", []):
        type_title = suspect["type"].replace("_", " ").title()
        status = "DETECTED" if suspect["detected"] else "NOT DETECTED"

        if format == "md":
            lines.append(f"## {type_title} - {status}")
            lines.append(f"**Confidence:** {suspect['confidence']}")
        else:
            lines.append(f"{type_title.upper()} - {status}")
            lines.append(f"Confidence: {suspect['confidence']}")

        # Toujours afficher le trend calculé (même si NOT DETECTED)
        if "trend_regions_per_min" in suspect:
            trend_val = suspect["trend_regions_per_min"]
            status_text = "(above threshold)" if suspect["detected"] else "(below threshold)"
            if format == "md":
                lines.append(f"**Trend:** {trend_val} regions/min {status_text}")
            else:
                lines.append(f"Trend: {trend_val} regions/min {status_text}")

        if suspect["detected"]:
            # Détails spécifiques au suspect
            if "delta_regions" in suspect:
                lines.append(f"Delta: +{suspect['delta_regions']} regions over {suspect['duration_min']} min")
            if "events_count" in suspect:
                lines.append(f"Events analyzed: {suspect['events_count']}")

            # Bloc spécifique retention_growth + OOM + occupation + graphe
            if suspect["type"] == "retention_growth":
                max_heap_mb = suspect.get("max_heap_mb")
                last_old_regions = suspect.get("last_old_regions", 0)
                trend_regions_per_min = suspect.get("trend_regions_per_min", 0)

                if region_size_mb:
                    old_current_mb = last_old_regions * region_size_mb

                    # Estimation OOM (seulement si trend positif)
                    if trend_regions_per_min > 0:
                        trend_mb_per_min = trend_regions_per_min * region_size_mb
                        oom_line = "OOM estimation not available"
                        if max_heap_mb:
                            remaining_mb = max_heap_mb * 0.9 - old_current_mb
                            if remaining_mb > 0:
                                minutes_remaining = remaining_mb / trend_mb_per_min
                                if minutes_remaining < 60:
                                    oom_line = f"Estimated time to potential OOM (~90%): {minutes_remaining:.0f} min"
                                else:
                                    hours = minutes_remaining / 60
                                    oom_line = f"Estimated time to potential OOM (~90%): {hours:.1f} h"
                            else:
                                oom_line = "Heap already critically full → immediate OOM risk"

                        if format == "md":
                            lines.append(f"**{oom_line}**")
                        else:
                            lines.append(oom_line)

                    # Occupation heap
                    if max_heap_mb:
                        occupation_pct = (old_current_mb / max_heap_mb * 100)
                        occupation_line = f"Heap occupation: ~{old_current_mb:.0f} / {max_heap_mb:.0f} MB ({occupation_pct:.1f}%)"
                        if format == "md":
                            lines.append(f"**{occupation_line}**")
                        else:
                            lines.append(occupation_line)

                    # Graphe ASCII de l'évolution mémoire
                    graph_events = suspect.get("stable_events") or suspect.get("filtered_events") or []
                    if graph_events:
                        lines.append("")
                        if format == "md":
                            lines.append("**Memory trend (Old Gen):**")
                            lines.append("```")
                        else:
                            lines.append("Memory trend (Old Gen):")
                        graph = render_ascii_graph(graph_events, region_size_mb)
                        lines.append(graph)
                        if format == "md":
                            lines.append("```")

            # Evidence, business note, next steps
            if format == "md":
                lines.append("")
                lines.append("**Evidence:**")
            else:
                lines.append("\nEvidence:")
            for ev in suspect.get("evidence", []):
                lines.append(f"  - {ev}")

            if suspect.get("business_note"):
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



def render_ascii_graph(events: List[Dict], region_size_mb: float, width: int = 40, height: int = 12) -> str:
    if not events or region_size_mb <= 0:
        return "No graph available (missing data)"

    # 1. Préparer les points : (temps_min, old_mb)
    points = []
    for e in events:
        time_min = e['uptime_sec'] / 60
        old_mb = e['old_after_regions'] * region_size_mb
        points.append((time_min, old_mb))

    if not points:
        return "No points to plot"

    # 2. Normaliser
    min_time = min(p[0] for p in points)
    max_time = max(p[0] for p in points)
    time_range = max_time - min_time if max_time > min_time else 1

    min_mb = min(p[1] for p in points)
    max_mb = max(p[1] for p in points)
    mb_range = max_mb - min_mb if max_mb > min_mb else 1

    # 3. Créer la grille
    grid = [[' ' for _ in range(width)] for _ in range(height)]

    # 4. Placer les points
    for time, mb in points:
        x = int((time - min_time) / time_range * (width - 1))
        y = int((mb - min_mb) / mb_range * (height - 1))
        y = height - 1 - y  # inverser Y (haut = max)
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] = '•'

    # 5. Ajouter axes
    for y in range(height):
        grid[y][0] = '|'
    for x in range(width):
        grid[height-1][x] = '-'
    grid[height-1][0] = '+'

    # 6. Labels simples (optionnel)
    # On peut ajouter min/max sur les bords

    # 7. Convertir en texte
    graph_lines = [''.join(row) for row in grid]

    # Ajouter labels
    graph_lines.append(f"0{' ' * (width-8)}{max_time:.0f} min")
    graph_lines.append(f"{min_mb:.0f} MB{' ' * (width-10)}{max_mb:.0f} MB")

    return "\n".join(graph_lines)