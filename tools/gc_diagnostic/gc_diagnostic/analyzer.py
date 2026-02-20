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
        threshold_ms: int = 500
) -> Dict:
    """
    Détection des pauses Stop-The-World longues.

    Seuil par défaut: 500ms (déjà problématique pour la plupart des applications).
    """
    # Récupérer les events avec pause_ms
    events_with_pause = [e for e in filtered_events if e.get('pause_ms') is not None]

    if not events_with_pause:
        return {
            "type": "long_stw_pauses",
            "detected": False,
            "confidence": "low",
            "reason": "no pause data found",
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Filtrer les longues pauses
    long_pause_events = [e for e in events_with_pause if e['pause_ms'] >= threshold_ms]
    detected = len(long_pause_events) >= 1

    confidence = (
        "high" if len(long_pause_events) >= 3
        else "medium" if detected
        else "low"
    )

    # Evidence avec cause (gc_type) et durée
    evidence = []
    for e in long_pause_events:
        pause_ms = e['pause_ms']
        gc_type = e.get('gc_type', 'Unknown')
        gc_num = e.get('gc_number', '?')
        time_min = e['uptime_sec'] / 60
        evidence.append(f"GC({gc_num}) at {time_min:.1f}min: {pause_ms:.0f}ms - {gc_type}")

    # Stats summary si plusieurs longues pauses
    if len(long_pause_events) > 1:
        max_pause = max(e['pause_ms'] for e in long_pause_events)
        avg_pause = sum(e['pause_ms'] for e in long_pause_events) / len(long_pause_events)
        evidence.insert(0, f"Found {len(long_pause_events)} pauses >= {threshold_ms}ms (max: {max_pause:.0f}ms, avg: {avg_pause:.0f}ms)")

    next_steps = [
        "JFR recording (GC + safepoint + pause phases)",
        "Increase logging: -Xlog:gc*,safepoint*",
        "Check for Full GC triggers (heap too small, System.gc() calls, metadata pressure)"
    ] if detected else []

    # Business note
    if detected:
        if len(long_pause_events) >= 3:
            business_note = (
                "FREQUENT LONG PAUSES: Multiple STW pauses exceeding {}ms detected. "
                "This severely impacts application responsiveness and throughput. "
                "Investigate GC configuration and heap sizing."
            ).format(threshold_ms)
        else:
            business_note = (
                "LONG STW PAUSE detected (>{}ms). "
                "This can cause application latency spikes and timeouts. "
                "Check if caused by Full GC, heap pressure, or explicit System.gc() calls."
            ).format(threshold_ms)
    else:
        business_note = ""

    return {
        "type": "long_stw_pauses",
        "detected": detected,
        "confidence": confidence,
        "long_pause_count": len(long_pause_events),
        "threshold_ms": threshold_ms,
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
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
            "Check for memory-intensive batch operations or bulk data processing"
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


def detect_humongous_pressure(
        filtered_events: List[Dict],
        frequency_threshold_pct: float = 20.0,
        peak_threshold_regions: int = 30,
        max_heap_regions: Optional[int] = None
) -> Dict:
    """
    Détection de pression humongous (objets > 50% d'une région G1).

    Les humongous objects causent:
    - Fragmentation du heap (ne peuvent pas être déplacés)
    - Concurrent cycles plus fréquents
    - Potentiellement des Full GC

    Signaux:
    1. Fréquence: % de GCs avec humongous > 0 (pression constante)
    2. Peak: Max humongous regions (taille des allocations)
    """
    if not filtered_events:
        return {
            "type": "humongous_pressure",
            "detected": False,
            "confidence": "low",
            "reason": "no events",
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Calcul durée pour contexte
    first = filtered_events[0]
    last = filtered_events[-1]
    duration_min = (last['uptime_sec'] - first['uptime_sec']) / 60

    # Récupérer les events avec humongous_before
    events_with_humongous = [
        e for e in filtered_events
        if e.get('humongous_before') is not None and e['humongous_before'] > 0
    ]

    total_gc_count = len(filtered_events)
    humongous_gc_count = len(events_with_humongous)

    # Fréquence des GCs avec humongous
    frequency_pct = (humongous_gc_count / total_gc_count * 100) if total_gc_count > 0 else 0

    # Peak et average humongous
    if events_with_humongous:
        peak_humongous = max(e['humongous_before'] for e in events_with_humongous)
        avg_humongous = sum(e['humongous_before'] for e in events_with_humongous) / len(events_with_humongous)
    else:
        peak_humongous = 0
        avg_humongous = 0

    # Ratio par rapport au heap total si disponible
    heap_ratio_pct = None
    if max_heap_regions and max_heap_regions > 0 and peak_humongous > 0:
        heap_ratio_pct = (peak_humongous / max_heap_regions) * 100

    # === LOGIQUE DE DÉTECTION ===
    # Signal 1: Fréquence élevée (beaucoup de GCs ont des humongous)
    detected_by_frequency = frequency_pct >= frequency_threshold_pct

    # Signal 2: Peak élevé (grosses allocations humongous)
    detected_by_peak = peak_humongous >= peak_threshold_regions

    # Détection finale
    detected = detected_by_frequency or detected_by_peak

    # === CONFIDENCE ===
    if detected:
        if detected_by_frequency and detected_by_peak and frequency_pct >= 50:
            confidence = "high"
        elif detected_by_frequency and frequency_pct >= 50:
            confidence = "high"
        elif detected_by_frequency and detected_by_peak:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "low"

    # === EVIDENCE ===
    evidence = []
    evidence.append(f"GCs with humongous: {humongous_gc_count}/{total_gc_count} ({frequency_pct:.1f}%)")
    if peak_humongous > 0:
        evidence.append(f"Peak humongous regions: {peak_humongous} (avg: {avg_humongous:.1f})")
    if heap_ratio_pct is not None:
        evidence.append(f"Peak humongous vs heap: {heap_ratio_pct:.1f}%")
    evidence.append(f"Analysis window: {duration_min:.1f} min")

    # Montrer quelques exemples si détecté
    if detected and events_with_humongous:
        # Top 3 par humongous_before
        top_events = sorted(events_with_humongous, key=lambda e: e['humongous_before'], reverse=True)[:3]
        for e in top_events:
            h_before = e['humongous_before']
            h_after = e.get('humongous_after', '?')
            t = e['uptime_sec'] / 60
            evidence.append(f"  GC({e['gc_number']}) at {t:.1f}min: Humongous {h_before}->{h_after}")

    # === NEXT STEPS ===
    next_steps = []
    if detected:
        next_steps = [
            "Identify humongous allocations: -Xlog:gc+humongous=debug",
            "JFR recording to find allocation sites of large objects",
            "Review code for large arrays, collections, or buffers (> region_size/2)",
            "Consider splitting large objects or using off-heap storage (DirectByteBuffer)"
        ]

    # === BUSINESS NOTE ===
    if detected:
        if confidence == "high":
            business_note = (
                "SIGNIFICANT HUMONGOUS PRESSURE: {:.0f}% of GCs involve humongous objects. "
                "These are objects larger than half a G1 region (typically > 512KB). "
                "Humongous objects cause heap fragmentation and cannot be evacuated during young GC. "
                "This leads to more frequent concurrent cycles and potential Full GCs."
            ).format(frequency_pct)
        elif detected_by_peak:
            business_note = (
                "LARGE HUMONGOUS ALLOCATIONS detected (peak: {} regions). "
                "Very large objects are being allocated, consuming significant heap space. "
                "Identify and optimize these allocations to reduce GC pressure."
            ).format(peak_humongous)
        else:
            business_note = (
                "HUMONGOUS ALLOCATIONS detected in {:.0f}% of GCs. "
                "Large objects are being allocated regularly. "
                "Monitor for impact on GC pause times and heap fragmentation."
            ).format(frequency_pct)
    else:
        business_note = ""

    return {
        "type": "humongous_pressure",
        "detected": detected,
        "confidence": confidence,
        "frequency_pct": round(frequency_pct, 1),
        "humongous_gc_count": humongous_gc_count,
        "total_gc_count": total_gc_count,
        "peak_humongous": peak_humongous,
        "avg_humongous": round(avg_humongous, 1),
        "heap_ratio_pct": round(heap_ratio_pct, 1) if heap_ratio_pct else None,
        "detected_by_frequency": detected_by_frequency,
        "detected_by_peak": detected_by_peak,
        "duration_min": round(duration_min, 1),
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
    }


def detect_gc_starvation(
        filtered_events: List[Dict],
        gap_threshold_sec: float = 30.0,
        max_heap_mb: Optional[float] = None,
        region_size_mb: Optional[float] = None
) -> Dict:
    """
    Détection de GC starvation / finalizer backlog.

    Symptôme typique des finalizers bloquants ou code legacy avec finalize() :
    - L'application est bloquée par le Finalizer thread
    - Peu de GCs malgré une heap sous pression
    - Longs gaps entre GCs consécutifs

    Ce pattern est différent d'une app idle : la heap est haute mais les GCs sont rares.

    Signaux:
    1. Long inter-GC gaps (>30s par défaut)
    2. Heap élevée pendant ces gaps
    3. Très peu de GCs par rapport à la durée totale
    """
    if len(filtered_events) < 3:
        return {
            "type": "gc_starvation",
            "detected": False,
            "confidence": "low",
            "reason": f"only {len(filtered_events)} events",
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Calcul durée totale
    first = filtered_events[0]
    last = filtered_events[-1]
    duration_sec = last['uptime_sec'] - first['uptime_sec']
    duration_min = duration_sec / 60

    if duration_min < 1:
        return {
            "type": "gc_starvation",
            "detected": False,
            "confidence": "low",
            "reason": "log duration too short",
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Calculer les gaps entre GCs consécutifs
    gaps = []
    for i in range(1, len(filtered_events)):
        gap_sec = filtered_events[i]['uptime_sec'] - filtered_events[i-1]['uptime_sec']
        prev_heap = filtered_events[i-1].get('old_after_regions', 0)
        gaps.append({
            'gap_sec': gap_sec,
            'from_gc': filtered_events[i-1].get('gc_number', i-1),
            'to_gc': filtered_events[i].get('gc_number', i),
            'heap_before_gap': prev_heap,
            'from_uptime': filtered_events[i-1]['uptime_sec'],
            'to_uptime': filtered_events[i]['uptime_sec']
        })

    # Trouver les longs gaps
    long_gaps = [g for g in gaps if g['gap_sec'] >= gap_threshold_sec]
    max_gap_sec = max(g['gap_sec'] for g in gaps) if gaps else 0

    # Calculer le GC rate (GCs par minute)
    gc_count = len(filtered_events)
    gc_rate_per_min = gc_count / duration_min if duration_min > 0 else 0

    # Calculer l'occupation heap moyenne pendant les longs gaps
    avg_heap_during_gaps = None
    if long_gaps and max_heap_mb and region_size_mb:
        max_heap_regions = max_heap_mb / region_size_mb
        heap_pcts = [(g['heap_before_gap'] / max_heap_regions * 100) for g in long_gaps if max_heap_regions > 0]
        if heap_pcts:
            avg_heap_during_gaps = sum(heap_pcts) / len(heap_pcts)

    # Calculer si la heap croît pendant la fenêtre d'analyse
    # Finalizer starvation = accumulation, Plateau = stable
    heap_growing = False
    heap_growth_rate = 0.0
    if len(filtered_events) >= 3:
        first_heap = filtered_events[0].get('old_after_regions', 0)
        last_heap = filtered_events[-1].get('old_after_regions', 0)
        heap_delta = last_heap - first_heap
        heap_growth_rate = heap_delta / duration_min if duration_min > 0 else 0
        # Considérer comme "croissant" si > 10 regions/min (significatif)
        heap_growing = heap_growth_rate > 10

    # === LOGIQUE DE DÉTECTION ===
    # Signal 1: Au moins un gap très long (>30s par défaut)
    has_long_gaps = len(long_gaps) >= 1

    # Signal 2: Heap élevée pendant les gaps (>50%)
    heap_high_during_gaps = avg_heap_during_gaps is not None and avg_heap_during_gaps > 50

    # Signal 3: Heap en croissance (pas un plateau stable)
    # C'est la différence clé : finalizer = accumulation, idle = stable
    # Un plateau avec gaps longs mais heap stable n'est PAS du starvation

    # Détection: gaps longs + heap haute + (heap croissante OU très haute >75%)
    # Si heap > 75%, même sans croissance c'est critique
    heap_critical = avg_heap_during_gaps is not None and avg_heap_during_gaps > 75
    detected = has_long_gaps and heap_high_during_gaps and (heap_growing or heap_critical)

    # === CONFIDENCE ===
    if detected:
        if len(long_gaps) >= 3 and heap_high_during_gaps:
            confidence = "high"
        elif len(long_gaps) >= 2 or (has_long_gaps and heap_high_during_gaps):
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "low"

    # === EVIDENCE ===
    evidence = []
    evidence.append(f"Max inter-GC gap: {max_gap_sec:.1f}s (threshold: {gap_threshold_sec}s)")
    evidence.append(f"Long gaps (>{gap_threshold_sec}s): {len(long_gaps)}")
    evidence.append(f"GC frequency: {gc_rate_per_min:.1f} GCs/min over {duration_min:.1f} min")
    if avg_heap_during_gaps is not None:
        evidence.append(f"Avg heap during long gaps: {avg_heap_during_gaps:.0f}%")
    evidence.append(f"Heap growth rate: {heap_growth_rate:.1f} regions/min ({'growing' if heap_growing else 'stable'})")

    # Montrer les top 3 plus longs gaps
    if long_gaps:
        sorted_gaps = sorted(long_gaps, key=lambda g: g['gap_sec'], reverse=True)[:3]
        for g in sorted_gaps:
            evidence.append(f"  GC({g['from_gc']}) → GC({g['to_gc']}): {g['gap_sec']:.0f}s gap")

    # === NEXT STEPS ===
    next_steps = []
    if detected:
        next_steps = [
            "Check for finalize() methods: grep -r 'void finalize' src/",
            "Enable finalizer logging: -Xlog:gc+ref=debug",
            "JFR recording focusing on 'Java Blocking' events",
            "Review legacy code for finalize() → refactor to try-with-resources or Cleaner API",
            "Monitor Finalizer thread CPU usage"
        ]

    # === BUSINESS NOTE ===
    if detected:
        if confidence == "high":
            business_note = (
                "SEVERE GC STARVATION: Very long gaps ({:.0f}s max) between GCs despite high heap usage. "
                "This is a classic symptom of FINALIZER BACKLOG - the Finalizer thread is blocking "
                "the application. finalize() methods with I/O or slow operations create queues that "
                "prevent objects from being collected. Immediate code review required."
            ).format(max_gap_sec)
        else:
            business_note = (
                "GC STARVATION detected: Long gaps ({:.0f}s) between GCs suggest the application "
                "may be blocked by finalizers or other reference processing. Check for finalize() "
                "methods in legacy code. This can cause indirect OOM and severe performance degradation."
            ).format(max_gap_sec)
    else:
        business_note = ""

    return {
        "type": "gc_starvation",
        "detected": detected,
        "confidence": confidence,
        "max_gap_sec": round(max_gap_sec, 1),
        "long_gap_count": len(long_gaps),
        "gc_rate_per_min": round(gc_rate_per_min, 1),
        "gc_count": gc_count,
        "duration_min": round(duration_min, 1),
        "avg_heap_during_gaps_pct": round(avg_heap_during_gaps, 1) if avg_heap_during_gaps else None,
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
    }


def detect_metaspace_leak(
        filtered_events: List[Dict],
        growth_threshold_kb_per_min: float = 500.0,
        metadata_gc_threshold_pct: float = 30.0
) -> Dict:
    """
    Détection de leak Metaspace (classloading dynamique, JSP, plugins).

    Le Metaspace contient les métadonnées des classes chargées.
    Un leak se produit quand des classes sont chargées mais jamais déchargées
    (ex: hot deploy, frameworks anciens, JSP compilées).

    Signaux:
    1. Croissance du Metaspace (metaspace_used_kb augmente)
    2. GCs déclenchés par "Metadata GC Threshold" (pression Metaspace)
    """
    # Filter events with metaspace data
    events_with_metaspace = [
        e for e in filtered_events
        if e.get('metaspace_used_kb') is not None
    ]

    if len(events_with_metaspace) < 2:
        return {
            "type": "metaspace_leak",
            "detected": False,
            "confidence": "low",
            "reason": f"only {len(events_with_metaspace)} events with metaspace data",
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Calcul durée
    first = events_with_metaspace[0]
    last = events_with_metaspace[-1]
    duration_sec = last['uptime_sec'] - first['uptime_sec']
    duration_min = duration_sec / 60

    if duration_min < 0.1:  # Minimum 6 seconds
        return {
            "type": "metaspace_leak",
            "detected": False,
            "confidence": "low",
            "reason": "log duration too short",
            "evidence": [],
            "next_steps": [],
            "business_note": ""
        }

    # Calcul croissance Metaspace
    first_metaspace_kb = first['metaspace_used_kb']
    last_metaspace_kb = last['metaspace_used_kb']
    delta_kb = last_metaspace_kb - first_metaspace_kb
    growth_kb_per_min = delta_kb / duration_min if duration_min > 0 else 0

    # Convertir en MB pour affichage
    first_metaspace_mb = first_metaspace_kb / 1024
    last_metaspace_mb = last_metaspace_kb / 1024
    delta_mb = delta_kb / 1024
    growth_mb_per_min = growth_kb_per_min / 1024

    # Compter les GCs déclenchés par Metadata GC Threshold
    metadata_gc_count = sum(1 for e in filtered_events if e.get('metadata_gc_threshold', False))
    total_gc_count = len(filtered_events)
    metadata_gc_pct = (metadata_gc_count / total_gc_count * 100) if total_gc_count > 0 else 0

    # === LOGIQUE DE DÉTECTION ===
    # Signal 1: Croissance significative du Metaspace
    detected_by_growth = growth_kb_per_min > growth_threshold_kb_per_min and delta_kb > 0

    # Signal 2: Beaucoup de GCs déclenchés par Metaspace pressure
    detected_by_metadata_gc = metadata_gc_pct >= metadata_gc_threshold_pct

    # Détection: croissance OU beaucoup de metadata GCs
    detected = detected_by_growth or detected_by_metadata_gc

    # === CONFIDENCE ===
    if detected:
        if detected_by_growth and detected_by_metadata_gc:
            confidence = "high"
        elif detected_by_growth and growth_kb_per_min > growth_threshold_kb_per_min * 3:
            confidence = "high"
        elif detected_by_growth:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "low"

    # === EVIDENCE ===
    evidence = []
    evidence.append(f"Metaspace: {first_metaspace_mb:.1f} MB → {last_metaspace_mb:.1f} MB (+{delta_mb:.1f} MB)")
    evidence.append(f"Growth rate: {growth_mb_per_min:.2f} MB/min over {duration_min:.1f} min")
    evidence.append(f"GCs triggered by Metaspace: {metadata_gc_count}/{total_gc_count} ({metadata_gc_pct:.0f}%)")

    # Montrer la progression
    if len(events_with_metaspace) >= 3:
        mid_idx = len(events_with_metaspace) // 2
        mid = events_with_metaspace[mid_idx]
        mid_mb = mid['metaspace_used_kb'] / 1024
        mid_time = mid['uptime_sec'] / 60
        evidence.append(f"Progression: {first_metaspace_mb:.0f}MB → {mid_mb:.0f}MB → {last_metaspace_mb:.0f}MB")

    # === NEXT STEPS ===
    next_steps = []
    if detected:
        next_steps = [
            "jcmd <pid> VM.classloader_stats (check classloader hierarchy)",
            "jcmd <pid> GC.class_stats (identify classes consuming metaspace)",
            "Check for: hot deploys, JSP compilation, dynamic proxies, reflection-heavy frameworks",
            "Review application restart strategy (rolling restarts if leak is slow)"
        ]

    # === BUSINESS NOTE ===
    if detected:
        if confidence == "high":
            business_note = (
                "METASPACE LEAK: Classes are being loaded but not unloaded. "
                "Metaspace grew by {:.1f} MB in {:.1f} minutes ({:.2f} MB/min). "
                "This is classic classloader leak behavior - common in applications with "
                "hot deploy, JSP compilation, or dynamic class generation. "
                "Left unchecked, this leads to OutOfMemoryError: Metaspace."
            ).format(delta_mb, duration_min, growth_mb_per_min)
        else:
            business_note = (
                "METASPACE PRESSURE detected: Metaspace is growing ({:.2f} MB/min). "
                "This may indicate classloader leak or heavy dynamic class loading. "
                "Monitor for continued growth after application warmup."
            ).format(growth_mb_per_min)
    else:
        business_note = ""

    return {
        "type": "metaspace_leak",
        "detected": detected,
        "confidence": confidence,
        "first_metaspace_mb": round(first_metaspace_mb, 1),
        "last_metaspace_mb": round(last_metaspace_mb, 1),
        "delta_mb": round(delta_mb, 1),
        "growth_mb_per_min": round(growth_mb_per_min, 2),
        "duration_min": round(duration_min, 1),
        "metadata_gc_count": metadata_gc_count,
        "metadata_gc_pct": round(metadata_gc_pct, 1),
        "detected_by_growth": detected_by_growth,
        "detected_by_metadata_gc": detected_by_metadata_gc,
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
    }


def detect_tlab_exhaustion(
        filtered_events: List[Dict],
        slow_alloc_ratio_threshold: float = 30.0,
        high_waste_threshold: float = 5.0
) -> Dict:
    """
    Détection d'exhaustion TLAB (Thread Local Allocation Buffer).

    Nécessite un logging spécial: -Xlog:gc+tlab=debug

    TLAB exhaustion se produit quand les threads épuisent leur TLAB
    et doivent faire des allocations "slow path" synchronisées.
    Cela dégrade les performances en multi-threaded.

    Signaux:
    1. Ratio élevé slow_allocs / refills (beaucoup d'allocations hors TLAB)
    2. Waste élevé (TLAB mal dimensionnés)

    Fix: Tuner -XX:TLABSize, -XX:MinTLABSize, ou padding fields (@Contended)
    """
    # Filter events with TLAB data
    events_with_tlab = [
        e for e in filtered_events
        if e.get('tlab_slow_allocs') is not None
    ]

    if len(events_with_tlab) < 2:
        return {
            "type": "tlab_exhaustion",
            "detected": False,
            "confidence": "low",
            "reason": "no TLAB data (requires -Xlog:gc+tlab=debug)",
            "evidence": ["TLAB stats not found in log - special logging required"],
            "next_steps": ["Enable TLAB logging: -Xlog:gc+tlab=debug:file=gc.log:time,uptime,level,tags"],
            "business_note": ""
        }

    # Calcul durée
    first = events_with_tlab[0]
    last = events_with_tlab[-1]
    duration_sec = last['uptime_sec'] - first['uptime_sec']
    duration_min = duration_sec / 60

    # Agrégation des métriques TLAB
    total_slow_allocs = sum(e['tlab_slow_allocs'] for e in events_with_tlab)
    total_refills = sum(e['tlab_refills'] for e in events_with_tlab)
    avg_waste_pct = sum(e['tlab_waste_pct'] for e in events_with_tlab) / len(events_with_tlab)
    max_waste_pct = max(e['tlab_waste_pct'] for e in events_with_tlab)
    avg_thrds = sum(e['tlab_thrds'] for e in events_with_tlab) / len(events_with_tlab)

    # Calculer le ratio slow_allocs / refills
    # Un ratio élevé signifie beaucoup d'allocations ne passent pas par TLAB
    slow_alloc_ratio = (total_slow_allocs / total_refills * 100) if total_refills > 0 else 0

    # Calculer slow allocs par seconde (indicateur de pression)
    slow_allocs_per_sec = total_slow_allocs / duration_sec if duration_sec > 0 else 0

    # === LOGIQUE DE DÉTECTION ===
    # Signal 1: Ratio élevé slow_allocs / refills
    detected_by_ratio = slow_alloc_ratio >= slow_alloc_ratio_threshold

    # Signal 2: Waste élevé (TLABs mal dimensionnés)
    detected_by_waste = avg_waste_pct >= high_waste_threshold

    # Détection: ratio OU waste élevé
    detected = detected_by_ratio or detected_by_waste

    # === CONFIDENCE ===
    if detected:
        if detected_by_ratio and detected_by_waste:
            confidence = "high"
        elif slow_alloc_ratio >= slow_alloc_ratio_threshold * 1.5:
            confidence = "high"
        elif detected_by_ratio:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = "low"

    # === EVIDENCE ===
    evidence = []
    evidence.append(f"TLAB slow allocs: {total_slow_allocs:,} ({slow_alloc_ratio:.1f}% of refills)")
    evidence.append(f"TLAB refills: {total_refills:,}")
    evidence.append(f"Avg TLAB waste: {avg_waste_pct:.1f}% (max: {max_waste_pct:.1f}%)")
    evidence.append(f"Slow allocs/sec: {slow_allocs_per_sec:.0f}")
    evidence.append(f"Avg threads: {avg_thrds:.0f} over {len(events_with_tlab)} GCs")

    # Top 3 worst GCs
    sorted_by_slow = sorted(events_with_tlab, key=lambda e: e['tlab_slow_allocs'], reverse=True)[:3]
    for e in sorted_by_slow:
        gc_num = e.get('gc_number', '?')
        slow = e['tlab_slow_allocs']
        waste = e['tlab_waste_pct']
        evidence.append(f"  GC({gc_num}): {slow} slow allocs, {waste:.1f}% waste")

    # === NEXT STEPS ===
    next_steps = []
    if detected:
        next_steps = [
            "Profile allocation hotspots with JFR (focus on TLAB events)",
            "Review large array allocations in multi-threaded code",
            "Check for allocation bursts in parallel stream operations",
            "Consider reducing allocation rate in hot paths"
        ]

    # === BUSINESS NOTE ===
    if detected:
        if confidence == "high":
            business_note = (
                "TLAB EXHAUSTION: {:.0f}% of allocations are slow path (synchronized). "
                "Threads are competing for heap allocation instead of using their local buffers. "
                "This severely impacts multi-threaded performance and scalability. "
                "Tune TLAB size or investigate allocation patterns."
            ).format(slow_alloc_ratio)
        else:
            business_note = (
                "TLAB PRESSURE detected: Elevated slow path allocations ({:.0f}%). "
                "This indicates suboptimal TLAB sizing for the workload. "
                "May cause latency spikes under high thread contention."
            ).format(slow_alloc_ratio)
    else:
        business_note = ""

    return {
        "type": "tlab_exhaustion",
        "detected": detected,
        "confidence": confidence,
        "total_slow_allocs": total_slow_allocs,
        "total_refills": total_refills,
        "slow_alloc_ratio": round(slow_alloc_ratio, 1),
        "avg_waste_pct": round(avg_waste_pct, 1),
        "max_waste_pct": round(max_waste_pct, 1),
        "slow_allocs_per_sec": round(slow_allocs_per_sec, 0),
        "avg_thrds": round(avg_thrds, 0),
        "gc_count_with_tlab": len(events_with_tlab),
        "duration_min": round(duration_min, 1),
        "detected_by_ratio": detected_by_ratio,
        "detected_by_waste": detected_by_waste,
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
    }


def detect_collector_choice(
        collector_type: Optional[str],
        max_heap_mb: Optional[float] = None
) -> Dict:
    """
    Détection de mauvais choix de collector GC.

    Les applications legacy sont souvent bloquées sur Serial/Parallel/CMS
    alors que G1 est le défaut depuis Java 9 et que ZGC/Shenandoah
    sont meilleurs pour les grosses heaps et la latence.

    Règles:
    - Serial/Parallel → suggérer G1 (ou ZGC si heap > 8GB)
    - G1 → OK (pas de détection)
    - ZGC/Shenandoah → OK (modern collectors)
    - Unknown → mentionner le risque
    """
    if collector_type is None:
        return {
            "type": "collector_choice",
            "detected": False,
            "confidence": "low",
            "reason": "collector type not found in log",
            "collector": None,
            "evidence": ["Could not determine GC collector from log"],
            "next_steps": [],
            "business_note": ""
        }

    collector_upper = collector_type.upper()

    # Modern collectors - OK
    if collector_upper in ('G1', 'ZGC', 'SHENANDOAH'):
        return {
            "type": "collector_choice",
            "detected": False,
            "confidence": "low",
            "collector": collector_type,
            "evidence": [f"Using {collector_type} collector (modern, recommended)"],
            "next_steps": [],
            "business_note": ""
        }

    # Legacy collectors - suggest upgrade
    detected = True
    confidence = "high" if collector_upper in ('SERIAL', 'PARALLEL') else "medium"

    evidence = [f"Using {collector_type} collector (legacy)"]

    # Build recommendations based on heap size
    next_steps = []
    if collector_upper == 'SERIAL':
        evidence.append("Serial collector is single-threaded - very slow for production workloads")
        next_steps.append("Switch to G1: -XX:+UseG1GC (default since Java 9)")
    elif collector_upper == 'PARALLEL':
        evidence.append("Parallel collector optimizes throughput but has long STW pauses")
        next_steps.append("Switch to G1: -XX:+UseG1GC (better pause times)")

    # For large heaps, suggest ZGC
    if max_heap_mb and max_heap_mb >= 8192:  # >= 8GB
        evidence.append(f"Heap is {max_heap_mb/1024:.0f}GB - consider low-latency collectors")
        next_steps.append("For large heaps (>8GB), consider ZGC: -XX:+UseZGC")
        next_steps.append("Or Shenandoah: -XX:+UseShenandoahGC")
    else:
        next_steps.append("For low-latency needs: ZGC (-XX:+UseZGC) or Shenandoah")

    next_steps.append("Benchmark before switching in production")

    # Business note
    if collector_upper == 'SERIAL':
        business_note = (
            "LEGACY COLLECTOR: Serial GC is designed for single-threaded apps and small heaps. "
            "It will cause severe pause times in any modern application. "
            "Switching to G1 is almost always beneficial."
        )
    elif collector_upper == 'PARALLEL':
        business_note = (
            "LEGACY COLLECTOR: Parallel GC prioritizes throughput over latency. "
            "This can cause unpredictable long STW pauses (seconds). "
            "G1 provides better pause time control with minimal throughput impact. "
            "For heaps >8GB with latency requirements, consider ZGC or Shenandoah."
        )
    else:
        business_note = (
            f"UNKNOWN COLLECTOR: {collector_type}. "
            "Consider using G1 (default since Java 9) or modern collectors (ZGC, Shenandoah)."
        )

    return {
        "type": "collector_choice",
        "detected": detected,
        "confidence": confidence,
        "collector": collector_type,
        "max_heap_mb": max_heap_mb,
        "evidence": evidence,
        "next_steps": next_steps,
        "business_note": business_note
    }


def analyze_events(
        events: List[Dict],
        tail_minutes: Optional[int] = None,
        old_trend_threshold: float = 30.0,
        stw_threshold_ms: int = 500,
        max_heap_mb: Optional[float] = None,
        region_size_mb: Optional[float] = None,
        collector_type: Optional[str] = None
) -> Dict:
    """
    Chef d'orchestre : applique filtre + appelle chaque détection de suspect + construit summary global.
    Scalable pour 8 suspects.
    """
    filtered_events = filter_by_tail_window(events, tail_minutes)

    if not filtered_events:
        return {
            "summary": "NO STRONG SIGNAL (empty after filtering)",
            "suspects": []
        }

    # Calcul max_heap_regions pour humongous detection
    max_heap_regions = None
    if max_heap_mb and region_size_mb and region_size_mb > 0:
        max_heap_regions = int(max_heap_mb / region_size_mb)

    # Liste des fonctions de détection
    detections = [
        detect_retention_growth(filtered_events,
                                old_trend_threshold,
                                max_heap_mb=max_heap_mb,
                                region_size_mb=region_size_mb),
        detect_allocation_pressure(filtered_events),
        detect_long_stw_pauses(filtered_events, stw_threshold_ms),
        detect_humongous_pressure(filtered_events, max_heap_regions=max_heap_regions),
        detect_gc_starvation(filtered_events, max_heap_mb=max_heap_mb, region_size_mb=region_size_mb),
        detect_metaspace_leak(filtered_events),
        detect_tlab_exhaustion(filtered_events),
        detect_collector_choice(collector_type, max_heap_mb=max_heap_mb),
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
