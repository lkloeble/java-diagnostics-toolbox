import pytest
from gc_diagnostic.analyzer import filter_by_tail_window
from gc_diagnostic.parser import parse_log
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.analyzer import detect_long_stw_pauses
from gc_diagnostic.analyzer import detect_retention_growth
from gc_diagnostic.analyzer import detect_allocation_pressure
from gc_diagnostic.analyzer import detect_humongous_pressure

@pytest.fixture
def sample_events():
    return [
        {'uptime_sec': 60.0, 'old_after_regions': 100},
        {'uptime_sec': 120.0, 'old_after_regions': 150},
        {'uptime_sec': 180.0, 'old_after_regions': 220},
        {'uptime_sec': 240.0, 'old_after_regions': 280},
        {'uptime_sec': 300.0, 'old_after_regions': 350},
    ]

def test_filter_by_tail_window_none_returns_all(sample_events):
    filtered = filter_by_tail_window(sample_events, tail_minutes=None)
    assert len(filtered) == 5
    assert filtered == sample_events  # référence égale ou deep equal

def test_filter_by_tail_window_larger_than_log_returns_all(sample_events):
    filtered = filter_by_tail_window(sample_events, tail_minutes=10)  # > 5 min
    assert len(filtered) == 5


def test_filter_by_tail_window_keeps_only_recent(sample_events):
    # Log de 5 min (300 s), on veut les 2 dernières minutes
    filtered = filter_by_tail_window(sample_events, tail_minutes=2)

    assert len(filtered) == 3, "Devrait garder les 3 derniers (180, 240, 300 s)"
    assert filtered[0]['uptime_sec'] == 180.0
    assert filtered[1]['uptime_sec'] == 240.0
    assert filtered[2]['uptime_sec'] == 300.0
    assert all(e['uptime_sec'] >= 180.0 for e in filtered)

def test_filter_by_tail_window_empty_list():
    assert filter_by_tail_window([], tail_minutes=5) == []

def test_filter_by_tail_window_zero_or_negative():
    events = [{'uptime_sec': 100.0, 'old_after_regions': 50}]
    with pytest.raises(ValueError, match="tail_minutes must be positive"):
        filter_by_tail_window(events, tail_minutes=0)
    with pytest.raises(ValueError, match="tail_minutes must be positive"):
        filter_by_tail_window(events, tail_minutes=-1)


def test_analyze_events_detects_growth_on_sample(sample_events):
    """Teste la détection de croissance sur la fixture (simule leak)."""
    result = analyze_events(sample_events, tail_minutes=None, old_trend_threshold=40.0)

    retention = next((s for s in result["suspects"] if s["type"] == "retention_growth"), None)
    assert retention is not None
    assert retention["detected"] is True
    assert retention["trend_regions_per_min"] > 40  # 250 delta / 4 min ≈ 62
    assert retention["confidence"] in ("high", "medium")
    assert len(retention["evidence"]) >= 3  # At least: signal + start + end

    assert "business_note" in retention
    assert len(retention["business_note"]) > 0  # Has some business note

    # Evidence contains key data points
    evidence_text = " ".join(retention["evidence"])
    assert "Start:" in evidence_text
    assert "End:" in evidence_text


def test_analyze_events_no_growth_stable():
    """No leak detected on stable memory (small delta, low trend)."""
    stable_events = [
        {'uptime_sec': 60.0, 'old_after_regions': 100},
        {'uptime_sec': 120.0, 'old_after_regions': 102},
        {'uptime_sec': 180.0, 'old_after_regions': 101},
        {'uptime_sec': 240.0, 'old_after_regions': 103},
        {'uptime_sec': 300.0, 'old_after_regions': 100},
    ]
    result = analyze_events(stable_events, tail_minutes=None, old_trend_threshold=5.0)
    retention = next((s for s in result["suspects"] if s["type"] == "retention_growth"), None)
    assert retention is not None
    assert not retention["detected"], "Stable memory should not trigger detection"
    assert retention["delta_regions"] <= 10  # Minimal change


def test_analyze_events_real_fast_log(gc_fast_log_lines):
    """Teste sur le vrai log : doit détecter la croissance rapide."""
    events = parse_log(gc_fast_log_lines)
    result = analyze_events(events, tail_minutes=None, old_trend_threshold=30.0)

    # Trouver le suspect retention dans la liste
    retention = next((s for s in result["suspects"] if s["type"] == "retention_growth"), None)
    assert retention is not None
    assert retention["detected"] is True  # 210 regions / ~4 min ≈ 52 regions/min
    assert retention["trend_regions_per_min"] > 30
    assert retention["detected_by_trend"] is True
    assert len(retention["evidence"]) >= 3  # At least: signal + start + end


