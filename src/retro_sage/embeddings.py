"""Embeddings locales (v0.2) — requiere el extra opcional [embeddings].

El núcleo sigue stdlib-only: sentence-transformers se importa de forma perezosa
dentro de `_load_encoder()`, y si falta el extra se lanza `EmbeddingsError` con
la instrucción de instalación (la CLI lo muestra sin traceback).

Los vectores se cachean en disco (JSON) con clave = hash del texto del juego:
en la segunda ejecución solo se vectoriza lo nuevo o lo que cambió.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingsError(RuntimeError):
    """Falta el extra [embeddings] o falló la vectorización."""


def default_cache_path() -> Path:
    """Fichero de caché de vectores: LOCALAPPDATA (Windows) o ~/.cache."""
    base = (
        os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    )
    return Path(base) / "retro-sage" / "embeddings.json"


def _load_encoder():
    """Carga el modelo real. Devuelve un callable list[str] → list[vector]."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingsError(
            'Este comando necesita el extra [embeddings]: pip install "retro-sage[embeddings]"'
        ) from exc
    model = SentenceTransformer(MODEL_NAME)
    return lambda texts: [list(map(float, vec)) for vec in model.encode(texts)]


def game_text(game: dict) -> str:
    """Texto que representa al juego: título + géneros + descripción."""
    parts = (game.get("title"), game.get("genre"), game.get("description"))
    return ". ".join(str(p).strip() for p in parts if p and str(p).strip())


def _text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embed_games(games: list[dict], encoder=None, cache_path: Path | None = None) -> dict:
    """id de juego → vector. Solo vectoriza textos que no están en la caché.

    `encoder` es inyectable para tests (sin red ni modelo); por defecto carga
    el modelo real bajo demanda — si nada falta en caché, ni siquiera importa ML.
    """
    cache_path = Path(cache_path) if cache_path else default_cache_path()
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, json.JSONDecodeError):
        cache = {}

    texts: dict = {}
    for game in games:
        gid, text = game.get("id"), game_text(game)
        if gid is not None and text:
            texts[gid] = text
    keys = {gid: _text_key(text) for gid, text in texts.items()}

    pending = [(gid, texts[gid]) for gid, key in keys.items() if key not in cache]
    if pending:
        if encoder is None:
            encoder = _load_encoder()
        vectors = encoder([text for _, text in pending])
        for (gid, _), vec in zip(pending, vectors):
            cache[keys[gid]] = list(map(float, vec))
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")

    return {gid: cache[key] for gid, key in keys.items()}


def cosine(a: list[float], b: list[float]) -> float:
    """Similitud coseno en [-1, 1]; 0.0 si algún vector es nulo."""
    # ponytail: python puro basta para bibliotecas de miles de juegos;
    # pasar a numpy solo si el ranking se nota lento con datos reales.
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0
