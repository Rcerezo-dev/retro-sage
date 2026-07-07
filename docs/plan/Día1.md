# Día 1 — Plan de trabajo: arrancar Fase 2 (v0.2 · Embeddings locales)

> Fases 0 y 1 cerradas (release `v0.1.0`). Lo que sigue es la Fase 2 del
> ROADMAP.md. Este documento baja esa fase a tareas concretas, en orden,
> con ficheros afectados y criterio de cierre por tarea.

## Estado de partida

- Núcleo stdlib-only funcionando: `vault_client → profile → scorer → cli`.
- Extra `[embeddings]` ya declarado en `pyproject.toml` (`sentence-transformers`, `numpy`) — no hay que tocar packaging para empezar.
- **Bloqueantes del lado Vault** (ver `docs/prompt-backlog-vault.md`):
  1. Scraping masivo de descripciones (>90% de juegos con descripción en el export).
  2. Migración `genres_list`/`players` persistidos y expuestos en `/api/export-history`.

Sin el bloqueante 1 no hay texto que vectorizar con datos reales, pero **todo
lo de este repo se puede construir y testear ya** con fixtures sintéticas
(los tests son sin red y sin descargar modelos, como siempre).

---

## Bloque A — Cimientos (no dependen del Vault)

### A1. Fixtures con descripciones y vectores precomputados

Ampliar `tests/conftest.py`: añadir campo `description` a los juegos de la
fixture espejo, y una fixture nueva con vectores pequeños precomputados
(listas de floats hardcodeadas, dimensión reducida tipo 8, no 384). CI nunca
descarga `all-MiniLM-L6-v2`.

- Ficheros: `tests/conftest.py`
- Hecho cuando: existe una fixture `games_with_descriptions` + vectores fake reutilizables por los tests de A2–A4.

### A2. Módulo `embeddings.py`

Nuevo `src/retro_sage/embeddings.py`, tres responsabilidades:

1. **Import perezoso** de `sentence_transformers`/`numpy` dentro de las
   funciones, con mensaje claro si falta el extra:
   `pip install "retro-sage[embeddings]"`. El núcleo sigue importable sin ML.
2. **Vectorización**: `embed_games(games)` toma los dicts crudos del export,
   vectoriza `description` (más título/géneros como contexto) con
   `all-MiniLM-L6-v2`.
3. **Caché en disco**: fichero en `~/.cache/retro-sage/` (o
   `platformdirs`-como pero stdlib: `os.environ` + fallback). Clave por id de
   juego + hash del texto; recomputar solo lo nuevo o lo que cambió.

- Ficheros: `src/retro_sage/embeddings.py` (nuevo), `tests/test_embeddings.py` (nuevo)
- Tests: coseno y caché se testean con los vectores fake de A1, inyectando el "modelo" como callable — sin red.
- Hecho cuando: segunda ejecución sobre la misma biblioteca no recomputa nada (verificable en test con un contador).

### A3. `retro-sage similar "Chrono Trigger"`

Subcomando nuevo en `cli.py`: busca el juego por título (matching laxo:
casefold, subcadena; si hay ambigüedad, listar opciones y salir con código 0),
top-N por similitud coseno contra el resto de la biblioteca. Reusar el patrón
de errores existente (`VaultError`, sin tracebacks) y los flags que ya hay
(`--file`, `--vault`, `--top`).

- Ficheros: `src/retro_sage/cli.py`, `src/retro_sage/embeddings.py`, `tests/test_cli.py`
- Hecho cuando: `retro-sage similar X --file export.json` devuelve top-N con score y razón en español; sin el extra instalado, mensaje claro y exit limpio.

### A4. `retro-sage search "rpg corto con buena historia"`

Igual que A3 pero la query libre se vectoriza y se compara contra todos los
juegos (no solo candidatos: buscar es sobre toda la biblioteca).

- Ficheros: `src/retro_sage/cli.py`, `tests/test_cli.py`
- Hecho cuando: consulta libre devuelve resultados razonables ordenados por coseno, mismos flags y misma degradación sin extra.

## Bloque B — Integración (mejor con datos reales del Vault)

### B1. Señal semántica en `recommend`

Mezclar en `scorer.py` la similitud media de cada candidato con los favoritos
del perfil (juegos con `signal_weight` alto). Nuevo término en el score con
peso propio, integrado en el mecanismo `--weights` existente en vez de
inventar otro flag. Si el extra no está instalado o no hay descripciones,
`recommend` funciona exactamente igual que en v0.1 (degradación silenciosa,
quizá una nota en `--verbose`/`profile`).

- Ficheros: `src/retro_sage/scorer.py`, `src/retro_sage/cli.py`, `tests/test_scorer.py`
- Hecho cuando: con el extra y descripciones, el ranking cambia de forma explicable; sin ellos, la salida es byte-a-byte la de v0.1.

### B2. Validación con biblioteca real

Cuando el Vault complete el scraping (bloqueante 1): correr `similar`,
`search` y `recommend` contra el export real y ajustar a ojo (¿la señal
semántica domina demasiado? ¿el caché escala con ~N juegos?).

- Depende de: backlog del Vault, tarea 1.
- Hecho cuando: criterio de la fase — "`similar` y `search` funcionan offline tras el primer run, y `recommend` mejora de forma visible".

## Bloque C — Coordinación (no es código de este repo)

- [ ] Pegar `docs/prompt-backlog-vault.md` en una sesión de Claude Code del
  Vault para dar de alta los dos bloqueantes en su backlog (si no está hecho ya).
- [ ] Cuando llegue la migración `genres_list`/`players` (bloqueante 2):
  actualizar `conftest.py` (fixture espejo) y `profile.py` para leer
  `genres_list` en lugar de parsear géneros al vuelo.

---

## Orden sugerido del día

1. A1 → A2 (la base: fixtures + módulo con caché) — el grueso del día.
2. A3 (`similar`) — primer subcomando visible.
3. C (pegar el prompt en el Vault) — 5 minutos, desbloquea B2 en paralelo.
4. A4 y B1 quedan para el día 2 si no da tiempo.

## Reglas que no se negocian (del ROADMAP/CLAUDE.md)

- Núcleo stdlib-only: `embeddings.py` solo importa ML dentro de sus funciones.
- Tests sin red y sin descargar modelos.
- Rama por tarea → PR a `develop` (Fase 2 es feature grande, no commits directos).
- Todo en español: CLI, razones, docstrings, commits.
