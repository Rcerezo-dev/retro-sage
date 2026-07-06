"""CLI de Retro Sage.

Uso:
    retro-sage recommend [--vault URL | --file export.json] [--top N] [--push] [--weights G,P,D]
    retro-sage profile   [--vault URL | --file export.json]
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
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


def _parse_weights(text: str) -> tuple[float, float, float]:
    """'60,25,15' → (0.60, 0.25, 0.15) — normaliza para que sumen 1."""
    try:
        genre, platform, decade = (float(tok) for tok in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "formato: GÉNERO,PLATAFORMA,DÉCADA — p. ej. --weights 60,25,15"
        ) from None
    total = genre + platform + decade
    if min(genre, platform, decade) < 0 or total <= 0:
        raise argparse.ArgumentTypeError("los pesos deben ser ≥ 0 y sumar más de 0")
    return (genre / total, platform / total, decade / total)


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

    items = recommend(games, profile, top=args.top, weights=args.weights)
    if not items:
        print("Perfil construido, pero ningún juego sin jugar coincide con tus gustos todavía.")
        return 0

    print(f"Perfil: {profile.signals} señales · biblioteca: {len(games)} juegos\n")
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
        help="Pesos género,plataforma,década (default 60,25,15; se normalizan)",
    )
    rec.set_defaults(func=_cmd_recommend)

    prof = subparsers.add_parser("profile", help="Muestra tu perfil de afinidades (debug).")
    add_source_args(prof)
    prof.set_defaults(func=_cmd_profile)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except VaultError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
