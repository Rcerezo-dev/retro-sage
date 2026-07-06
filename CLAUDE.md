# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

Retro Sage es el recomendador de juegos companion de **Retro Vault**. Consume la
biblioteca del usuario vía la API del Vault, construye un perfil de jugador y
devuelve recomendaciones de su propia colección. Vive en un repo aparte porque
el Vault es stdlib-only estricto y el ML (v0.2+) no puede entrar allí.

**Regla central: el núcleo v0.1 es stdlib-only.** Nada de dependencias en
`[project] dependencies`. El ML entra solo vía extras opcionales
(`[embeddings]`, `[chat]`) según avance el ROADMAP.md.

## Comandos

```bash
pip install -e ".[dev]"            # setup

ruff format src tests              # formatear
ruff check src tests               # lint (mismo gate que CI: format --check + check)
pytest -q                          # todos los tests
pytest tests/test_scorer.py -q     # un fichero
pytest tests/test_scorer.py::test_nombre -q   # un test

retro-sage recommend --file export.json       # probar la CLI sin Vault corriendo
```

CI corre `ruff format --check`, `ruff check` y `pytest` en Python 3.11 y 3.12.
Los tests son sin red: fixtures sintéticas en `tests/conftest.py` con el mismo
shape que el export del Vault.

## Arquitectura

Pipeline lineal, un módulo por etapa (`src/retro_sage/`):

```
vault_client → profile → scorer → cli
```

- **`vault_client.py`** — HTTP con urllib. `GET /api/export-history` (biblioteca
  completa) y `POST /api/recommendations` (máx. 50 items). Todo error de red o
  shape se convierte en `VaultError`, que la CLI captura y muestra sin traceback.
- **`profile.py`** — señales por juego (`user_rating` ★1-5, `play_status`,
  `play_count`) → `signal_weight()` en [-1.4, ~2.0] → agregado en `Profile`:
  afinidades ponderadas por género, plataforma y década. Pesos negativos =
  rechazo explícito (★1, dropped).
- **`scorer.py`** — solo puntúa **candidatos** (juegos sin señal alguna:
  `is_candidate`). Score = 0.60·género + 0.25·plataforma + 0.15·década, con
  penalización por géneros rechazados. Genera la `reason` legible en español
  que muestra el panel del Vault.
- **`cli.py`** — `retro-sage recommend`; exige mínimo 3 señales para construir
  perfil, si no lo dice y sale con código 0.

Los juegos circulan como dicts crudos del export (sin modelos intermedios);
el único dataclass es `Profile`.

## Contrato con Retro Vault

El shape de datos lo define el Vault, no este repo. Clon local:
`C:\Users\rammu\Documents\projects\Retro_gaming_app` — el contrato está en
`src/rom_manager/web/handlers/play_history.py` de ese repo. Si un campo del
export cambia, ajustar aquí `conftest.py` (fixture espejo) y los módulos que lo
lean. El Vault corre por defecto en `http://127.0.0.1:7777` sin PIN; con PIN
activo solo funciona el modo `--file`.

## Convenciones

- Todo en español: docstrings, commits (estilo conventional: `feat:`, `docs:`,
  `ci:`...), mensajes de la CLI y las `reason` de las recomendaciones.
- Cambios pequeños directos a `develop`; rama + PR solo para features grandes.
  `main` es estable.
- ROADMAP.md manda: cada fase tiene criterio de "hecho cuando". No adelantar
  dependencias de fases futuras.
