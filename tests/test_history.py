from __future__ import annotations

from retro_sage.history import load_history, record_recommendations


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
