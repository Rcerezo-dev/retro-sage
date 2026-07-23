"""Historial local de recomendaciones pasadas (v0.4, bucle de feedback).

Cada `recommend --push` añade una línea al log — la base para que Sage
compare en el futuro si lo recomendado acabó jugándose (Fase 4). Formato
JSONL append-only: nunca se reescribe el fichero completo, así que dos
`--push` seguidos no se pisan entre sí.

`evaluate_history()` cruza ese log contra un export actual y clasifica cada
recomendación pasada en acierto / fallo / pendiente — la señal heurística
que consume `retro-sage stats` (sin tocar el Vault: v. `docs/plan/Fase4.md`).
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

DEFAULT_THRESHOLD_DAYS = 14
_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def default_history_path() -> Path:
    """Fichero de historial: LOCALAPPDATA (Windows) o ~/.cache — mismo patrón que embeddings.py."""
    base = (
        os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    )
    return Path(base) / "retro-sage" / "history.jsonl"


def record_recommendations(items: list[dict], path: Path | None = None) -> None:
    """Añade una línea por item de `recommend` (id, title, platform, score, reason)."""
    path = Path(path) if path else default_history_path()
    now = datetime.datetime.now(datetime.UTC).strftime(_TS_FORMAT)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for item in items:
            entry = {
                "game_id": item.get("id"),
                "title": item.get("title"),
                "platform": item.get("platform"),
                "score": item.get("score"),
                "reason": item.get("reason"),
                "recommended_at": now,
            }
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_history(path: Path | None = None) -> list[dict]:
    """Lee el historial completo; [] si no existe todavía o está vacío."""
    path = Path(path) if path else default_history_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # línea corrupta puntual no debe tirar todo el historial
    return entries


def classify_outcome(
    entry: dict,
    games_by_id: dict,
    now: datetime.datetime,
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
) -> str | None:
    """'acierto' | 'fallo' | 'pendiente' para una entrada del historial.

    Acierto: el juego recomendado ya tiene partidas o puntuación en el export
    actual (recordar que solo se recomiendan candidatos sin jugar, así que
    cualquier cambio es posterior a la recomendación). Fallo: sigue intacto
    y ya pasaron `threshold_days` desde que se recomendó. Pendiente: sigue
    intacto pero aún es pronto para descartarlo. `None` si el juego ya no
    aparece en el export (nada con que compararlo).
    """
    game = games_by_id.get(entry.get("game_id"))
    if game is None:
        return None
    played = (game.get("play_count") or 0) > 0 or game.get("user_rating") is not None
    if played:
        return "acierto"
    recommended_at = datetime.datetime.strptime(entry["recommended_at"], _TS_FORMAT).replace(
        tzinfo=datetime.UTC
    )
    return "fallo" if (now - recommended_at).days >= threshold_days else "pendiente"


def evaluate_history(
    entries: list[dict],
    games: list[dict],
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
    now: datetime.datetime | None = None,
) -> list[dict]:
    """Cruza el historial con el export actual: cada entrada + su `outcome`.

    Entradas cuyo juego ya no existe en el export se omiten (nada que evaluar).
    """
    now = now or datetime.datetime.now(datetime.UTC)
    games_by_id = {g.get("id"): g for g in games}
    evaluated = []
    for entry in entries:
        outcome = classify_outcome(entry, games_by_id, now, threshold_days)
        if outcome is not None:
            evaluated.append({**entry, "outcome": outcome})
    return evaluated
