"""Cliente HTTP hacia Retro Vault — stdlib only.

Contrato (definido en Retro Vault, `web/handlers/play_history.py`):
- GET  /api/export-history   → {exported_at, total, games: [...]}
- POST /api/recommendations  → body {items: [{id, title, platform, score, reason}]}
  (el Vault guarda un máximo de 50 items en memoria)

Asume el caso por defecto: Vault en loopback sin PIN. Si el Vault tiene PIN
activo, exporta manualmente el JSON desde la UI y usa `--file`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_VAULT_URL = "http://127.0.0.1:7777"
MAX_ITEMS = 50  # cap del lado Vault; no tiene sentido enviar más


class VaultError(RuntimeError):
    """Fallo de comunicación o respuesta inesperada del Vault."""


def fetch_library(vault_url: str = DEFAULT_VAULT_URL, timeout: float = 30.0) -> dict:
    """Descarga la biblioteca completa (jugados y no jugados) del Vault."""
    url = vault_url.rstrip("/") + "/api/export-history"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise VaultError(
            f"No se pudo obtener la biblioteca de {url}: {exc}. "
            "¿Está Retro Vault corriendo? (rommgr serve)"
        ) from exc
    if not isinstance(payload, dict) or "games" not in payload:
        raise VaultError(f"Respuesta inesperada de {url}: falta la clave 'games'.")
    return payload


def load_library_file(path: str) -> dict:
    """Carga un export descargado a mano (modo offline / Vault con PIN)."""
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    if "games" not in payload:
        raise VaultError(f"'{path}' no parece un export de Retro Vault (falta 'games').")
    return payload


def push_recommendations(
    items: list[dict], vault_url: str = DEFAULT_VAULT_URL, timeout: float = 30.0
) -> int:
    """Envía las recomendaciones al Vault. Devuelve cuántas almacenó."""
    url = vault_url.rstrip("/") + "/api/recommendations"
    body = json.dumps({"items": items[:MAX_ITEMS]}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            answer = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise VaultError(f"No se pudieron enviar las recomendaciones a {url}: {exc}") from exc
    if not answer.get("ok"):
        raise VaultError(f"El Vault rechazó el envío: {answer}")
    return int(answer.get("stored", 0))