def test_analyze_events_tail_window_real_log(gc_fast_log_lines):
    """Vérifie que tail-window réduit la fenêtre ET détecte toujours (ou pas)."""
    events = parse_log(gc_fast_log_lines)

    # Full log → détecté
    full_result = analyze_events(events, tail_minutes=None, old_trend_threshold=30.0)
    # Trouver le suspect retention dans la liste
    retention = next((s for s in full_result["suspects"] if s["type"] == "retention_growth"), None)
    assert retention is not None
    assert retention["detected"]

    # Seulement 1 min → filtre réduit le nombre d'événements
    short_result = analyze_events(events, tail_minutes=1, old_trend_threshold=30.0)
    # Trouver le suspect retention dans la liste
    retention = next((s for s in short_result["suspects"] if s["type"] == "retention_growth"), None)
    assert retention is not None

    # Assertions réalistes
    assert retention["confidence"] in ("low", "medium")  # Pas "high" avec peu de points
    assert "evidence" in retention






# Ajoute ça à la fin de test_analyzer.py

def test_detect_long_stw_pauses_no_pauses(sample_events):
    result = detect_long_stw_pauses(sample_events, threshold_ms=1000)
    assert not result["detected"]
    assert result["confidence"] == "low"

def test_detect_long_stw_pauses_with_long_pause():
    events_with_pauses = [
        {'uptime_sec': 60.0, 'pause_ms': 250},
        {'uptime_sec': 120.0, 'pause_ms': 1800},
        {'uptime_sec': 180.0, 'pause_ms': 400},
    ]
    result = detect_long_stw_pauses(events_with_pauses, threshold_ms=1000)
    assert result["detected"]
    assert result["confidence"] == "medium"
    assert len(result["evidence"]) == 1


def test_analyze_events_orchestrates_multiple_suspects(sample_events):
    result = analyze_events(sample_events, tail_minutes=None, old_trend_threshold=40.0)
    assert "suspects" in result
    assert len(result["suspects"]) == 4, "Doit analyser retention_growth + allocation_pressure + long_stw_pauses + humongous_pressure"

    # Vérifie que les quatre types sont présents
    types = {s["type"] for s in result["suspects"]}
    assert "retention_growth" in types
    assert "allocation_pressure" in types
    assert "long_stw_pauses" in types
    assert "humongous_pressure" in types

    # Vérifie que retention est détecté, les autres non
    retention = next(s for s in result["suspects"] if s["type"] == "retention_growth")
    assert retention["detected"] is True

    alloc = next(s for s in result["suspects"] if s["type"] == "allocation_pressure")
    assert alloc["detected"] is False  # sample_events n'a pas d'evacuation_failure

    stw = next(s for s in result["suspects"] if s["type"] == "long_stw_pauses")
    assert stw["detected"] is False

    humongous = next(s for s in result["suspects"] if s["type"] == "humongous_pressure")
    assert humongous["detected"] is False  # sample_events n'a pas d'humongous


def test_detect_retention_growth_ignores_last_oom_crash():
    """
    Vérifie que la fonction ignore le dernier événement si chute > 90%
    (cas typique OOM/crash/restart), et utilise l'avant-dernier comme état stable.
    """
    # Fixture : 5 événements avec chute finale massive (>90%)
    events = [
        {'uptime_sec': 60.0,  'old_after_regions': 100},
        {'uptime_sec': 120.0, 'old_after_regions': 200},
        {'uptime_sec': 180.0, 'old_after_regions': 400},
        {'uptime_sec': 240.0, 'old_after_regions': 800},
        {'uptime_sec': 300.0, 'old_after_regions': 10},   # ← chute brutale 800 → 10 (~99%)
    ]

    result = detect_retention_growth(
        events,
        old_trend_threshold=50.0,  # threshold for trend
        delta_regions_threshold=200,  # threshold for delta
        max_heap_mb=1024,
        region_size_mb=1
    )

    # Assertions clés
    assert result["detected"] is True, "Devrait détecter malgré la chute finale"
    assert result["oom_filtered"] is True, "Devrait avoir filtré le dernier event"
    assert result["trend_regions_per_min"] > 0, "Trend doit être positif sur les événements stables"

    # Vérifie que last_old_regions = 800 (avant-dernier, pas 10)
    assert result["last_old_regions"] == 800, "Doit ignorer la chute finale"

    # Vérifie que la durée et delta sont calculés sans le dernier
    assert result["duration_min"] == pytest.approx(3.0, abs=0.1)  # 240 - 60 = 180 s = 3 min
    assert result["delta_regions"] == 800 - 100, "Delta sur events stables"
    assert result["events_count"] == 5, "events_count reste le total filtré"


# === Tests for allocation pressure ===

def test_detect_allocation_pressure_no_failures():
    """No allocation pressure when no evacuation failures."""
    events = [
        {'uptime_sec': 60.0, 'old_after_regions': 100, 'evacuation_failure': False},
        {'uptime_sec': 120.0, 'old_after_regions': 150, 'evacuation_failure': False},
        {'uptime_sec': 180.0, 'old_after_regions': 200, 'evacuation_failure': False},
    ]
    result = detect_allocation_pressure(events, evac_failure_threshold=5)
    assert result["detected"] is False
    assert result["evac_failure_count"] == 0
    assert result["confidence"] == "low"


