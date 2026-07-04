from __future__ import annotations

import pytest


def _game(gid: int, title: str, platform: str, genre: str | None, year, **signals) -> dict:
    """Mismo shape que GET /api/export-history de Retro Vault."""
    return {
        "id": gid,
        "title": title,
        "platform": platform,
        "genre": genre,
        "year": year,
        "developer": None,
        "publisher": None,
        "description": None,
        "play_count": signals.get("play_count", 0),
        "first_played_at": None,
        "last_played_at": None,
        "play_status": signals.get("play_status"),
        "user_rating": signals.get("user_rating"),
        "tags": signals.get("tags", []),
        "notes": None,
    }


@pytest.fixture
def library() -> list[dict]:
    """Usuario al que le encantan los RPG de SNES de los 90 y odia los deportes."""
    return [
        # Señales positivas
        _game(1, "Chrono Trigger", "snes", "RPG", 1995, user_rating=5, play_status="completed"),
        _game(2, "Final Fantasy VI", "snes", "RPG", 1994, user_rating=5, play_count=8),
        _game(3, "Secret of Mana", "snes", "RPG, Action RPG", 1993, play_status="playing"),
        # Señal negativa
        _game(4, "Madden 95", "megadrive", "Sports", 1994, user_rating=1, play_status="dropped"),
        # Candidatos (sin señal)
        _game(5, "Terranigma", "snes", "RPG, Action RPG", 1995),
        _game(6, "Earthbound", "snes", "RPG", 1994),
        _game(7, "FIFA 96", "megadrive", "Sports", 1995),
        _game(8, "Tetris", "gb", "Puzzle", 1989),
        _game(9, "Sin metadata", "psx", None, None),
    ]
