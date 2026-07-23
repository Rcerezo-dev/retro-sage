"""Modo explicado con IA (v0.3): Claude API o Gemini (free tier).

Dos backends detrás del mismo `_complete()`:
- **Gemini** si hay `GEMINI_API_KEY` en el entorno (free tier de Google AI
  Studio): API REST con urllib puro, sin dependencias — ni siquiera el extra.
- **Claude** en caso contrario: extra opcional [chat] (`anthropic`, import
  perezoso); el SDK resuelve ANTHROPIC_API_KEY o un perfil de `ant auth login`.

Control de coste: un solo request por invocación, con los candidatos ya
filtrados y puntuados por el scorer local. Sin backend disponible se lanza
`ChatError`: `ask` muestra el mensaje y sale limpio, `recommend --explain`
degrada a las razones del scorer (modo v0.1).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .profile import Profile

DEFAULT_MODELS = {"claude": "claude-opus-4-8", "gemini": "gemini-2.5-flash"}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
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
    """No hay backend de IA disponible, o la llamada falló."""


def _provider() -> str:
    """'gemini' si hay GEMINI_API_KEY (free tier); 'claude' en caso contrario."""
    return "gemini" if os.environ.get("GEMINI_API_KEY") else "claude"


def _complete(prompt: str, model: str | None, json_schema: dict | None = None) -> str:
    """Un único request al backend activo. Devuelve el texto de la respuesta."""
    if _provider() == "gemini":
        return _gemini_complete(prompt, model or DEFAULT_MODELS["gemini"], json_schema)
    return _claude_complete(prompt, model or DEFAULT_MODELS["claude"], json_schema)


# --- Backend Claude (extra [chat]) -------------------------------------------


def _client():
    """Cliente de Anthropic, importado y construido bajo demanda."""
    try:
        import anthropic
    except ImportError as exc:
        raise ChatError(
            "Sin backend de IA: exporta GEMINI_API_KEY (free tier, "
            "https://aistudio.google.com) o instala el extra [chat] "
            '(pip install "retro-sage[chat]") con ANTHROPIC_API_KEY.'
        ) from exc
    try:
        # Sin api_key explícita: el SDK resuelve ANTHROPIC_API_KEY o el perfil
        # de `ant auth login` por su cuenta.
        return anthropic.Anthropic()
    except Exception as exc:
        raise ChatError(
            "No hay credenciales: exporta ANTHROPIC_API_KEY (o `ant auth login`), "
            "o usa GEMINI_API_KEY (free tier, sin extra)."
        ) from exc


def _claude_complete(prompt: str, model: str, json_schema: dict | None) -> str:
    kwargs: dict = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }
    if json_schema:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": json_schema}}
    else:
        kwargs["thinking"] = {"type": "adaptive"}
    return _extract_text(_request(**kwargs))


def _request(**kwargs):
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


# --- Backend Gemini (free tier, urllib puro) ----------------------------------


def _gemini_complete(prompt: str, model: str, json_schema: dict | None) -> str:
    body: dict = {
        "system_instruction": {"parts": [{"text": _SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    if json_schema:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseJsonSchema": json_schema,
        }
    payload = _post_json(
        GEMINI_URL.format(model=model),
        body,
        {
            "Content-Type": "application/json",
            "x-goog-api-key": os.environ["GEMINI_API_KEY"],
        },
    )
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        return "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        candidates = payload.get("candidates") or [{}]
        reason = (
            payload.get("promptFeedback", {}).get("blockReason")
            or candidates[0].get("finishReason")
            or "respuesta vacía"
        )
        raise ChatError(f"Gemini no devolvió respuesta ({reason}).") from exc


def _post_json(url: str, body: dict, headers: dict) -> dict:
    """POST JSON con urllib; separado para poder fakearlo en los tests."""
    request = urllib.request.Request(  # noqa: S310
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise ChatError(f"La llamada a Gemini falló ({exc.code}): {detail}") from exc
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise ChatError(f"La llamada a Gemini falló: {exc}") from exc


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
    model: str | None = None,
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
    text = _complete(prompt, model).strip()
    if not text:
        raise ChatError("El modelo devolvió una respuesta vacía.")
    return text


def explain(
    items: list[dict], profile: Profile, games: list[dict], model: str | None = None
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
    try:
        data = json.loads(_complete(prompt, model, json_schema=_EXPLAIN_SCHEMA))
        return {entry["id"]: entry["reason"] for entry in data["reasons"]}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ChatError("El modelo devolvió un formato inesperado.") from exc
