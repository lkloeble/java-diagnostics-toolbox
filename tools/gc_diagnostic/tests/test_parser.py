from pathlib import Path
import pytest
from gc_diagnostic.parser import parse_log, validate_log_format, OLD_REGIONS_PATTERN

def test_parses_real_fast_leak_log(gc_fast_log_lines):
    events = parse_log(gc_fast_log_lines)
    assert len(events) >= 5, f"Seulement {len(events)} events GC old regions détectés"
    old_afters = [e['old_after_regions'] for e in events]
    assert max(old_afters) > min(old_afters), "Pas de variation d'old regions"
    # Ajoute plus tard : assert croissance globale


def test_theregexp():
    test_line1 = "[2026-02-05T05:47:54.265+0200][264.303s][info][gc,heap     ] GC(10) Old regions: 214->227"
    match1 = OLD_REGIONS_PATTERN.search(test_line1)

    test_line2 = "[2026-02-05T05:47:40.131+0200][250.169s][info][gc,heap     ] GC(8) Old regions: 192->214"
    match2 = OLD_REGIONS_PATTERN.search(test_line2)

    test_line3 = "[2026-02-05T05:43:52.074+0200][22.113s][info][gc,heap     ] GC(0) Eden regions: 23->0(14)"
    match3 = OLD_REGIONS_PATTERN.search(test_line3)

    # Affichage pour debug
    if match1:
        print("MATCH line1 ! Groups:", match1.groups())
    else:
        print("NO MATCH line1 - line was:", repr(test_line1))

    if match2:
        print("MATCH line2 ! Groups:", match2.groups())
    else:
        print("NO MATCH line2 - line was:", repr(test_line2))

    if match3:
        print("MATCH line3 ! Groups:", match3.groups())
    else:
        print("NO MATCH line3 - line was:", repr(test_line3))


    # Assertions claires et idiomatiques
    assert match1 is not None, "Regex ne matche pas la ligne 1"
    assert match2 is not None, "Regex ne matche pas la ligne 2"
    assert match3 is None, "Regex ne matche pas la ligne 3"

    # Vérifie les groupes extraits (optionnel mais utile)
    assert match1.group(3) == '214'
    assert match1.group(4) == '227'
    assert match2.group(3) == '192'
    assert match2.group(4) == '214'


def test_parses_real_fast_leak_log(gc_fast_log_lines):
    events = parse_log(gc_fast_log_lines)
    print(f"Nombre d'événements old regions parsés : {len(events)}")

    if events:
        print("Premier event:", events[0])
        print("Dernier event:", events[-1])
        old_afters = [e['old_after_regions'] for e in events]
        print("Old after regions:", old_afters)
        print("Croissance totale:", max(old_afters) - min(old_afters))

    assert len(events) >= 5, f"Seulement {len(events)} events GC old regions détectés"
    old_afters = [e['old_after_regions'] for e in events]
    assert max(old_afters) > min(old_afters), "Pas de variation d'old regions"