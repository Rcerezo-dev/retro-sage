from __future__ import annotations

from retro_sage.profile import (
    FEEDBACK_ADJUSTMENT,
    Profile,
    adjust_profile_with_feedback,
    affinity_tokens,
    build_profile,
    decade_of,
    signal_weight,
    split_genres,
)


def test_split_genres_tokenizes_and_normalizes():
    assert split_genres("RPG, Action RPG") == ["rpg", "action rpg"]
    assert split_genres(None) == []
    assert split_genres("  ") == []


def test_decade_of_handles_int_str_and_garbage():
    assert decade_of(1994) == 1990
    assert decade_of("1995") == 1990
    assert decade_of("1995-11-23") == 1990  # ScreenScraper a veces da fecha completa
    assert decade_of(None) is None
    assert decade_of("N/A") is None


def test_signal_weight_direction():
    assert signal_weight({"user_rating": 5}) > 0
    assert signal_weight({"user_rating": 1}) < 0
    assert signal_weight({"play_status": "completed"}) > 0
    assert signal_weight({"play_status": "dropped"}) < 0
    assert signal_weight({}) == 0.0


def test_build_profile_aggregates_likes_and_dislikes(library):
    profile = build_profile(library)
    assert profile.signals == 4  # 3 positivos + 1 negativo; candidatos no cuentan
    assert profile.genres["rpg"] > 0
    assert profile.genres["sports"] < 0
    assert profile.platforms["snes"] > 0
    assert profile.decades[1990] > 0
    assert profile.is_usable()


def test_affinity_tokens_merges_genres_and_tags():
    game = {"genre": "RPG, Action RPG", "tags": ["Metroidvania", "rpg", "  "]}
    assert affinity_tokens(game) == ["rpg", "action rpg", "metroidvania"]
    assert affinity_tokens({"genre": None, "tags": "no-una-lista"}) == []


def test_tags_feed_the_profile_and_reach_candidates():
    games = [
        {
            "id": 1,
            "title": "a",
            "platform": "snes",
            "genre": "RPG",
            "user_rating": 5,
            "tags": ["metroidvania"],
        },
    ]
    profile = build_profile(games)
    assert profile.genres["metroidvania"] > 0


def test_signal_weight_tolerates_garbage_types():
    assert signal_weight({"user_rating": "N/A", "play_count": "no"}) == 0.0
    assert signal_weight({"play_count": "3"}) > 0  # numérico como string cuenta


def test_profile_unusable_without_signals():
    profile = build_profile([{"id": 1, "title": "x", "platform": "gb", "genre": "Puzzle"}])
    assert profile.signals == 0
    assert not profile.is_usable()


_FEEDBACK_GAMES = [
    {"id": 1, "genre": "RPG", "platform": "snes"},
    {"id": 2, "genre": "RPG", "platform": "snes"},
    {"id": 3, "genre": "RPG", "platform": "snes"},
]


def test_adjust_profile_baja_la_afinidad_con_fallos_repetidos():
    profile = Profile(genres={"rpg": 1.0}, signals=5)
    evaluated = [{"game_id": gid, "outcome": "fallo"} for gid in (1, 2, 3)]
    adjusted = adjust_profile_with_feedback(profile, evaluated, _FEEDBACK_GAMES)
    assert adjusted.genres["rpg"] == 1.0 * (1 - FEEDBACK_ADJUSTMENT)


def test_adjust_profile_sube_la_afinidad_con_aciertos_repetidos():
    profile = Profile(genres={"rpg": 1.0}, signals=5)
    evaluated = [{"game_id": gid, "outcome": "acierto"} for gid in (1, 2, 3)]
    adjusted = adjust_profile_with_feedback(profile, evaluated, _FEEDBACK_GAMES)
    assert adjusted.genres["rpg"] == 1.0 * (1 + FEEDBACK_ADJUSTMENT)


def test_adjust_profile_ajuste_acotado_dentro_del_limite():
    profile = Profile(genres={"rpg": 1.0}, signals=5)
    evaluated = [{"game_id": gid, "outcome": "acierto"} for gid in (1, 2, 3)]
    adjusted = adjust_profile_with_feedback(profile, evaluated, _FEEDBACK_GAMES)
    assert adjusted.genres["rpg"] <= 1.0 * (1 + FEEDBACK_ADJUSTMENT)


def test_adjust_profile_sin_historico_deja_el_perfil_igual():
    profile = Profile(genres={"rpg": 1.0}, platforms={"snes": 0.5}, signals=5)
    adjusted = adjust_profile_with_feedback(profile, [], _FEEDBACK_GAMES)
    assert adjusted.genres == profile.genres
    assert adjusted.platforms == profile.platforms


def test_adjust_profile_ignora_tokens_con_muestra_insuficiente():
    profile = Profile(genres={"rpg": 1.0}, signals=5)
    evaluated = [{"game_id": 1, "outcome": "fallo"}, {"game_id": 2, "outcome": "fallo"}]  # solo 2
    adjusted = adjust_profile_with_feedback(profile, evaluated, _FEEDBACK_GAMES)
    assert adjusted.genres["rpg"] == 1.0  # sin cambios, bajo el umbral


def test_adjust_profile_no_inventa_afinidades_nuevas():
    profile = Profile(genres={}, signals=5)  # sin afinidad previa a rpg
    evaluated = [{"game_id": gid, "outcome": "acierto"} for gid in (1, 2, 3)]
    adjusted = adjust_profile_with_feedback(profile, evaluated, _FEEDBACK_GAMES)
    assert "rpg" not in adjusted.genres  # el histórico refuerza, no inventa gustos
