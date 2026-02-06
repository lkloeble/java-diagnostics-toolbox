import pytest
from gc_diagnostic.analyzer import filter_by_tail_window
from gc_diagnostic.parser import parse_log
from gc_diagnostic.analyzer import analyze_events
from gc_diagnostic.analyzer import detect_long_stw_pauses

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
    assert len(retention["evidence"]) == 5

    assert "business_note" in retention
    assert "plateau" in retention["business_note"].lower()  # Vérifie que le note mentionne le plateau
    assert "warmup" in retention["business_note"].lower()  # Vérifie le chargement nominal

    assert all("N/A" in ev or "Line" in ev for ev in retention["evidence"])  # Tolérant pour fixtures sans line_num


def test_analyze_events_no_growth_low_threshold(sample_events):
    """Pas de leak si threshold élevé."""
    result = analyze_events(sample_events, tail_minutes=None, old_trend_threshold=100.0)
    # Trouver le suspect retention dans la liste
    retention = next((s for s in result["suspects"] if s["type"] == "retention_growth"), None)
    assert retention is not None
    assert not retention["detected"]


def test_analyze_events_real_fast_log(gc_fast_log_lines):
    """Teste sur le vrai log : doit détecter la croissance rapide."""
    events = parse_log(gc_fast_log_lines)
    result = analyze_events(events, tail_minutes=None, old_trend_threshold=30.0)

    # Trouver le suspect retention dans la liste
    retention = next((s for s in result["suspects"] if s["type"] == "retention_growth"), None)
    assert retention is not None
    assert retention["detected"] is True  # 210 regions / ~4 min ≈ 52 regions/min
    assert retention["trend_regions_per_min"] > 30
    assert len(retention["evidence"]) == 9


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
    assert len(result["suspects"]) == 2, "Doit analyser retention_growth + long_stw_pauses"

    # Vérifie que les deux types sont présents
    types = {s["type"] for s in result["suspects"]}
    assert "retention_growth" in types
    assert "long_stw_pauses" in types

    # Vérifie que retention est détecté, STW non
    retention = next(s for s in result["suspects"] if s["type"] == "retention_growth")
    assert retention["detected"] is True

    stw = next(s for s in result["suspects"] if s["type"] == "long_stw_pauses")
    assert stw["detected"] is False