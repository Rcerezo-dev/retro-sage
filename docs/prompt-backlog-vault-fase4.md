# Prompt para el backlog del Vault — SAGE-3 (Sage v0.4, bucle de feedback)

> Pegar este documento en una sesión de Claude Code del repo del Vault
> (`Retro_gaming_app`). Objetivo: pasar la entrada SAGE-3 de
> `Tareas/backlog.md` (hoy "no implementar todavía — se negocia cuando Sage
> llegue a v0.4") a un contrato concreto, e implementarlo si el alcance
> parece razonable para una sesión.

## Contexto

Retro Sage (repo aparte, `retro-sage`) entra en su Fase 4: cerrar el círculo
de si sus recomendaciones aciertan. Hoy puede aproximarlo sin tocar el Vault
— guarda localmente qué recomendó y compara contra `GET /api/export-history`
en ejecuciones posteriores (¿el juego pasó de `play_count == 0` a jugado?).

Esa señal es ruidosa: no distingue "el usuario vio la recomendación en el
panel y la ignoró" (fallo real) de "nunca abrió el panel" (no debería contar
en contra) o "la vio y la jugó por eso" (acierto fuerte, causal). Para esa
señal fina hace falta que el propio Vault registre impresión y clic, porque
solo el panel sabe qué se renderizó y qué se clicó.

Esto es exactamente SAGE-3 (`Tareas/backlog.md` línea 138). Contrato
propuesto abajo, sobre el patrón ya existente en
`src/rom_manager/web/handlers/play_history.py`.

## Estado actual (punto de partida)

- `POST /api/recommendations` recibe items de Sage y los guarda en
  `_recommendations`, un dict **en memoria** que se reemplaza entero en cada
  push (sin histórico).
- `GET /api/recommendations` sirve ese único batch en memoria, enriquecido
  con datos de `games`/`game_metadata`.
- Nada persiste entre pushes ni entre reinicios del servidor.

## Contrato propuesto

### 1. Persistir cada push (no solo el último)

Tabla nueva `recommendation_log` (misma BD que `games`):

| Columna | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK autoincrement | |
| `game_id` | INTEGER, nullable | FK lógica a `games.id` |
| `title` | TEXT | fallback si `game_id` es null (igual que hoy en el POST) |
| `platform` | TEXT, nullable | |
| `score` | REAL, nullable | |
| `reason` | TEXT, nullable | |
| `pushed_at` | TEXT (ISO 8601 UTC) | cuándo Sage hizo el POST |
| `shown_at` | TEXT (ISO 8601 UTC), nullable | primera vez que el panel pidió este batch |
| `clicked_at` | TEXT (ISO 8601 UTC), nullable | cuándo el usuario clicó la tarjeta |

`POST /api/recommendations` (sin cambiar su contrato externo — sigue
aceptando `{"items": [...]}` y cap de 50): además de reemplazar
`_recommendations` como hoy, inserta una fila por item con `pushed_at = now()`.

`GET /api/recommendations` (sin cambiar su respuesta): si algún item del
batch actual tiene `shown_at` nulo en la tabla, lo actualiza a `now()` en esa
misma llamada — "mostrado" = el panel efectivamente lo pidió y renderizó.

### 2. Endpoint nuevo — registrar clic

```
POST /api/recommendations/click
Body: {"game_id": int}
```

Actualiza `clicked_at = now()` en la fila más reciente de
`recommendation_log` para ese `game_id` que aún tenga `clicked_at IS NULL`.
Respuesta `{"ok": true}`, o `{"error": "..."}` si no hay fila que marcar
(mismo estilo de errores que el resto de `play_history.py`).

Requiere un cambio mínimo de frontend: la tarjeta de recomendación en el
panel dispara este POST al clicarse (fire-and-forget, no bloquea la
navegación).

### 3. Endpoint nuevo — exportar el historial para Sage

```
GET /api/recommendations/feedback?since=<ISO 8601, opcional>
```

Devuelve el log completo (o desde `since` si se pasa) para que Sage lo
consuma y cruce con su propio historial local:

```json
{
  "items": [
    {
      "game_id": 123,
      "title": "Chrono Trigger",
      "platform": "snes",
      "score": 0.82,
      "reason": "...",
      "pushed_at": "2026-07-20T10:00:00Z",
      "shown_at": "2026-07-20T10:05:00Z",
      "clicked_at": null
    }
  ],
  "total": 1
}
```

Sin `since`, cap razonable (ej. últimos 500 registros) para no mandar toda la
tabla si crece mucho — mismo criterio que el cap de 50 en `POST
/api/recommendations`.

## Fuera de alcance (que Sage no necesita del Vault)

- Nada de calcular tasas de acierto en el Vault — eso es trabajo de
  `retro-sage stats` (Fase 4, Bloque A, no depende de esto).
- Nada de UI nueva más allá del `POST` de clic en la tarjeta existente.

## Hecho cuando

- `recommendation_log` persiste cada push con `pushed_at`.
- `shown_at` se rellena solo al servir el batch por `GET
  /api/recommendations`.
- Clicar una tarjeta en el panel marca `clicked_at` vía el endpoint nuevo.
- `GET /api/recommendations/feedback` devuelve el histórico con los tres
  timestamps, consumible sin credenciales extra (mismo esquema de auth/PIN
  que el resto de `/api/*`).
- Actualizar `Tareas/backlog.md`: SAGE-3 pasa de ⬜ a 🟡/✅ según lo que se
  implemente en la sesión, con nota de qué falta si se hace parcial.
