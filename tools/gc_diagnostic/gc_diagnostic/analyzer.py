# gc_diagnostic/analyzer.py

from typing import List, Dict, Optional
from statistics import stdev  # stdlib pour variance (optionnel)


def filter_by_tail_window(
        events: List[Dict],
        tail_minutes: Optional[int] = None
) -> List[Dict]:
    """
    Filtre les événements pour ne garder que ceux des tail_minutes dernières minutes.
    Si tail_minutes est None → retourne tout.
    Si tail_minutes <= 0 → lève une erreur.
    """
    if tail_minutes is None:
        return events  # Pas de filtre → full log

    if tail_minutes <= 0:
        raise ValueError("tail_minutes must be positive")

    if not events:
        return []

    max_uptime = max(e['uptime_sec'] for e in events)
    cutoff = max_uptime - (tail_minutes * 60)

    filtered = [e for e in events if e['uptime_sec'] >= cutoff]

    return filtered


def detect_retention_growth(
        filtered_events: List[Dict],
        old_trend_threshold: float = 30.0
) -> Dict:
    """
    Détection spécifique au retention / leak-like (ancien code de analyze_events).
    """
    if len(filtered_events) < 3:
        return {
            "type": "retention_growth",
            "detected": False,
            "confidence": "low",
            "reason": f"only {len(filtered_events)} events",
            "events_count": len(filtered_events),
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # 2. Calcule le trend simple (delta / durée)
    first = filtered_events[0]
    last = filtered_events[-1]
    duration_min = (last['uptime_sec'] - first['uptime_sec']) / 60
    delta_regions = last['old_after_regions'] - first['old_after_regions']
    trend_regions_per_min = delta_regions / duration_min if duration_min > 0 else 0.0

    # 3. Détection
    detected = trend_regions_per_min > old_trend_threshold

    # 4. Confidence : nombre d'événements + monotonicité
    old_afters = [e['old_after_regions'] for e in filtered_events]
    is_monotonic = all(old_afters[i] <= old_afters[i + 1] for i in range(len(old_afters) - 1))
    confidence = (
        "high" if len(filtered_events) >= 5 and is_monotonic
        else "medium" if detected
        else "low"
    )

    # 5. Evidence lisible (avec tolérance pour line_num)
    evidence = []
    for e in filtered_events:
        line_str = f"Line {e.get('line_num', 'N/A')}: {e['old_after_regions']} regions at {e['uptime_sec'] / 60:.1f}min"
        evidence.append(line_str)

    # 6. Next steps business-oriented + business note
    next_steps = [
        "jcmd <pid> GC.class_histogram (check dominant classes)",
        "Short JFR capture (10-30 min, focus on allocations + GC phases)",
        "Heap dump + Eclipse MAT analysis (especially if trend persists after warmup/plateau)"
    ] if detected else []

    business_note = (
        "This pattern shows a steady increase in old generation occupancy. "
        "However, if the application is still in warmup/initial loading phase (e.g. caches, data structures filling up), "
        "this may be nominal growth until a plateau is reached. If a plateau is reached and growth continues → "
        "very strong leak signal. If no plateau after long runtime (several hours) → almost certain leak. "
        "Always compare with a baseline healthy run to distinguish nominal from leak-like behavior."
    ) if detected else ""

    return {
        "type": "retention_growth",
        "detected": detected,
        "confidence": confidence,
        "trend_regions_per_min": round(trend_regions_per_min, 1),
        "delta_regions": int(delta_regions),
        "duration_min": round(duration_min, 1),
        "events_count": len(filtered_events),
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
    }


def detect_long_stw_pauses(
        filtered_events: List[Dict],
        threshold_ms: int = 1000
) -> Dict:
    """
    Détection spécifique aux pauses STW longues.
    (À affiner avec parsing réel de pause_ms dans parser.py)
    """
    # Assume que 'pause_ms' est extrait dans parser.py (à implémenter)
    pauses = [e.get('pause_ms', 0) for e in filtered_events if 'pause_ms' in e]

    if not pauses:
        return {
            "type": "long_stw_pauses",
            "detected": False,
            "confidence": "low",
            "reason": "no pause data found",
            "evidence": [],
            "next_steps": []
        }

    long_pauses = [p for p in pauses if p >= threshold_ms]
    detected = len(long_pauses) >= 1

    confidence = (
        "high" if len(long_pauses) >= 3
        else "medium" if detected
        else "low"
    )

    evidence = [f"Pause of {p} ms" for p in long_pauses]

    next_steps = [
        "JFR recording (GC + safepoint + pause phases)",
        "Increase logging: -Xlog:gc*,safepoint*",
        "Thread dump during long pause if reproducible"
    ] if detected else []

    return {
        "type": "long_stw_pauses",
        "detected": detected,
        "confidence": confidence,
        "evidence": evidence,
        "next_steps": next_steps
    }


def analyze_events(
        events: List[Dict],
        tail_minutes: Optional[int] = None,
        old_trend_threshold: float = 30.0,
        stw_threshold_ms: int = 1000
) -> Dict:
    """
    Chef d'orchestre : applique filtre + appelle chaque détection de suspect + construit summary global.
    Scalable pour 6+ suspects.
    """
    filtered_events = filter_by_tail_window(events, tail_minutes)

    if not filtered_events:
        return {
            "summary": "NO STRONG SIGNAL (empty after filtering)",
            "suspects": []
        }

    # Liste des fonctions de détection (ajoute-en 6 autres ici plus tard)
    detections = [
        detect_retention_growth(filtered_events, old_trend_threshold),
        detect_long_stw_pauses(filtered_events, stw_threshold_ms),
        # Ajoute ici detect_allocation_pressure, detect_humongous, etc.
    ]

    # Filtre seulement les detected/suspected
    suspects = detections  # Tous les suspects analysés (détectés ou non)

    # Summary global
    detected_count = sum(1 for s in suspects if s["detected"])
    summary = f"{detected_count} issues DETECTED" if detected_count > 0 else "NO STRONG SIGNAL"

    return {
        "summary": summary,
        "suspects": suspects
    }
