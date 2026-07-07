"""CLI de Retro Sage.

Uso:
    retro-sage recommend [--vault URL | --file export.json] [--top N] [--push] [--weights G,P,D[,S]]
    retro-sage profile   [--vault URL | --file export.json]
    retro-sage similar "Chrono Trigger" [--top N]     (requiere el extra [embeddings])
    retro-sage search "rpg corto con buena historia"  (requiere el extra [embeddings])
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, embeddings
from .profile import Profile, build_profile
from .scorer import DEFAULT_WEIGHTS, recommend
from .vault_client import (
    DEFAULT_VAULT_URL,
    VaultError,
    fetch_library,
    load_library_file,
    push_recommendations,
)

MIN_SIGNALS = 3


def _load_games(args: argparse.Namespace) -> list[dict]:
    payload = load_library_file(args.file) if args.file else fetch_library(args.vault)
    return payload["games"]


def _parse_weights(text: str) -> tuple[float, float, float, float]:
    """'60,25,15' o '60,25,15,30' — el 4º es la señal semántica (extra [embeddings]).

    Devuelve los pesos crudos; el scorer los normaliza según haya o no vectores.
    """
    try:
        parts = tuple(float(tok) for tok in text.split(","))
    except ValueError:
        parts = ()
    if len(parts) == 3:
        parts = (*parts, DEFAULT_WEIGHTS[3])
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            "formato: GÉNERO,PLATAFORMA,DÉCADA[,SEMÁNTICA] — p. ej. --weights 60,25,15,30"
        )
    if min(parts) < 0 or sum(parts[:3]) <= 0:
        raise argparse.ArgumentTypeError(
            "los pesos deben ser ≥ 0 y los tres primeros sumar más de 0"
        )
    return parts


def _print_affinities(label: str, prefs: dict, top: int = 8) -> None:
    if not prefs:
        return
    print(f"\n{label}:")
    ranked = sorted(prefs.items(), key=lambda kv: kv[1], reverse=True)[:top]
    for key, weight in ranked:
        print(f"  {weight:+.2f}  {key}")


def _cmd_recommend(args: argparse.Namespace) -> int:
    games = _load_games(args)
    profile = build_profile(games)
    if not profile.is_usable(MIN_SIGNALS):
        print(
            f"Aún no hay perfil que construir ({profile.signals} señales; mínimo {MIN_SIGNALS}).\n"
            "Marca ratings ★, completa juegos o juega unas sesiones en Retro Vault y vuelve."
        )
        return 0

    similarity = None
    try:
        vectors = embeddings.embed_games(games)
        similarity = embeddings.similarity_to_favorites(games, vectors) or None
    except embeddings.EmbeddingsError:
        pass  # sin extra [embeddings]: scoring v0.1, misma salida de siempre

    items = recommend(games, profile, top=args.top, weights=args.weights, similarity=similarity)
    if not items:
        print("Perfil construido, pero ningún juego sin jugar coincide con tus gustos todavía.")
        return 0

    semantic_note = " · señal semántica activa" if similarity else ""
    print(f"Perfil: {profile.signals} señales · biblioteca: {len(games)} juegos{semantic_note}\n")
    width = max(len(item["title"] or "?") for item in items)
    for rank, item in enumerate(items, start=1):
        title = (item["title"] or "?").ljust(width)
        print(f"{rank:>2}. {title}  [{item['platform']}]  {item['score']:.2f}  — {item['reason']}")

    if args.push:
        stored = push_recommendations(items, args.vault)
        print(f"\n✓ {stored} recomendaciones enviadas al panel 'Recomendados' de Retro Vault.")
    return 0


def _cmd_profile(args: argparse.Namespace) -> int:
    games = _load_games(args)
    profile: Profile = build_profile(games)
    if profile.signals == 0:
        print("Sin señales todavía: puntúa, completa o juega algo en Retro Vault.")
        return 0

    print(f"Perfil: {profile.signals} señales · biblioteca: {len(games)} juegos")
    _print_affinities("Géneros y tags", profile.genres)
    _print_affinities("Plataformas", profile.platforms)
    _print_affinities("Décadas", {f"{d}s": w for d, w in profile.decades.items()})
    return 0


def _find_game(games: list[dict], query: str) -> tuple[dict | None, list[dict]]:
    """Busca por título: exacto (casefold) primero, subcadena después.

    Devuelve (juego, []) si hay uno claro, (None, coincidencias) si es ambiguo.
    """
    q = query.strip().casefold()
    exact = [g for g in games if (g.get("title") or "").casefold() == q]
    if exact:
        return exact[0], []
    matches = [g for g in games if q in (g.get("title") or "").casefold()]
    if len(matches) == 1:
        return matches[0], []
    return None, matches


def _print_ranked(ranked: list[tuple[float, dict]], reason: str) -> None:
    width = max(len(game.get("title") or "?") for _, game in ranked)
    for rank, (score, game) in enumerate(ranked, start=1):
        title = (game.get("title") or "?").ljust(width)
        print(f"{rank:>2}. {title}  [{game.get('platform')}]  {score:.2f}  — {reason}")


def _cmd_similar(args: argparse.Namespace) -> int:
    games = _load_games(args)
    target, matches = _find_game(games, args.title)
    if target is None:
        if matches:
            print(f"Varios juegos coinciden con «{args.title}»; sé más específico:")
            for game in matches[:10]:
                print(f"  - {game.get('title')}  [{game.get('platform')}]")
            return 0
        print(f"✗ Ningún juego de tu biblioteca coincide con «{args.title}».", file=sys.stderr)
        return 1

    vectors = embeddings.embed_games(games)
    target_vec = vectors.get(target.get("id"))
    if target_vec is None:
        print(f"✗ «{target.get('title')}» no tiene texto que vectorizar.", file=sys.stderr)
        return 1
    by_id = {g.get("id"): g for g in games}
    ranked = sorted(
        (
            (embeddings.cosine(target_vec, vec), by_id[gid])
            for gid, vec in vectors.items()
            if gid != target.get("id")
        ),
        key=lambda pair: pair[0],
        reverse=True,
    )
    ranked = [pair for pair in ranked if pair[0] > 0][: args.top]
    if not ranked:
        print(f"Nada en tu biblioteca se parece a «{target.get('title')}».")
        return 0
    print(f"Parecidos a «{target.get('title')}» en tu biblioteca:\n")
    _print_ranked(ranked, f"similar a {target.get('title')}")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    games = _load_games(args)
    encoder = embeddings._load_encoder()
    query_vec = encoder([args.query])[0]
    vectors = embeddings.embed_games(games, encoder=encoder)
    by_id = {g.get("id"): g for g in games}
    ranked = sorted(
        ((embeddings.cosine(query_vec, vec), by_id[gid]) for gid, vec in vectors.items()),
        key=lambda pair: pair[0],
        reverse=True,
    )
    ranked = [pair for pair in ranked if pair[0] > 0][: args.top]
    if not ranked:
        print(f"Nada en tu biblioteca encaja con «{args.query}».")
        return 0
    print(f"Resultados para «{args.query}»:\n")
    _print_ranked(ranked, f"encaja con «{args.query}»")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retro-sage", description=__doc__)
    parser.add_argument("--version", action="version", version=f"retro-sage {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_source_args(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--vault", default=DEFAULT_VAULT_URL, help="URL de Retro Vault")
        sub.add_argument("--file", help="Export JSON descargado (modo offline)")

    rec = subparsers.add_parser("recommend", help="Genera recomendaciones desde tu colección.")
    add_source_args(rec)
    rec.add_argument("--top", type=int, default=10, help="Nº de recomendaciones (máx. 50)")
    rec.add_argument("--push", action="store_true", help="Enviar el resultado al Vault")
    rec.add_argument(
        "--weights",
        type=_parse_weights,
        default=DEFAULT_WEIGHTS,
        help=(
            "Pesos género,plataforma,década[,semántica] (default 60,25,15,30; se normalizan; "
            "el 4º solo cuenta con el extra [embeddings])"
        ),
    )
    rec.set_defaults(func=_cmd_recommend)

    prof = subparsers.add_parser("profile", help="Muestra tu perfil de afinidades (debug).")
    add_source_args(prof)
    prof.set_defaults(func=_cmd_profile)

    sim = subparsers.add_parser("similar", help="Juegos de tu biblioteca parecidos a uno dado.")
    add_source_args(sim)
    sim.add_argument("title", help="Título (o parte) del juego de referencia")
    sim.add_argument("--top", type=int, default=10, help="Nº de resultados")
    sim.set_defaults(func=_cmd_similar)

    sea = subparsers.add_parser("search", help="Búsqueda semántica libre en tu biblioteca.")
    add_source_args(sea)
    sea.add_argument("query", help='Consulta libre, p. ej. "rpg corto con buena historia"')
    sea.add_argument("--top", type=int, default=10, help="Nº de resultados")
    sea.set_defaults(func=_cmd_search)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (VaultError, embeddings.EmbeddingsError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
