# Roadmap — Retro Sage 🔮

De principio a fin: qué se construye, en qué orden y cuándo se considera hecho.
El detalle de cada versión vive aquí; el README solo mantiene la tabla resumen.

```
v0.1 ──► v0.1.x ──► v0.2 ──► v0.3 ──► v0.4 ──► v1.0
scaffold  robustez  embeddings  Claude   feedback  estable
   ✅        ✅         ⬜         ⬜        ⬜        ⬜
```

---

## ✅ Fase 0 — v0.1 · Scaffold stdlib-only (hecho)

Perfil de jugador + scoring por afinidad, sin dependencias.

- [x] `vault_client`: `GET /api/export-history` y `POST /api/recommendations` (urllib)
- [x] `profile`: señales (★, completados, dropped, sesiones) → afinidades género/plataforma/década
- [x] `scorer`: candidatos no jugados → top-N con razón legible (60/25/15)
- [x] CLI `retro-sage recommend` con `--push`, `--top`, `--vault`, `--file`
- [x] Tests sin red, CI (ruff + pytest, py3.11/3.12), pre-commit — espejo de Retro Vault

## ✅ Fase 1 — v0.1.x · Robustez y señales extra (hecho)

Endurecer lo que ya existe antes de añadir ML. Sin dependencias nuevas.

- [x] Usar `tags` del export como señal de afinidad adicional (entran al espacio de géneros)
- [x] Manejo de errores del Vault: timeouts, respuestas parciales, mensajes claros en CLI
- [x] `retro-sage profile`: subcomando que imprime tu perfil (debug y transparencia)
- [x] Pesos del scoring configurables por flag (`--weights 60,25,15`) para experimentar
- [x] Primera release etiquetada ([`v0.1.0`](https://github.com/Rcerezo-dev/retro-sage/releases/tag/v0.1.0)) desde `main`

**Hecho cuando:** la CLI nunca muere con traceback ante un Vault caído o un export raro.

## ⬜ Fase 2 — v0.2 · Embeddings locales

"Juegos similares a X" y búsqueda semántica libre. Extra `[embeddings]`
(`sentence-transformers`, `numpy`) — el núcleo sigue stdlib-only.

**Prerrequisitos (lado Vault, bloqueantes):**
- [ ] Scraping masivo de descripciones hecho (sin texto no hay semántica)
- [ ] Migración `genres_list`/`players` persistidos (ver `docs/ideas/propuestas-recomendador-nlp.md` en el Vault)

**Este repo:**
- [x] Módulo `embeddings.py`: vectoriza descripciones con `all-MiniLM-L6-v2`, caché en disco (recomputar solo lo nuevo)
- [x] `retro-sage similar "Chrono Trigger"` → top-N por coseno
- [x] `retro-sage search "rpg corto con buena historia"` → búsqueda semántica
- [x] Mezclar señal semántica en `recommend` (afinidad + similitud a tus favoritos)
- [x] Tests con vectores precomputados en fixtures (sin descargar el modelo en CI)

**Hecho cuando:** `similar` y `search` funcionan offline tras el primer run, y `recommend` mejora de forma visible con la señal semántica.

## ⬜ Fase 3 — v0.3 · Modo explicado con Claude API

Recomendaciones con razonamiento en lenguaje natural. Extra `[chat]` (`anthropic`).

- [ ] `retro-sage ask "como Zelda pero más corto"` → Claude recibe perfil + candidatos y razona la respuesta
- [ ] `recommend --explain`: razones ricas ("lo dejaste a medias en 2024, y es del mismo estudio que…") en vez de la plantilla del scorer
- [ ] Degradación limpia: sin `ANTHROPIC_API_KEY`, mensaje claro y fallback al modo v0.1
- [ ] Control de coste: un solo request por invocación, candidatos ya filtrados por el scorer local

**Hecho cuando:** `ask` responde bien a consultas libres y todo sigue funcionando igual sin API key.

## ⬜ Fase 4 — v0.4 · Bucle de feedback

Cerrar el círculo: saber si las recomendaciones acertaron.

- [ ] Consumir del export las señales posteriores al push (¿jugaste/puntuaste lo recomendado?)
- [ ] `retro-sage stats`: tasa de acierto de recomendaciones pasadas
- [ ] Ajustar pesos del perfil con ese histórico (heurística simple, no ML entrenado)

Puede requerir que el Vault registre qué recomendaciones se mostraron/clicaron —
negociar ese endpoint cuando llegue el momento.

**Hecho cuando:** `stats` demuestra con números si Sage acierta más que el azar.

## ⬜ Fase 5 — v1.0 · Estable

- [ ] Contrato de API con el Vault versionado y documentado (qué campos del export son estables)
- [ ] Publicación en PyPI (`pip install retro-sage`)
- [ ] README/docs al día: quickstart por cada modo (stdlib, embeddings, chat)
- [ ] Congelar: a partir de aquí, semver de verdad

---

## Reglas transversales (todas las fases)

- Núcleo stdlib-only; el ML solo entra vía extras opcionales.
- Ramas por tarea → PR a `develop`; `main` estable. CI verde obligatoria.
- Tests sin red y sin descargar modelos.
- Cada fase se cierra con su criterio de "hecho cuando" — no por fecha.
