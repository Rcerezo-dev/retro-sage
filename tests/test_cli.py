from __future__ import annotations

import json

import pytest

from retro_sage import embeddings
from retro_sage.cli import main


@pytest.fixture
def export_file(tmp_path, library):
    export = tmp_path / "export.json"
    export.write_text(json.dumps({"games": library}), encoding="utf-8")
    return str(export)


@pytest.fixture
def fake_model(monkeypatch, fake_encoder, tmp_path):
    """Sustituye el modelo real por el encoder fake y aísla la caché en tmp."""
    monkeypatch.setattr(embeddings, "_load_encoder", lambda: fake_encoder)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))
    return fake_encoder


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


def test_weird_exports_never_traceback(tmp_path, capsys):
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{esto no es json", encoding="utf-8")
    assert main(["recommend", "--file", str(corrupt)]) == 1

    not_a_list = tmp_path / "games_dict.json"
    not_a_list.write_text('{"games": {"1": {}}}', encoding="utf-8")
    assert main(["recommend", "--file", str(not_a_list)]) == 1

    assert main(["recommend", "--file", str(tmp_path / "no_existe.json")]) == 1
    assert capsys.readouterr().err.count("✗") == 3


def test_mixed_garbage_entries_are_filtered(tmp_path, library, capsys):
    dirty = library + [None, "cadena", 42]
    export = tmp_path / "dirty.json"
    export.write_text(json.dumps({"games": dirty}), encoding="utf-8")
    assert main(["recommend", "--file", str(export)]) == 0
    assert "Perfil: 4 señales" in capsys.readouterr().out


def test_profile_subcommand_prints_affinities(tmp_path, library, capsys):
    export = tmp_path / "export.json"
    export.write_text(json.dumps({"games": library}), encoding="utf-8")
    assert main(["profile", "--file", str(export)]) == 0
    out = capsys.readouterr().out
    assert "Perfil: 4 señales" in out
    assert "rpg" in out and "snes" in out and "1990s" in out
    assert "-" in out  # el rechazo (sports) también se muestra


def test_weights_flag(tmp_path, library, capsys):
    export = tmp_path / "export.json"
    export.write_text(json.dumps({"games": library}), encoding="utf-8")
    assert main(["recommend", "--file", str(export), "--weights", "100,0,0"]) == 0
    assert "Terranigma" in capsys.readouterr().out

    with pytest.raises(SystemExit):  # argparse rechaza formatos inválidos
        main(["recommend", "--file", str(export), "--weights", "1,2"])
    with pytest.raises(SystemExit):
        main(["recommend", "--file", str(export), "--weights", "0,0,0"])


def test_similar_encuentra_juegos_del_mismo_palo(export_file, fake_model, capsys):
    assert main(["similar", "Chrono Trigger", "--file", export_file, "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "Parecidos a «Chrono Trigger»" in out
    assert "Final Fantasy VI" in out or "Earthbound" in out
    assert "FIFA 96" not in out  # ortogonal: los deportes no se parecen a un rpg


def test_similar_titulo_ambiguo_lista_opciones(export_file, fake_model, capsys):
    assert main(["similar", "fi", "--file", export_file]) == 0  # Final Fantasy VI y FIFA 96
    out = capsys.readouterr().out
    assert "sé más específico" in out
    assert "Final Fantasy VI" in out and "FIFA 96" in out


def test_similar_titulo_inexistente_falla_limpio(export_file, fake_model, capsys):
    assert main(["similar", "Doom", "--file", export_file]) == 1
    assert "✗" in capsys.readouterr().err


def test_search_consulta_libre(export_file, fake_model, capsys):
    assert main(["search", "rpg de acción", "--file", export_file, "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "Secret of Mana" in out or "Terranigma" in out
    assert "FIFA 96" not in out


def test_sin_extra_embeddings_mensaje_claro(export_file, monkeypatch, capsys):
    def sin_extra():
        raise embeddings.EmbeddingsError('pip install "retro-sage[embeddings]"')

    monkeypatch.setattr(embeddings, "_load_encoder", sin_extra)
    monkeypatch.setenv("LOCALAPPDATA", "cache-inexistente")
    assert main(["search", "lo que sea", "--file", export_file]) == 1
    assert "retro-sage[embeddings]" in capsys.readouterr().err


def test_similar_usa_la_cache_en_la_segunda_pasada(export_file, fake_model, capsys):
    assert main(["similar", "Tetris", "--file", export_file]) == 0
    llamadas = fake_model.texts_seen
    assert main(["similar", "Tetris", "--file", export_file]) == 0
    assert fake_model.texts_seen == llamadas  # nada que recomputar
