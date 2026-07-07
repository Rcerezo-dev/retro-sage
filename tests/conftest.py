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
        "description": signals.get("description"),
        "play_count": signals.get("play_count", 0),
        "first_played_at": None,
        "last_played_at": None,
        "play_status": signals.get("play_status"),
        "user_rating": signals.get("user_rating"),
        "tags": signals.get("tags", []),
        "notes": None,
    }


@pytest.fixture(autouse=True)
def _sin_credenciales_reales(monkeypatch):
    """Los tests nunca tocan APIs reales: fuera credenciales del entorno."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture
def library() -> list[dict]:
    """Usuario al que le encantan los RPG de SNES de los 90 y odia los deportes."""
    return [
        # Señales positivas
        _game(
            1,
            "Chrono Trigger",
            "snes",
            "RPG",
            1995,
            user_rating=5,
            play_status="completed",
            description="rpg de viajes en el tiempo con historia épica",
        ),
        _game(
            2,
            "Final Fantasy VI",
            "snes",
            "RPG",
            1994,
            user_rating=5,
            play_count=8,
            description="rpg de fantasía con un imperio y catorce protagonistas",
        ),
        _game(
            3,
            "Secret of Mana",
            "snes",
            "RPG, Action RPG",
            1993,
            play_status="playing",
            description="rpg de acción cooperativo en tiempo real",
        ),
        # Señal negativa
        _game(
            4,
            "Madden 95",
            "megadrive",
            "Sports",
            1994,
            user_rating=1,
            play_status="dropped",
            description="deporte, fútbol americano de la NFL",
        ),
        # Candidatos (sin señal)
        _game(
            5,
            "Terranigma",
            "snes",
            "RPG, Action RPG",
            1995,
            description="rpg de acción sobre la resurrección del mundo",
        ),
        _game(
            6,
            "Earthbound",
            "snes",
            "RPG",
            1994,
            description="rpg excéntrico ambientado en la américa moderna",
        ),
        _game(
            7,
            "FIFA 96",
            "megadrive",
            "Sports",
            1995,
            description="deporte, fútbol con licencias oficiales",
        ),
        _game(
            8,
            "Tetris",
            "gb",
            "Puzzle",
            1989,
            description="puzzle de piezas que caen",
        ),
        _game(9, "Sin metadata", "psx", None, None),
    ]


# Espacio de vectores fake para los tests de embeddings: una dimensión por
# palabra clave. Determinista, sin red y sin descargar el modelo en CI.
_FAKE_DIMS = ("rpg", "deporte", "puzzle", "acción")


@pytest.fixture
def fake_encoder():
    """Encoder inyectable: vector = conteo de palabras clave. Cuenta llamadas."""

    def encode(texts: list[str]) -> list[list[float]]:
        encode.calls += 1
        encode.texts_seen += len(texts)
        return [[float(t.casefold().count(dim)) for dim in _FAKE_DIMS] for t in texts]

    encode.calls = 0
    encode.texts_seen = 0
    return encode
