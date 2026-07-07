from __future__ import annotations

from retro_sage.embeddings import cosine, embed_games, game_text


def test_game_text_compone_los_campos_disponibles(library):
    assert game_text(library[0]) == (
        "Chrono Trigger. RPG. rpg de viajes en el tiempo con historia épica"
    )
    assert game_text(library[8]) == "Sin metadata"  # sin género ni descripción
    assert game_text({"id": 1}) == ""  # sin texto alguno


def test_cosine():
    assert cosine([1.0, 0.0], [2.0, 0.0]) == 1.0
    assert cosine([1.0, 0.0], [0.0, 3.0]) == 0.0
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0  # vector nulo no revienta


def test_embed_games_devuelve_vector_por_juego(library, fake_encoder, tmp_path):
    vectors = embed_games(library, encoder=fake_encoder, cache_path=tmp_path / "cache.json")
    assert set(vectors) == {g["id"] for g in library}  # todos tienen título → todos entran
    assert cosine(vectors[1], vectors[6]) > 0.9  # dos rpg apuntan igual
    assert cosine(vectors[1], vectors[4]) == 0.0  # rpg vs deporte, ortogonales


def test_embed_games_cachea_y_solo_recomputa_lo_nuevo(library, fake_encoder, tmp_path):
    cache = tmp_path / "cache.json"
    embed_games(library, encoder=fake_encoder, cache_path=cache)
    assert fake_encoder.texts_seen == len(library)

    # Segunda pasada: todo en caché, cero llamadas nuevas.
    embed_games(library, encoder=fake_encoder, cache_path=cache)
    assert fake_encoder.texts_seen == len(library)

    # Cambia una descripción: solo ese juego se recomputa.
    library[0]["description"] = "ahora es otro texto"
    embed_games(library, encoder=fake_encoder, cache_path=cache)
    assert fake_encoder.texts_seen == len(library) + 1


def test_embed_games_ignora_cache_corrupta(library, fake_encoder, tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text("{esto no es json", encoding="utf-8")
    vectors = embed_games(library, encoder=fake_encoder, cache_path=cache)
    assert len(vectors) == len(library)
