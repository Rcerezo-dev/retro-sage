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

# Bucle de feedback (v0.4): ajuste heurístico acotado, no ML entrenado.
FEEDBACK_ADJUSTMENT = 0.15  # factor máximo: ±15% de la afinidad existente
MIN_RESOLVED_PER_TOKEN = 3  # ignora tokens con muestra pequeña (mismo umbral que MIN_SIGNALS)


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


def affinity_tokens(game: dict) -> list[str]:
    """Tokens de afinidad de un juego: géneros + tags del usuario, normalizados.

    ponytail: los tags entran al mismo espacio que los géneros en vez de ser
    una 4ª dimensión — un tag compartido entre un favorito y un candidato
    puntúa vía el peso de género. Dimensión propia solo si algún día estorba.
    """
    tokens = split_genres(game.get("genre"))
    tags = game.get("tags") or []
    if isinstance(tags, list):
        tokens += [str(t).strip().lower() for t in tags if str(t).strip()]
    return list(dict.fromkeys(tokens))  # dedup conservando orden


def decade_of(year) -> int | None:
    """1994 → 1990. Acepta int o str; None si no es parseable."""
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return None
    return (y // 10) * 10 if 1950 <= y <= 2100 else None


def _as_number(value) -> float:
    """float(value) tolerante: 0.0 si el export trae basura ('N/A', None, [])."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def signal_weight(game: dict) -> float:
    """Peso de la señal de un juego. 0.0 = el usuario no ha dicho nada de él."""
    weight = 0.0
    rating = _as_number(game.get("user_rating"))
    if rating:
        weight += (rating - 2.5) / 2.5  # 1★ → -0.6 · 3★ → +0.2 · 5★ → +1.0
    weight += _STATUS_WEIGHT.get(game.get("play_status") or "", 0.0)
    play_count = _as_number(game.get("play_count"))
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
        for genre in affinity_tokens(game):
            profile.genres[genre] = profile.genres.get(genre, 0.0) + weight
        platform = (game.get("platform") or "").lower()
        if platform:
            profile.platforms[platform] = profile.platforms.get(platform, 0.0) + weight
        dec = decade_of(game.get("year"))
        if dec is not None:
            profile.decades[dec] = profile.decades.get(dec, 0.0) + weight
    return profile


def _hit_rates(evaluated: list[dict], games_by_id: dict, tokens_of) -> dict[str, float]:
    """token → tasa de acierto, solo para tokens con >= MIN_RESOLVED_PER_TOKEN resueltos.

    Pendientes no cuentan como resueltos (ni a favor ni en contra).
    """
    counts: dict[str, list[int]] = {}  # token -> [aciertos, resueltos]
    for entry in evaluated:
        if entry["outcome"] == "pendiente":
            continue
        game = games_by_id.get(entry["game_id"])
        if game is None:
            continue
        for token in tokens_of(game):
            bucket = counts.setdefault(token, [0, 0])
            bucket[1] += 1
            if entry["outcome"] == "acierto":
                bucket[0] += 1
    return {
        token: hits / resolved
        for token, (hits, resolved) in counts.items()
        if resolved >= MIN_RESOLVED_PER_TOKEN
    }


def _apply_hit_rates(prefs: dict[str, float], hit_rates: dict[str, float]) -> dict[str, float]:
    """Reescala cada afinidad ya existente en `prefs` según su tasa de acierto.

    50% de acierto = neutro (factor 1.0); 100% = +FEEDBACK_ADJUSTMENT; 0% =
    -FEEDBACK_ADJUSTMENT. Tokens sin afinidad previa no se tocan — el
    histórico solo refuerza o atenúa gustos ya detectados, no inventa nuevos.
    """
    adjusted = dict(prefs)
    for token, rate in hit_rates.items():
        if token in adjusted:
            factor = 1 + FEEDBACK_ADJUSTMENT * (rate - 0.5) * 2
            adjusted[token] *= factor
    return adjusted


def adjust_profile_with_feedback(
    profile: Profile, evaluated: list[dict], games: list[dict]
) -> Profile:
    """Refuerza/atenúa afinidades de `profile` según el historial de recomendaciones.

    Heurística acotada (± FEEDBACK_ADJUSTMENT), nada de ML entrenado. Sin
    histórico suficiente por token, ese género/plataforma queda idéntico —
    con un `evaluated` vacío, `profile` sale exactamente igual que hoy.
    """
    games_by_id = {g.get("id"): g for g in games}
    genre_rates = _hit_rates(evaluated, games_by_id, affinity_tokens)
    platform_rates = _hit_rates(
        evaluated,
        games_by_id,
        lambda g: [g["platform"].lower()] if g.get("platform") else [],
    )
    return Profile(
        genres=_apply_hit_rates(profile.genres, genre_rates),
        platforms=_apply_hit_rates(profile.platforms, platform_rates),
        decades=dict(profile.decades),
        signals=profile.signals,
    )
