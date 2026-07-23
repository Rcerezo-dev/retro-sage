"""Historial local de recomendaciones pasadas (v0.4, bucle de feedback).

Cada `recommend --push` añade una línea al log — la base para que Sage
compare en el futuro si lo recomendado acabó jugándose (Fase 4). Formato
JSONL append-only: nunca se reescribe el fichero completo, así que dos
`--push` seguidos no se pisan entre sí.
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path


def default_history_path() -> Path:
    """Fichero de historial: LOCALAPPDATA (Windows) o ~/.cache — mismo patrón que embeddings.py."""
    base = (
        os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    )
    return Path(base) / "retro-sage" / "history.jsonl"


def record_recommendations(items: list[dict], path: Path | None = None) -> None:
    """Añade una línea por item de `recommend` (id, title, platform, score, reason)."""
    path = Path(path) if path else default_history_path()
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
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
