"""Scoring: afinidad del perfil contra los juegos no jugados.

Mezcla normalizada de género + plataforma + década (60/25/15 por defecto) y,
si hay vectores del extra [embeddings], un 4º término: similitud semántica con
los favoritos. Sin vectores, el resultado es exactamente el de v0.1.
Cada item lleva una razón legible en español para el panel del Vault.
"""

from __future__ import annotations

from .profile import Profile, _as_number, affinity_tokens, decade_of

# Pesos crudos (género, plataforma, década, semántica) — se normalizan en
# recommend(); el semántico solo cuenta si hay similitud disponible.
# Sobreescribibles desde la CLI con --weights.
DEFAULT_WEIGHTS = (60.0, 25.0, 15.0, 30.0)


def is_candidate(game: dict) -> bool:
    """Candidato = juego del que el usuario aún no ha dicho ni jugado nada."""
    if _as_number(game.get("play_count")) > 0:
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


def _build_reason(
    game: dict, genre_hit: str | None, decade_hit: int | None, semantic_hit: bool = False
) -> str:
    parts = []
    if genre_hit:
        parts.append(f"te suelen gustar los {genre_hit}")
    if semantic_hit:
        parts.append("se parece a lo que mejor puntúas")
    if decade_hit:
        parts.append(f"encaja con tu época favorita ({decade_hit}s)")
    if not parts:
        parts.append("afín a tu plataforma habitual")
    return "Sin jugar todavía y " + " y ".join(parts) + "."


def recommend(
    games: list[dict],
    profile: Profile,
    top: int = 10,
    weights: tuple = DEFAULT_WEIGHTS,
    similarity: dict | None = None,
) -> list[dict]:
    """Devuelve los `top` items {id, title, platform, score, reason} para el Vault.

    `similarity` (opcional, v0.2) = {id: similitud [0, 1] con los favoritos},
    de `embeddings.similarity_to_favorites`. Sin ella, scoring v0.1 exacto.
    """
    if len(weights) == 3:
        weights = (*weights, 0.0)  # compat: pesos v0.1 sin término semántico
    weight_genre, weight_platform, weight_decade, weight_semantic = weights
    if not similarity:
        weight_semantic = 0.0
    total = weight_genre + weight_platform + weight_decade + weight_semantic
    if total <= 0:
        return []
    weight_genre, weight_platform, weight_decade, weight_semantic = (
        weight_genre / total,
        weight_platform / total,
        weight_decade / total,
        weight_semantic / total,
    )
    genre_prefs = _normalized(profile.genres)
    platform_prefs = _normalized(profile.platforms)
    decade_prefs = _normalized(profile.decades)

    scored: list[tuple[float, dict]] = []
    for game in games:
        if not is_candidate(game):
            continue
        genres = affinity_tokens(game)
        platform = (game.get("platform") or "").lower()
        dec = decade_of(game.get("year"))

        genre_score = _affinity(genre_prefs, genres)
        platform_score = _affinity(platform_prefs, [platform] if platform else [])
        decade_score = _affinity(decade_prefs, [dec] if dec is not None else [])
        semantic_score = similarity.get(game.get("id"), 0.0) if similarity else 0.0

        score = (
            weight_genre * genre_score
            + weight_platform * platform_score
            + weight_decade * decade_score
            + weight_semantic * semantic_score
        )
        # Un género que el usuario rechazó explícitamente (★1, dropped) resta:
        # que la época coincida no salva a un juego de deportes si odias los deportes.
        score -= weight_genre * _dislike(genre_prefs, genres)
        if score <= 0:
            continue

        genre_hit = next(
            (g for g in genres if genre_prefs.get(g, 0) > 0 and genre_prefs[g] == genre_score),
            None,
        )
        decade_hit = dec if dec is not None and decade_prefs.get(dec, 0) > 0 else None
        semantic_hit = weight_semantic > 0 and semantic_score >= 0.5
        scored.append(
            (
                score,
                {
                    "id": game.get("id"),
                    "title": game.get("title"),
                    "platform": game.get("platform"),
                    "score": round(score, 3),
                    "reason": _build_reason(game, genre_hit, decade_hit, semantic_hit),
                },
            )
        )

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:top]]
