"""CLI de Retro Sage.

Uso:
    retro-sage recommend [--vault URL | --file export.json] [--top N] [--push]
"""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .profile import build_profile
from .scorer import recommend
from .vault_client import (
    DEFAULT_VAULT_URL,
    VaultError,
    fetch_library,
    load_library_file,
    push_recommendations,
)

MIN_SIGNALS = 3


def _cmd_recommend(args: argparse.Namespace) -> int:
    try:
        payload = load_library_file(args.file) if args.file else fetch_library(args.vault)
    except VaultError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    games = payload["games"]
    profile = build_profile(games)
    if not profile.is_usable(MIN_SIGNALS):
        print(
            f"Aún no hay perfil que construir ({profile.signals} señales; mínimo {MIN_SIGNALS}).\n"
            "Marca ratings ★, completa juegos o juega unas sesiones en Retro Vault y vuelve."
        )
        return 0

    items = recommend(games, profile, top=args.top)
    if not items:
        print("Perfil construido, pero ningún juego sin jugar coincide con tus gustos todavía.")
        return 0

    print(f"Perfil: {profile.signals} señales · biblioteca: {len(games)} juegos\n")
    width = max(len(item["title"] or "?") for item in items)
    for rank, item in enumerate(items, start=1):
        title = (item["title"] or "?").ljust(width)
        print(f"{rank:>2}. {title}  [{item['platform']}]  {item['score']:.2f}  — {item['reason']}")

    if args.push:
        try:
            stored = push_recommendations(items, args.vault)
        except VaultError as exc:
            print(f"\n✗ {exc}", file=sys.stderr)
            return 1
        print(f"\n✓ {stored} recomendaciones enviadas al panel 'Recomendados' de Retro Vault.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retro-sage", description=__doc__)
    parser.add_argument("--version", action="version", version=f"retro-sage {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rec = subparsers.add_parser("recommend", help="Genera recomendaciones desde tu colección.")
    rec.add_argument("--vault", default=DEFAULT_VAULT_URL, help="URL de Retro Vault")
    rec.add_argument("--file", help="Export JSON descargado (modo offline)")
    rec.add_argument("--top", type=int, default=10, help="Nº de recomendaciones (máx. 50)")
    rec.add_argument("--push", action="store_true", help="Enviar el resultado al Vault")
    rec.set_defaults(func=_cmd_recommend)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
