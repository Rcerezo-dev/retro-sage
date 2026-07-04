from __future__ import annotations

import json

from retro_sage.cli import main


def test_recommend_from_file_prints_top(tmp_path, library, capsys):
    export = tmp_path / "export.json"
    export.write_text(json.dumps({"total": len(library), "games": library}), encoding="utf-8")

    assert main(["recommend", "--file", str(export), "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "Perfil: 4 señales" in out
    assert "Terranigma" in out or "Earthbound" in out


def test_recommend_without_signals_shows_cta(tmp_path, capsys):
    games = [
        {
            "id": 1,
            "title": "x",
            "platform": "gb",
            "genre": "Puzzle",
            "year": 1989,
            "play_count": 0,
            "tags": [],
        }
    ]
    export = tmp_path / "export.json"
    export.write_text(json.dumps({"total": 1, "games": games}), encoding="utf-8")

    assert main(["recommend", "--file", str(export)]) == 0
    assert "Marca ratings" in capsys.readouterr().out


def test_recommend_bad_file_fails_cleanly(tmp_path, capsys):
    bogus = tmp_path / "bogus.json"
    bogus.write_text('{"nada": true}', encoding="utf-8")
    assert main(["recommend", "--file", str(bogus)]) == 1
    assert "✗" in capsys.readouterr().err
