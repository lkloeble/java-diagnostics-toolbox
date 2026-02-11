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
        old_trend_threshold: float = 30.0,
        delta_regions_threshold: int = 200,
        max_heap_mb: Optional[float] = None,
        region_size_mb: Optional[float] = None
) -> Dict:
    """
    Détection de memory leak / retention growth.

    Détecte via deux signaux complémentaires:
    1. Trend (regions/min) - détecte les leaks rapides
    2. Delta absolu (regions) - détecte les augmentations significatives (warmup ou leak lent)

    Sans tail-window: détecte toute augmentation significative de mémoire
    Avec tail-window: permet de distinguer warmup (début) vs leak continu (fin)
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

    # Filtrage défensif du dernier événement (OOM/crash artifact)
    # Si chute > 90% → probable restart/OOM, on ignore
    effective_events = filtered_events
    oom_filtered = False
    if len(filtered_events) >= 2:
        before_last = filtered_events[-2]['old_after_regions']
        last_val = filtered_events[-1]['old_after_regions']
        drop_pct = (before_last - last_val) / before_last if before_last > 0 else 0
        if drop_pct > 0.90:  # chute > 90% → probable OOM/crash
            effective_events = filtered_events[:-1]
            oom_filtered = True

    if len(effective_events) < 3:
        return {
            "type": "retention_growth",
            "detected": False,
            "confidence": "low",
            "reason": f"only {len(effective_events)} stable events after OOM filter",
            "events_count": len(filtered_events),
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Calculs de base sur les événements stables
    first = effective_events[0]
    last = effective_events[-1]
    duration_min = (last['uptime_sec'] - first['uptime_sec']) / 60
    delta_regions = last['old_after_regions'] - first['old_after_regions']
    trend_regions_per_min = delta_regions / duration_min if duration_min > 0 else 0.0

    # Calcul occupation heap si infos disponibles
    heap_occupation_pct = None
    delta_mb = None
    if region_size_mb:
        delta_mb = delta_regions * region_size_mb
        if max_heap_mb and max_heap_mb > 0:
            current_old_mb = last['old_after_regions'] * region_size_mb
            heap_occupation_pct = (current_old_mb / max_heap_mb) * 100

    # === LOGIQUE DE DÉTECTION ===
    # Signal 1: Trend élevé (leak rapide)
    detected_by_trend = trend_regions_per_min > old_trend_threshold

    # Signal 2: Delta absolu significatif (warmup massif ou leak lent)
    detected_by_delta = delta_regions > delta_regions_threshold

    # Signal 3: Occupation critique (>80% de la heap Old gen)
    detected_by_occupation = heap_occupation_pct is not None and heap_occupation_pct > 80

    # Détection finale: trend OU delta OU occupation critique
    detected = detected_by_trend or detected_by_delta or detected_by_occupation

    # === CONFIDENCE ===
    old_afters = [e['old_after_regions'] for e in effective_events]
    is_monotonic = all(old_afters[i] <= old_afters[i + 1] for i in range(len(old_afters) - 1))

    # Calcul de confidence basé sur les signaux
    if detected:
        signals_count = sum([detected_by_trend, detected_by_delta, detected_by_occupation])
        if signals_count >= 2 and is_monotonic:
            confidence = "high"
        elif detected_by_trend and is_monotonic and len(effective_events) >= 5:
            confidence = "high"
        elif detected_by_trend:
            confidence = "medium"
        elif detected_by_delta and delta_regions > delta_regions_threshold * 2:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "low"

    # === EVIDENCE ===
    evidence = []
    # Résumé des signaux
    if detected_by_trend:
        evidence.append(f"Trend signal: {trend_regions_per_min:.1f} regions/min (threshold: {old_trend_threshold})")
    if detected_by_delta:
        evidence.append(f"Delta signal: +{delta_regions} regions over {duration_min:.1f} min")
    if detected_by_occupation:
        evidence.append(f"Heap occupation: {heap_occupation_pct:.1f}% (critical >80%)")
    if oom_filtered:
        evidence.append("Note: Last event filtered (suspected OOM/restart artifact)")

    # Points de données clés (premier, milieu, dernier)
    evidence.append(f"Start: {first['old_after_regions']} regions at {first['uptime_sec']/60:.1f}min")
    if len(effective_events) > 2:
        mid_idx = len(effective_events) // 2
        mid = effective_events[mid_idx]
        evidence.append(f"Mid: {mid['old_after_regions']} regions at {mid['uptime_sec']/60:.1f}min")
    evidence.append(f"End: {last['old_after_regions']} regions at {last['uptime_sec']/60:.1f}min")

    stable_events = effective_events

    # === NEXT STEPS ===
    next_steps = []
    if detected:
        if duration_min > 30 and not detected_by_trend:
            # Long duration mais trend faible → probable warmup, suggérer tail-window
            next_steps.append(f"Use --tail-window 30 to analyze only recent data (exclude warmup)")
        next_steps.extend([
            "jcmd <pid> GC.class_histogram (check dominant classes)",
            "Short JFR capture (10-30 min, focus on allocations + GC phases)",
            "Heap dump + Eclipse MAT analysis"
        ])

    # === BUSINESS NOTE ===
    if detected:
        if detected_by_occupation and heap_occupation_pct >= 95:
            business_note = (
                "CRITICAL: Old generation is nearly full ({:.0f}%). "
                "Application is at high risk of OutOfMemoryError. "
                "Immediate action required: heap dump + investigation."
            ).format(heap_occupation_pct)
        elif detected_by_occupation:
            business_note = (
                "WARNING: Old generation occupation is high ({:.0f}%). "
                "This indicates significant memory retention. "
                "If application is not in warmup phase, this likely indicates a memory leak."
            ).format(heap_occupation_pct)
        elif detected_by_trend:
            business_note = (
                "ACTIVE LEAK PATTERN: Old generation is growing at a significant rate. "
                "This indicates objects are being retained and not collected. "
                "Immediate investigation recommended."
            )
        elif detected_by_delta and duration_min > 60:
            business_note = (
                "SIGNIFICANT MEMORY GROWTH detected over a long period. "
                "This could be: (1) Application warmup/cache filling - normal if it plateaus, "
                "(2) Slow memory leak - problematic if growth continues. "
                "Use --tail-window to analyze only recent data and distinguish warmup from leak."
            )
        else:
            business_note = (
                "Memory retention detected. If application just started, this may be normal warmup. "
                "Monitor if growth continues after expected warmup period."
            )
    else:
        business_note = ""

    return {
        "type": "retention_growth",
        "detected": detected,
        "confidence": confidence,
        "trend_regions_per_min": round(trend_regions_per_min, 1),
        "delta_regions": int(delta_regions),
        "delta_mb": int(delta_mb) if delta_mb else None,
        "duration_min": round(duration_min, 1),
        "events_count": len(filtered_events),
        "heap_occupation_pct": round(heap_occupation_pct, 1) if heap_occupation_pct else None,
        "detected_by_trend": detected_by_trend,
        "detected_by_delta": detected_by_delta,
        "detected_by_occupation": detected_by_occupation,
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note,
        "last_old_regions": last['old_after_regions'],
        "max_heap_mb": max_heap_mb,
        "region_size_mb": region_size_mb,
        "filtered_events": filtered_events,
        "stable_events": stable_events,
        "oom_filtered": oom_filtered
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


def detect_allocation_pressure(
        filtered_events: List[Dict],
        evac_failure_threshold: int = 5
) -> Dict:
    """
    Détection de l'allocation pressure via Evacuation Failure count.

    Evacuation Failure = le GC n'a pas pu déplacer les objets car pas assez de place.
    C'est le signal le plus direct d'allocation pressure en G1GC.

    Seuil par défaut: > 5 evacuation failures → allocation pressure détectée.
    """
    if not filtered_events:
        return {
            "type": "allocation_pressure",
            "detected": False,
            "confidence": "low",
            "reason": "no events",
            "evac_failure_count": 0,
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Compter les Evacuation Failures
    evac_failures = [e for e in filtered_events if e.get('evacuation_failure', False)]
    evac_failure_count = len(evac_failures)

    # Calcul durée pour contexte
    first = filtered_events[0]
    last = filtered_events[-1]
    duration_min = (last['uptime_sec'] - first['uptime_sec']) / 60

    # Détection
    detected = evac_failure_count > evac_failure_threshold

    # Confidence basée sur le nombre d'échecs
    if detected:
        if evac_failure_count > 50:
            confidence = "high"
        elif evac_failure_count > 20:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "low"

    # Evidence
    evidence = []
    if evac_failure_count > 0:
        evidence.append(f"Evacuation Failures: {evac_failure_count} (threshold: {evac_failure_threshold})")
        evidence.append(f"Analysis window: {duration_min:.1f} min, {len(filtered_events)} GC events")

        # Montrer quelques exemples
        samples = evac_failures[:5]
        for e in samples:
            old = e.get('old_after_regions', '?')
            t = e['uptime_sec'] / 60
            evidence.append(f"  GC({e['gc_number']}) at {t:.1f}min: Old={old} regions")
        if len(evac_failures) > 5:
            evidence.append(f"  ... and {len(evac_failures) - 5} more")
    else:
        evidence.append("No Evacuation Failures detected")

    # Next steps
    next_steps = []
    if detected:
        next_steps = [
            "Increase heap size (-Xmx) if possible",
            "JFR recording to identify allocation hotspots",
            "Review object allocation patterns (large arrays, frequent allocations)",
            "Consider tuning G1 parameters: -XX:G1HeapRegionSize, -XX:G1ReservePercent"
        ]

    # Business note
    if detected:
        if evac_failure_count > 50:
            business_note = (
                "SEVERE ALLOCATION PRESSURE: {} Evacuation Failures detected. "
                "The application is allocating objects faster than G1 can evacuate them. "
                "This causes promotion failures and degrades performance significantly. "
                "Immediate action: increase heap or reduce allocation rate."
            ).format(evac_failure_count)
        else:
            business_note = (
                "ALLOCATION PRESSURE detected: {} Evacuation Failures. "
                "G1 is struggling to keep up with object allocation rate. "
                "This can lead to longer GC pauses and degraded throughput. "
                "Consider increasing heap size or optimizing allocation patterns."
            ).format(evac_failure_count)
    else:
        business_note = ""

    return {
        "type": "allocation_pressure",
        "detected": detected,
        "confidence": confidence,
        "evac_failure_count": evac_failure_count,
        "evac_failure_threshold": evac_failure_threshold,
        "duration_min": round(duration_min, 1),
        "events_count": len(filtered_events),
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
    }


def analyze_events(
        events: List[Dict],
        tail_minutes: Optional[int] = None,
        old_trend_threshold: float = 30.0,
        stw_threshold_ms: int = 1000,
        max_heap_mb: Optional[float] = None,
        region_size_mb: Optional[float] = None
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

    # Liste des fonctions de détection
    detections = [
        detect_retention_growth(filtered_events,
                                old_trend_threshold,
                                max_heap_mb=max_heap_mb,
                                region_size_mb=region_size_mb),
        detect_allocation_pressure(filtered_events),
        detect_long_stw_pauses(filtered_events, stw_threshold_ms),
    ]

    # Filtre seulement les detected/suspected
    suspects = detections  # Tous les suspects analysés (détectés ou non)

    # Enrichissement OOM-related sur le suspect retention (seulement s'il existe et est détecté)
    for suspect in suspects:
        if suspect["type"] == "retention_growth" and suspect["detected"]:
            suspect["max_heap_mb"] = max_heap_mb
            suspect["region_size_mb"] = region_size_mb

    # Summary global
    detected_count = sum(1 for s in suspects if s["detected"])
    summary = f"{detected_count} issues DETECTED" if detected_count > 0 else "NO STRONG SIGNAL"

    return {
        "summary": summary,
        "suspects": suspects,
        "filtered_events": filtered_events,  # TOUJOURS inclus
        "region_size_mb": region_size_mb  # TOUJOURS inclus (ou None)
    }
