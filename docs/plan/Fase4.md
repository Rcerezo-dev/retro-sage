# Fase 4 — Plan de trabajo: bucle de feedback (v0.4)

> Fases 0-3 cerradas (release `v0.1.0`, embeddings v0.2, chat v0.3 — PR #3
> mergeado a `develop`). Lo que sigue es la Fase 4 del ROADMAP.md (líneas
> 66-77). Este documento baja esa fase a tareas concretas, en orden, con
> ficheros afectados y criterio de cierre por tarea.

## Estado de partida

- Núcleo funcionando: `vault_client → profile → scorer → cli`, más
  `embeddings.py` (v0.2) y `chat.py` (v0.3).
- Las 3 tareas de la fase (ROADMAP): consumir señales posteriores al push,
  `retro-sage stats`, ajustar pesos con ese histórico.
- **Matiz importante:** la tarea 1 NO depende del Vault para empezar. Sage ya
  sabe qué recomendó (lo generó él mismo) — solo necesita guardarlo localmente
  y compararlo contra exports posteriores (`GET /api/export-history`, que ya
  expone `play_status`/`user_rating`/`play_count`). Eso basta para una señal
  heurística razonable: "¿el juego que recomendé cambió de estado después?".
- Lo que sí depende del Vault es la señal **fina**: distinguir "se mostró en
  el panel y se ignoró" (fallo real) de "nunca se mostró" (no cuenta) o "se
  clicó" (acierto fuerte). Eso es SAGE-3 del backlog del Vault, hoy marcado
  "no implementar todavía — se negocia cuando Sage llegue a v0.4". Ese
  momento es ahora: contrato redactado en
  `docs/prompt-backlog-vault-fase4.md`, listo para pegar en una sesión del
  Vault.

---

## Bloque A — Cimientos (no dependen del Vault, con fixtures ya)

### A1. Historial local de recomendaciones pasadas

Cada vez que `recommend --push` (o `ask`) entrega una lista, guardarla en un
log local propio de Sage — stdlib puro (`json` + `pathlib`), mismo patrón de
caché que `embeddings.py` (`~/.cache/retro-sage/`, o `RETRO_SAGE_HOME` si ya
existe una convención). Una entrada por recomendación: `game_id`, `title`,
`platform`, `score`, `reason`, `recommended_at` (ISO).

- Ficheros: `src/retro_sage/history.py` (nuevo), `src/retro_sage/cli.py`
  (hook en el flujo de `--push`), `tests/test_history.py` (nuevo)
- Tests: con `tmp_path` como home del log, sin red.
- Hecho cuando: cada `recommend --push` añade N entradas al historial local;
  ejecuciones repetidas no corrompen el fichero (append, no overwrite).

### A2. Cruce historial vs export → acierto / fallo / pendiente

Función pura: dado el historial local + el export actual (mismo shape que
`tests/conftest.py`), clasifica cada recomendación pasada:

- **Acierto**: el juego tenía `play_count == 0` y sin `user_rating` al
  recomendarse, y ahora tiene `play_count > 0` o `user_rating` no nulo.
- **Fallo**: han pasado ≥N días (umbral configurable, ej. 14) desde
  `recommended_at` y el juego sigue exactamente igual.
- **Pendiente**: recomendado hace menos de N días, sin cambios aún — no
  cuenta ni a favor ni en contra.

- Ficheros: `src/retro_sage/history.py`, `tests/test_history.py`
- Hecho cuando: tests cubren los 3 casos con fixtures sintéticas (una
  recomendación vieja que luego se jugó, una vieja que sigue intacta, una
  reciente).

### A3. `retro-sage stats`

Subcomando nuevo: carga historial local, cruza con export (`--file`/`--vault`,
mismos flags que el resto de la CLI), imprime en español tasa de acierto
global y desglose por género/plataforma. Reusa el patrón de errores existente
(`VaultError`, sin tracebacks); sin historial aún, mensaje claro y exit 0
(mismo criterio que "menos de 3 señales" en `recommend`).

- Ficheros: `src/retro_sage/cli.py`, `tests/test_cli.py`
- Hecho cuando: `retro-sage stats --file export.json` imprime
  aciertos/fallos/pendientes y % de acierto; sin historial, no rompe y lo dice.

### A4. Ajuste heurístico de pesos con el histórico

Heurística simple, **nada de ML entrenado** (regla del ROADMAP): antes de
puntuar candidatos en `scorer.py`, atenuar/reforzar la afinidad de un
género/plataforma en el `Profile` según su ratio de aciertos acumulado en
`stats` — un factor fijo y acotado (ej. ±15%), no un peso libre. Si no hay
histórico suficiente (mismo mínimo que arranca `Profile`, ej. <3 recomendaciones
evaluadas), no se toca nada — se comporta como hoy.

- Ficheros: `src/retro_sage/profile.py` (o `src/retro_sage/history.py` si
  queda más natural ahí — decidir al implementar), `tests/test_profile.py`
  o `tests/test_history.py`
- Hecho cuando: un test demuestra que un género con fallos repetidos baja su
  afinidad en el `Profile` resultante y uno con aciertos la sube, siempre
  dentro del límite acotado; sin histórico, `Profile` sale idéntico a hoy.

## Bloque B — Señal fina (depende del Vault: SAGE-3)

### B1. Consumir shown/clicked cuando el Vault lo exponga

Cuando el Vault implemente el endpoint negociado en
`docs/prompt-backlog-vault-fase4.md`: añadir a `vault_client.py` un método
para leer ese historial (`GET /api/recommendations/feedback`) y enriquecer la
clasificación de A2 — un "fallo" solo cuenta si `shown_at` no es nulo (se
mostró de verdad), y un `clicked_at` no nulo sube de peso el acierto en A4.

- Depende de: backlog Vault, SAGE-3.
- Ficheros: `src/retro_sage/vault_client.py`, `src/retro_sage/history.py`
- Hecho cuando: con el endpoint real disponible, `stats` deja de contar como
  fallo las recomendaciones que nunca llegaron a mostrarse en el panel.

## Bloque C — Coordinación (no es código de este repo)

- [ ] Pegar `docs/prompt-backlog-vault-fase4.md` en una sesión de Claude Code
  del Vault para pasar SAGE-3 de "no implementar todavía" a un contrato
  concreto en su backlog.

---

## Orden sugerido

1. A1 → A2 (historial + cruce) — la base.
2. A3 (`stats`) — primer resultado visible, funciona ya con fixtures.
3. C (pegar el prompt en el Vault) — 5 minutos, desbloquea B1 en paralelo.
4. A4 (ajuste de pesos) al final del bloque A: necesita A2/A3 ya probados.
5. B1 cuando el Vault entregue SAGE-3 — no bloquea el resto de la fase.

## Reglas que no se negocian (del ROADMAP/CLAUDE.md)

- Núcleo stdlib-only: `history.py` solo usa `json`/`pathlib`/`datetime`.
- Ajuste de pesos = heurística simple y acotada, no ML entrenado.
- Tests sin red y sin depender de un Vault corriendo.
- Rama por tarea → PR a `develop` (Fase 4 es feature grande, no commits
  directos).
- Todo en español: CLI, razones, docstrings, commits.