def test_detect_allocation_pressure_with_failures():
    """Allocation pressure detected with multiple evacuation failures."""
    events = [
        {'uptime_sec': 60.0, 'old_after_regions': 100, 'evacuation_failure': False, 'gc_number': 1},
        {'uptime_sec': 120.0, 'old_after_regions': 500, 'evacuation_failure': True, 'gc_number': 2},
        {'uptime_sec': 180.0, 'old_after_regions': 600, 'evacuation_failure': True, 'gc_number': 3},
        {'uptime_sec': 240.0, 'old_after_regions': 700, 'evacuation_failure': True, 'gc_number': 4},
        {'uptime_sec': 300.0, 'old_after_regions': 800, 'evacuation_failure': True, 'gc_number': 5},
        {'uptime_sec': 360.0, 'old_after_regions': 850, 'evacuation_failure': True, 'gc_number': 6},
        {'uptime_sec': 420.0, 'old_after_regions': 900, 'evacuation_failure': True, 'gc_number': 7},
    ]
    result = detect_allocation_pressure(events, evac_failure_threshold=5)
    assert result["detected"] is True
    assert result["evac_failure_count"] == 6
    assert result["confidence"] == "low"  # 6 failures, threshold for medium is 20
    assert len(result["evidence"]) > 0
    assert len(result["next_steps"]) > 0


def test_detect_allocation_pressure_high_confidence():
    """High confidence with many evacuation failures."""
    # 60 evacuation failures
    events = [
        {'uptime_sec': i * 10.0, 'old_after_regions': 900, 'evacuation_failure': True, 'gc_number': i}
        for i in range(60)
    ]
    result = detect_allocation_pressure(events, evac_failure_threshold=5)
    assert result["detected"] is True
    assert result["evac_failure_count"] == 60
    assert result["confidence"] == "high"
    assert "SEVERE" in result["business_note"]


# === Tests for humongous pressure ===

def test_detect_humongous_pressure_no_humongous():
    """No humongous pressure when no humongous regions."""
    events = [
        {'uptime_sec': 60.0, 'old_after_regions': 100, 'humongous_before': 0, 'humongous_after': 0, 'gc_number': 0},
        {'uptime_sec': 120.0, 'old_after_regions': 150, 'humongous_before': 0, 'humongous_after': 0, 'gc_number': 1},
        {'uptime_sec': 180.0, 'old_after_regions': 200, 'humongous_before': 0, 'humongous_after': 0, 'gc_number': 2},
    ]
    result = detect_humongous_pressure(events)
    assert result["detected"] is False
    assert result["frequency_pct"] == 0.0
    assert result["peak_humongous"] == 0
    assert result["confidence"] == "low"


def test_detect_humongous_pressure_low_frequency():
    """No detection when humongous frequency is below threshold."""
    # Only 1 out of 10 GCs has humongous = 10% (below 20% threshold)
    events = [
        {'uptime_sec': i * 60.0, 'old_after_regions': 100, 'humongous_before': 0, 'humongous_after': 0, 'gc_number': i}
        for i in range(10)
    ]
    events[5]['humongous_before'] = 15  # Only one with humongous
    events[5]['humongous_after'] = 0

    result = detect_humongous_pressure(events, frequency_threshold_pct=20.0, peak_threshold_regions=30)
    assert result["detected"] is False
    assert result["frequency_pct"] == 10.0
    assert result["peak_humongous"] == 15


def test_detect_humongous_pressure_high_frequency():
    """Detect humongous pressure with high frequency."""
    # 6 out of 10 GCs have humongous = 60%
    events = [
        {'uptime_sec': i * 60.0, 'old_after_regions': 100, 'humongous_before': 35 if i >= 4 else 0, 'humongous_after': 0, 'gc_number': i}
        for i in range(10)
    ]

    result = detect_humongous_pressure(events, frequency_threshold_pct=20.0, peak_threshold_regions=30)
    assert result["detected"] is True
    assert result["frequency_pct"] == 60.0
    assert result["detected_by_frequency"] is True
    assert result["confidence"] == "high"  # >50% frequency
    assert "SIGNIFICANT HUMONGOUS PRESSURE" in result["business_note"]


def test_detect_humongous_pressure_high_peak():
    """Detect humongous pressure with high peak (large allocations)."""
    # Low frequency but high peak
    events = [
        {'uptime_sec': i * 60.0, 'old_after_regions': 100, 'humongous_before': 0, 'humongous_after': 0, 'gc_number': i}
        for i in range(10)
    ]
    events[5]['humongous_before'] = 50  # One large humongous allocation
    events[5]['humongous_after'] = 0

    result = detect_humongous_pressure(events, frequency_threshold_pct=20.0, peak_threshold_regions=30)
    assert result["detected"] is True
    assert result["peak_humongous"] == 50
    assert result["detected_by_peak"] is True
    assert result["detected_by_frequency"] is False
    assert result["confidence"] == "low"  # Only peak, not frequency