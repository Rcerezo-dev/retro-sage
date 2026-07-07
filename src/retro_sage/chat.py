"""Modo explicado con Claude API (v0.3) — requiere el extra opcional [chat].

El núcleo sigue stdlib-only: `anthropic` se importa de forma perezosa dentro
de `_client()`. Control de coste: un solo request por invocación, con los
candidatos ya filtrados y puntuados por el scorer local.

Sin credenciales (ANTHROPIC_API_KEY, o un perfil de `ant auth login` que el
SDK detecta solo) se lanza `ChatError`: `ask` muestra el mensaje y sale
limpio, `recommend --explain` degrada a las razones del scorer (modo v0.1).
"""

from __future__ import annotations

import json

from .profile import Profile

DEFAULT_MODEL = "claude-opus-4-8"
MAX_TOKENS = 2000
MAX_CANDIDATES = 30  # techo de candidatos enviados: el scorer local ya filtró

_SYSTEM = (
    "Eres Retro Sage, el recomendador de la colección retro personal del usuario. "
    "Solo puedes hablar de juegos de la lista que se te proporciona: nunca inventes "
    "títulos ni recomiendes juegos fuera de ella. Responde en español, breve y concreto."
)

_EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "reasons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reasons"],
    "additionalProperties": False,
}


class ChatError(RuntimeError):
    """Falta el extra [chat], las credenciales, o falló la llamada a Claude."""


def _client():
    """Cliente de Anthropic, importado y construido bajo demanda."""
    try:
        import anthropic
    except ImportError as exc:
        raise ChatError(
            'Este comando necesita el extra [chat]: pip install "retro-sage[chat]"'
        ) from exc
    try:
        # Sin api_key explícita: el SDK resuelve ANTHROPIC_API_KEY o el perfil
        # de `ant auth login` por su cuenta.
        return anthropic.Anthropic()
    except Exception as exc:
        raise ChatError(
            "No hay credenciales de la API de Claude: exporta ANTHROPIC_API_KEY "
            "o inicia sesión con `ant auth login`."
        ) from exc


def _request(**kwargs):
    """Un único request a Claude; cualquier fallo se convierte en ChatError."""
    client = _client()
    try:
        response = client.messages.create(**kwargs)
    except ChatError:
        raise
    except Exception as exc:
        raise ChatError(f"La llamada a Claude falló: {exc}") from exc
    if getattr(response, "stop_reason", None) == "refusal":
        raise ChatError("Claude declinó responder a esta consulta.")
    return response


def _extract_text(response) -> str:
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


def _profile_summary(profile: Profile) -> str:
    def top(prefs: dict, n: int = 6) -> str:
        ranked = sorted(prefs.items(), key=lambda kv: kv[1], reverse=True)[:n]
        return ", ".join(f"{key} ({weight:+.1f})" for key, weight in ranked) or "sin datos"

    return (
        f"Géneros y tags: {top(profile.genres)}\n"
        f"Plataformas: {top(profile.platforms)}\n"
        f"Décadas: {top({f'{d}s': w for d, w in profile.decades.items()})}"
    )


def _format_games(items: list[dict], by_id: dict) -> str:
    lines = []
    for item in items:
        game = by_id.get(item.get("id"), {})
        desc = str(game.get("description") or "").strip()[:200]
        parts = [
            f"id {item.get('id')}: {item.get('title')}",
            f"[{item.get('platform')}]",
            str(game.get("genre") or "género desconocido"),
            str(game.get("year") or "año desconocido"),
            f"afinidad local {item.get('score')}",
        ]
        line = "- " + " · ".join(parts)
        if desc:
            line += f" — {desc}"
        lines.append(line)
    return "\n".join(lines)


def ask(
    question: str,
    profile: Profile,
    items: list[dict],
    games: list[dict],
    model: str = DEFAULT_MODEL,
) -> str:
    """Responde una consulta libre razonando sobre perfil + candidatos. Un request."""
    by_id = {g.get("id"): g for g in games}
    prompt = (
        "Perfil del jugador (afinidades; peso positivo = le gusta, negativo = rechazo):\n"
        f"{_profile_summary(profile)}\n\n"
        "Candidatos de su colección (sin jugar, ya ordenados por afinidad local):\n"
        f"{_format_games(items[:MAX_CANDIDATES], by_id)}\n\n"
        f"Consulta del usuario: {question}\n\n"
        "Recomienda los juegos de la lista que mejor encajen con la consulta y razona "
        "por qué en 1-2 frases por juego, conectando con su perfil. "
        "Si ninguno encaja de verdad, dilo claramente en vez de forzar una respuesta."
    )
    response = _request(
        model=model,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = _extract_text(response).strip()
    if not text:
        raise ChatError("Claude devolvió una respuesta vacía.")
    return text


def explain(
    items: list[dict], profile: Profile, games: list[dict], model: str = DEFAULT_MODEL
) -> dict:
    """Razones ricas para items ya puntuados. Devuelve {id: razón}. Un request."""
    by_id = {g.get("id"): g for g in games}
    prompt = (
        "Perfil del jugador (afinidades; peso positivo = le gusta, negativo = rechazo):\n"
        f"{_profile_summary(profile)}\n\n"
        "Recomendaciones ya calculadas por el scorer local:\n"
        f"{_format_games(items, by_id)}\n\n"
        "Escribe para cada recomendación una razón nueva en español: una sola frase, "
        "personal y concreta, que conecte el juego con el perfil del jugador. "
        "Sin fórmulas repetidas entre juegos."
    )
    response = _request(
        model=model,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": _EXPLAIN_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        data = json.loads(_extract_text(response))
        return {entry["id"]: entry["reason"] for entry in data["reasons"]}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ChatError("Claude devolvió un formato inesperado.") from exc
