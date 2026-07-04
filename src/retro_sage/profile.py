"""Construcción del perfil de jugador a partir de las señales del Vault.

Señales disponibles en el export (todas opcionales por juego):
- user_rating (1-5 ★)      — la señal más fuerte, en ambas direcciones
- play_status              — completed / playing / dropped / pending
- play_count               — sesiones detectadas por el sync de saves

El perfil son afinidades ponderadas por género, plataforma y década.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Un juego con status positivo cuenta aunque no tenga rating.
_STATUS_WEIGHT = {"completed": 1.0, "playing": 0.8, "dropped": -0.8}
_GENRE_SPLIT = re.compile(r"[,/;|]| - ")


@dataclass(slots=True)
class Profile:
    """Afinidades del usuario. Pesos positivos = le gusta; negativos = evitar."""

    genres: dict[str, float] = field(default_factory=dict)
    platforms: dict[str, float] = field(default_factory=dict)
    decades: dict[int, float] = field(default_factory=dict)
    signals: int = 0  # nº de juegos que aportaron señal

    def is_usable(self, min_signals: int = 3) -> bool:
        return self.signals >= min_signals and bool(self.genres or self.platforms)


def split_genres(genre: str | None) -> list[str]:
    """'RPG, Action RPG' → ['rpg', 'action rpg'] — tokens normalizados."""
    if not genre:
        return []
    return [tok.strip().lower() for tok in _GENRE_SPLIT.split(genre) if tok.strip()]


def decade_of(year) -> int | None:
    """1994 → 1990. Acepta int o str; None si no es parseable."""
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return None
    return (y // 10) * 10 if 1950 <= y <= 2100 else None


def signal_weight(game: dict) -> float:
    """Peso de la señal de un juego. 0.0 = el usuario no ha dicho nada de él."""
    weight = 0.0
    rating = game.get("user_rating")
    if rating:
        weight += (float(rating) - 2.5) / 2.5  # 1★ → -0.6 · 3★ → +0.2 · 5★ → +1.0
    weight += _STATUS_WEIGHT.get(game.get("play_status") or "", 0.0)
    play_count = game.get("play_count") or 0
    if play_count > 0:
        weight += min(play_count, 10) / 10 * 0.5  # jugarlo mucho es señal suave
    return weight


def build_profile(games: list[dict]) -> Profile:
    """Agrega las señales de toda la biblioteca en un Profile."""
    profile = Profile()
    for game in games:
        weight = signal_weight(game)
        if weight == 0.0:
            continue
        profile.signals += 1
        for genre in split_genres(game.get("genre")):
            profile.genres[genre] = profile.genres.get(genre, 0.0) + weight
        platform = (game.get("platform") or "").lower()
        if platform:
            profile.platforms[platform] = profile.platforms.get(platform, 0.0) + weight
        dec = decade_of(game.get("year"))
        if dec is not None:
            profile.decades[dec] = profile.decades.get(dec, 0.0) + weight
    return profile
