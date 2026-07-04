"""Scoring v0.1: afinidad del perfil contra los juegos no jugados.

Score = 0.60 · género + 0.25 · plataforma + 0.15 · década, normalizado a [0, 1].
Cada item lleva una razón legible en español para el panel del Vault.
"""

from __future__ import annotations

from .profile import Profile, decade_of, split_genres

_WEIGHT_GENRE = 0.60
_WEIGHT_PLATFORM = 0.25
_WEIGHT_DECADE = 0.15


def is_candidate(game: dict) -> bool:
    """Candidato = juego del que el usuario aún no ha dicho ni jugado nada."""
    if (game.get("play_count") or 0) > 0:
        return False
    if (game.get("play_status") or "") in ("completed", "playing", "dropped"):
        return False
    return not game.get("user_rating")


def _normalized(prefs: dict) -> dict:
    """Escala los pesos a [-1, 1] dividiendo por el máximo absoluto."""
    if not prefs:
        return {}
    peak = max(abs(v) for v in prefs.values())
    if peak == 0:
        return {}
    return {k: v / peak for k, v in prefs.items()}


def _affinity(normalized_prefs: dict, keys: list) -> float:
    """Mejor afinidad entre las claves del juego, recortada a [0, 1]."""
    values = [normalized_prefs[k] for k in keys if k in normalized_prefs]
    if not values:
        return 0.0
    return max(0.0, max(values))


def _dislike(normalized_prefs: dict, keys: list) -> float:
    """Magnitud del rechazo explícito (peor afinidad negativa), en [0, 1]."""
    values = [normalized_prefs[k] for k in keys if k in normalized_prefs]
    if not values:
        return 0.0
    return max(0.0, -min(values))


def _build_reason(game: dict, genre_hit: str | None, decade_hit: int | None) -> str:
    parts = []
    if genre_hit:
        parts.append(f"te suelen gustar los {genre_hit}")
    if decade_hit:
        parts.append(f"encaja con tu época favorita ({decade_hit}s)")
    if not parts:
        parts.append("afín a tu plataforma habitual")
    return "Sin jugar todavía y " + " y ".join(parts) + "."


def recommend(games: list[dict], profile: Profile, top: int = 10) -> list[dict]:
    """Devuelve los `top` items {id, title, platform, score, reason} para el Vault."""
    genre_prefs = _normalized(profile.genres)
    platform_prefs = _normalized(profile.platforms)
    decade_prefs = _normalized(profile.decades)

    scored: list[tuple[float, dict]] = []
    for game in games:
        if not is_candidate(game):
            continue
        genres = split_genres(game.get("genre"))
        platform = (game.get("platform") or "").lower()
        dec = decade_of(game.get("year"))

        genre_score = _affinity(genre_prefs, genres)
        platform_score = _affinity(platform_prefs, [platform] if platform else [])
        decade_score = _affinity(decade_prefs, [dec] if dec is not None else [])

        score = (
            _WEIGHT_GENRE * genre_score
            + _WEIGHT_PLATFORM * platform_score
            + _WEIGHT_DECADE * decade_score
        )
        # Un género que el usuario rechazó explícitamente (★1, dropped) resta:
        # que la época coincida no salva a un juego de deportes si odias los deportes.
        score -= _WEIGHT_GENRE * _dislike(genre_prefs, genres)
        if score <= 0:
            continue

        genre_hit = next(
            (g for g in genres if genre_prefs.get(g, 0) > 0 and genre_prefs[g] == genre_score),
            None,
        )
        decade_hit = dec if dec is not None and decade_prefs.get(dec, 0) > 0 else None
        scored.append(
            (
                score,
                {
                    "id": game.get("id"),
                    "title": game.get("title"),
                    "platform": game.get("platform"),
                    "score": round(score, 3),
                    "reason": _build_reason(game, genre_hit, decade_hit),
                },
            )
        )

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:top]]
