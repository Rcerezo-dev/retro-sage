# Retro Sage 🔮

**El recomendador de juegos para [Retro Vault](https://github.com/Rcerezo-dev/Retro-gaming-companion).**

Retro Vault organiza tu colección de ROMs y registra cómo juegas (ratings,
sesiones, estados). Retro Sage consume esos datos, construye tu perfil de
jugador y le devuelve al Vault recomendaciones de tu propia colección:
*qué juego de los que ya tienes deberías jugar ahora*.

```
┌─────────────┐  GET /api/export-history   ┌─────────────┐
│ Retro Vault │ ─────────────────────────► │ Retro Sage  │
│ (127.0.0.1: │                            │ perfil +    │
│    7777)    │ ◄───────────────────────── │ scoring     │
└─────────────┘  POST /api/recommendations └─────────────┘
        └── panel "Recomendados" en el tab Juegos
```

**¿Por qué un repo aparte?** Retro Vault tiene una regla de diseño estricta:
*solo stdlib en runtime*. Un recomendador real necesita numpy, embeddings o la
Claude API — cosas que no pueden entrar allí. Retro Sage vive fuera y habla con
el Vault por su API pública, que ya existe (NLP-REC-5/6).

---

## Estado y roadmap

| Versión | Qué hace | Dependencias | Estado |
|---------|----------|--------------|--------|
| **v0.1** | Perfil desde tus señales (ratings ★, completados, sesiones) + scoring por afinidad de género/plataforma/época. CLI que imprime y/o empuja al Vault | **ninguna** (stdlib) | ✅ este scaffold |
| v0.2 | Embeddings locales (`all-MiniLM-L6-v2`) sobre descripciones scrapeadas → "juegos similares a X" y búsqueda semántica libre | `sentence-transformers`, `numpy` (extra `[embeddings]`) | ⬜ |
| v0.3 | Modo explicado con Claude API: recomendaciones con razonamiento en lenguaje natural ("como Zelda pero más corto") | `anthropic` (extra `[chat]`) | ⬜ |

Prerrequisitos en el lado Vault para exprimir v0.2+: scraping masivo hecho
(sin descripciones no hay semántica) y persistir `genres_list`/`players`
(migración pendiente allí — ver `docs/ideas/propuestas-recomendador-nlp.md`).

---

## Quickstart

```bash
pip install -e ".[dev]"

# Con Retro Vault corriendo en http://127.0.0.1:7777
retro-sage recommend                  # imprime el top 10 en terminal
retro-sage recommend --push           # además lo envía al panel "Recomendados"
retro-sage recommend --top 5 --vault http://127.0.0.1:7777

# Sin Vault corriendo (desde un export descargado):
retro-sage recommend --file export.json
```

Si aún no has puntuado ni completado nada en el Vault, no hay perfil que
construir: la CLI te lo dirá y te sugerirá marcar unos cuantos juegos primero
(mínimo 3 señales).

## Cómo funciona (v0.1)

1. **`vault_client`** descarga `GET /api/export-history`: toda tu biblioteca con
   `genre`, `year`, `platform`, `user_rating`, `play_status`, `play_count`, `tags`.
2. **`profile`** convierte tus señales en pesos: ★4-5 y `completed` suman,
   `dropped` resta, las sesiones (`play_count`) refuerzan. El resultado son tus
   afinidades por género, plataforma y década.
3. **`scorer`** puntúa los juegos **no jugados** contra ese perfil
   (60% género, 25% plataforma, 15% época) y genera una razón legible por ítem.
4. **`--push`** envía `POST /api/recommendations` con
   `{items: [{id, title, platform, score, reason}]}` — el panel del Vault se
   enciende sin tocar una línea de su código.

## Estructura

```
src/retro_sage/
  vault_client.py   # HTTP hacia Retro Vault (urllib, stdlib)
  profile.py        # señales → Profile (afinidades género/plataforma/década)
  scorer.py         # candidatos no jugados → items puntuados con razón
  cli.py            # entrypoint `retro-sage`
tests/              # pytest, fixtures sintéticas, sin red
```

## Desarrollo

```bash
ruff format --check src tests && ruff check src tests
pytest -q

# Hooks locales (una vez):
pre-commit install && pre-commit install --hook-type pre-push
```

CI (GitHub Actions) corre en cada PR y push a `develop`/`main`: `Lint (ruff)`
+ `Tests (pytest)` en Python 3.11 y 3.12 — el mismo pipeline que Retro Vault.

Mismas convenciones que Retro Vault: ramas por tarea → PR a `develop`,
`main` estable, formato ruff. Núcleo stdlib-only; el ML entra solo vía extras
opcionales (`pip install -e ".[embeddings]"`).

## Licencia

[MIT](LICENSE)
