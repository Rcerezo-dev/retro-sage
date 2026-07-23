from __future__ import annotations

import json

import pytest

from retro_sage import chat, embeddings, history
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

    # 4º peso (semántica): aceptado, y sin extra [embeddings] no cambia nada
    assert main(["recommend", "--file", str(export), "--weights", "60,25,15,100"]) == 0
    assert "señal semántica" not in capsys.readouterr().out

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


def test_recommend_con_extra_activa_senal_semantica(export_file, fake_model, capsys):
    assert main(["recommend", "--file", export_file, "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "señal semántica activa" in out
    assert "Terranigma" in out or "Earthbound" in out


def test_similar_usa_la_cache_en_la_segunda_pasada(export_file, fake_model, capsys):
    assert main(["similar", "Tetris", "--file", export_file]) == 0
    llamadas = fake_model.texts_seen
    assert main(["similar", "Tetris", "--file", export_file]) == 0
    assert fake_model.texts_seen == llamadas  # nada que recomputar


def _fake_claude(monkeypatch, text: str):
    """Sustituye el cliente de anthropic por uno fake que devuelve `text`."""
    from types import SimpleNamespace

    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn"
        )

    fake = SimpleNamespace(messages=SimpleNamespace(create=create), calls=calls)
    monkeypatch.setattr(chat, "_client", lambda: fake)
    return fake


def test_ask_responde_con_un_solo_request(export_file, monkeypatch, capsys):
    fake = _fake_claude(monkeypatch, "Juega a Terranigma: encaja con tus rpg de SNES.")
    assert main(["ask", "algo largo y épico", "--file", export_file]) == 0
    assert "Terranigma" in capsys.readouterr().out
    assert len(fake.calls) == 1


def test_ask_sin_credenciales_falla_limpio(export_file, monkeypatch, capsys):
    def sin_credenciales():
        raise chat.ChatError('pip install "retro-sage[chat]"')

    monkeypatch.setattr(chat, "_client", sin_credenciales)
    assert main(["ask", "lo que sea", "--file", export_file]) == 1
    assert "retro-sage[chat]" in capsys.readouterr().err


def test_recommend_explain_reescribe_las_razones(export_file, monkeypatch, capsys):
    razones = json.dumps(
        {
            "reasons": [
                {"id": 5, "reason": "Como Chrono Trigger pero sobre resucitar el mundo."},
                {"id": 6, "reason": "El rpg más raro de tu SNES, y eso te va."},
            ]
        }
    )
    fake = _fake_claude(monkeypatch, razones)
    assert main(["recommend", "--file", export_file, "--explain", "--top", "3"]) == 0
    out = capsys.readouterr().out
    assert "resucitar el mundo" in out
    assert len(fake.calls) == 1


def test_ask_con_gemini_free_tier(export_file, monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-test")
    monkeypatch.setattr(
        chat,
        "_post_json",
        lambda url, body, headers: {
            "candidates": [{"content": {"parts": [{"text": "Terranigma encaja contigo."}]}}]
        },
    )
    assert main(["ask", "algo largo", "--file", export_file]) == 0
    assert "Terranigma" in capsys.readouterr().out


def test_recommend_explain_sin_credenciales_degrada_a_v01(export_file, monkeypatch, capsys):
    def sin_credenciales():
        raise chat.ChatError("No hay credenciales de la API de Claude")

    monkeypatch.setattr(chat, "_client", sin_credenciales)
    assert main(["recommend", "--file", export_file, "--explain"]) == 0
    captured = capsys.readouterr()
    assert "Sin jugar todavía" in captured.out  # razones del scorer local, como v0.1
    assert "razones del scorer local" in captured.err


def test_recommend_push_registra_historial_local(export_file, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("retro_sage.cli.push_recommendations", lambda items, vault: len(items))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))

    assert main(["recommend", "--file", export_file, "--push", "--top", "3"]) == 0
    assert "recomendaciones enviadas" in capsys.readouterr().out

    entries = history.load_history(tmp_path / "cache" / "retro-sage" / "history.jsonl")
    assert {e["title"] for e in entries} <= {"Terranigma", "Earthbound", "FIFA 96", "Tetris"}
    assert entries  # al menos un candidato encajó
    assert all(e["recommended_at"] for e in entries)
