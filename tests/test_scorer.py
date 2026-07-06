from __future__ import annotations

from retro_sage.profile import build_profile
from retro_sage.scorer import is_candidate, recommend
from retro_sage.vault_client import MAX_ITEMS


def test_played_or_rated_games_are_not_candidates(library):
    by_id = {g["id"]: g for g in library}
    assert not is_candidate(by_id[1])  # rated + completed
    assert not is_candidate(by_id[3])  # playing
    assert not is_candidate(by_id[4])  # dropped
    assert is_candidate(by_id[5])
    assert is_candidate(by_id[9])  # sin metadata sigue siendo candidato


def test_recommend_prefers_profile_matches(library):
    profile = build_profile(library)
    items = recommend(library, profile, top=10)
    titles = [item["title"] for item in items]

    # Los RPG de SNES de los 90 van primero; el juego de deportes no aparece
    assert titles[0] in ("Terranigma", "Earthbound")
    assert "FIFA 96" not in titles
    # Nunca se recomienda algo ya jugado/puntuado
    assert "Chrono Trigger" not in titles


def test_items_match_vault_contract(library):
    profile = build_profile(library)
    items = recommend(library, profile, top=3)
    assert 0 < len(items) <= 3
    for item in items:
        assert set(item) == {"id", "title", "platform", "score", "reason"}
        assert 0.0 < item["score"] <= 1.0
        assert item["reason"]
    # Orden descendente por score
    scores = [item["score"] for item in items]
    assert scores == sorted(scores, reverse=True)
    assert len(items) <= MAX_ITEMS


def test_shared_tag_scores_a_candidate():
    games = [
        {
            "id": 1,
            "title": "fav",
            "platform": "snes",
            "genre": None,
            "user_rating": 5,
            "play_status": "completed",
            "tags": ["metroidvania"],
        },
        {
            "id": 2,
            "title": "fav2",
            "platform": "snes",
            "genre": None,
            "user_rating": 4,
            "tags": ["metroidvania"],
        },
        {"id": 3, "title": "cand", "platform": "gba", "genre": None, "tags": ["metroidvania"]},
        {"id": 4, "title": "soso", "platform": "gba", "genre": None, "tags": []},
    ]
    profile = build_profile(games)
    titles = [item["title"] for item in recommend(games, profile)]
    assert "cand" in titles
    assert "soso" not in titles  # sin tag compartido no hay afinidad de género


def test_custom_weights_change_the_mix(library):
    profile = build_profile(library)
    # Solo década: Tetris (1989) queda fuera; los de los 90 puntúan igual por época
    items = recommend(library, profile, weights=(0.0, 0.0, 1.0))
    titles = [item["title"] for item in items]
    assert "Tetris" not in titles
    assert "Terranigma" in titles


def test_is_candidate_tolerates_string_play_count():
    assert not is_candidate({"play_count": "2"})
    assert is_candidate({"play_count": "0", "tags": []})


def test_recommend_empty_when_no_positive_affinity(library):
    # Perfil de alguien que solo ha odiado un puzzle: nada de la lista encaja
    hater = [
        {
            "id": 1,
            "title": "x",
            "platform": "gb",
            "genre": "Puzzle",
            "year": 1989,
            "user_rating": 1,
            "play_count": 0,
            "play_status": "dropped",
            "tags": [],
        },
        {
            "id": 2,
            "title": "y",
            "platform": "gb",
            "genre": "Puzzle",
            "year": 1990,
            "play_count": 0,
            "tags": [],
        },
    ]
    profile = build_profile(hater)
    assert recommend(hater, profile) == []
