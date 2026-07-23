from __future__ import annotations

import datetime

from retro_sage.history import (
    classify_outcome,
    evaluate_history,
    load_history,
    record_recommendations,
)

NOW = datetime.datetime(2026, 7, 23, tzinfo=datetime.UTC)


def _entry(game_id: int, days_ago: int) -> dict:
    recommended_at = NOW - datetime.timedelta(days=days_ago)
    return {
        "game_id": game_id,
        "title": f"juego-{game_id}",
        "recommended_at": recommended_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def test_record_recommendations_anade_una_linea_por_item(tmp_path):
    path = tmp_path / "history.jsonl"
    items = [
        {"id": 5, "title": "Terranigma", "platform": "snes", "score": 0.82, "reason": "..."},
        {"id": 6, "title": "Earthbound", "platform": "snes", "score": 0.71, "reason": "..."},
    ]
    record_recommendations(items, path=path)

    entries = load_history(path)
    assert len(entries) == 2
    assert entries[0]["game_id"] == 5
    assert entries[0]["title"] == "Terranigma"
    assert entries[0]["recommended_at"].endswith("Z")  # ISO 8601 UTC


def test_record_recommendations_es_append_no_overwrite(tmp_path):
    path = tmp_path / "history.jsonl"
    record_recommendations(
        [{"id": 1, "title": "a", "platform": "snes", "score": 1, "reason": "x"}], path
    )
    record_recommendations(
        [{"id": 2, "title": "b", "platform": "snes", "score": 1, "reason": "x"}], path
    )

    entries = load_history(path)
    assert [e["game_id"] for e in entries] == [1, 2]


def test_load_history_sin_fichero_devuelve_vacio(tmp_path):
    assert load_history(tmp_path / "no-existe.jsonl") == []


def test_load_history_ignora_lineas_corruptas(tmp_path):
    path = tmp_path / "history.jsonl"
    path.write_text('{"game_id": 1}\nesto no es json\n{"game_id": 2}\n', encoding="utf-8")
    entries = load_history(path)
    assert [e["game_id"] for e in entries] == [1, 2]


def test_classify_acierto_si_el_juego_ya_se_jugo():
    entry = _entry(1, days_ago=1)  # reciente, pero ya cambió de estado
    game = {"id": 1, "play_count": 3, "user_rating": None}
    assert classify_outcome(entry, {1: game}, NOW) == "acierto"


def test_classify_acierto_por_rating_sin_partidas():
    entry = _entry(1, days_ago=1)
    game = {"id": 1, "play_count": 0, "user_rating": 4}
    assert classify_outcome(entry, {1: game}, NOW) == "acierto"


def test_classify_fallo_si_paso_el_umbral_sin_cambios():
    entry = _entry(1, days_ago=20)
    game = {"id": 1, "play_count": 0, "user_rating": None}
    assert classify_outcome(entry, {1: game}, NOW, threshold_days=14) == "fallo"


def test_classify_pendiente_si_es_reciente_sin_cambios():
    entry = _entry(1, days_ago=2)
    game = {"id": 1, "play_count": 0, "user_rating": None}
    assert classify_outcome(entry, {1: game}, NOW, threshold_days=14) == "pendiente"


def test_classify_none_si_el_juego_ya_no_existe():
    entry = _entry(1, days_ago=20)
    assert classify_outcome(entry, {}, NOW) is None


def test_evaluate_history_combina_los_tres_casos():
    entries = [
        _entry(1, days_ago=1),  # acierto
        _entry(2, days_ago=20),  # fallo
        _entry(3, days_ago=2),  # pendiente
        _entry(4, days_ago=20),  # ya no existe en el export -> se omite
    ]
    games = [
        {"id": 1, "play_count": 5, "user_rating": None},
        {"id": 2, "play_count": 0, "user_rating": None},
        {"id": 3, "play_count": 0, "user_rating": None},
    ]
    evaluated = evaluate_history(entries, games, threshold_days=14, now=NOW)
    outcomes = {e["game_id"]: e["outcome"] for e in evaluated}
    assert outcomes == {1: "acierto", 2: "fallo", 3: "pendiente"}
