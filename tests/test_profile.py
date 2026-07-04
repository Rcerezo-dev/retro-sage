from __future__ import annotations

from retro_sage.profile import build_profile, decade_of, signal_weight, split_genres


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


def test_profile_unusable_without_signals():
    profile = build_profile([{"id": 1, "title": "x", "platform": "gb", "genre": "Puzzle"}])
    assert profile.signals == 0
    assert not profile.is_usable()
