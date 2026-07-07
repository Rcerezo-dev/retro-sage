from __future__ import annotations

from retro_sage.embeddings import cosine, embed_games, game_text, similarity_to_favorites


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


def test_similarity_to_favorites_ordena_por_parecido(library, fake_encoder, tmp_path):
    vectors = embed_games(library, encoder=fake_encoder, cache_path=tmp_path / "cache.json")
    sims = similarity_to_favorites(library, vectors)
    assert sims[6] > sims[7]  # Earthbound (rpg) más cerca de los favoritos que FIFA
    assert sims[7] == 0.0  # deporte ortogonal a un perfil rpg
    assert 0.0 <= min(sims.values()) and max(sims.values()) <= 1.0


def test_similarity_sin_favoritos_devuelve_vacio(fake_encoder, tmp_path):
    games = [{"id": 1, "title": "x", "genre": "RPG"}]  # nadie con señal positiva
    vectors = embed_games(games, encoder=fake_encoder, cache_path=tmp_path / "cache.json")
    assert similarity_to_favorites(games, vectors) == {}


def test_embed_games_ignora_cache_corrupta(library, fake_encoder, tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text("{esto no es json", encoding="utf-8")
    vectors = embed_games(library, encoder=fake_encoder, cache_path=cache)
    assert len(vectors) == len(library)
