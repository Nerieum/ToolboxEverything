#!/usr/bin/env python3
"""
Toolbox Everything — point d'entrée.

- Sous gunicorn : c'est `app` (module-level) qui est importé ; la bannière et
  Compress sont déjà gérés par `create_app()`.
- En direct (`python run.py [--dev]`) : on demande la bannière via la variable
  d'env TOOLBOX_PRINT_BANNER et on lance le serveur de dev Flask.
"""

from __future__ import annotations

import argparse
import os
import sys

from app import __version__


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Toolbox Everything — collection d'outils pratiques",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  python run.py                     # production locale (Werkzeug)\n"
            "  python run.py --dev               # mode dev + reloader\n"
            "  python run.py --port 5000         # port custom\n"
        ),
    )
    parser.add_argument("--dev", action="store_true", help="Mode développement (debug + reloader)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    # Par défaut, le serveur de développement reste local. HOST=0.0.0.0 permet
    # explicitement un accès LAN ; Docker utilise directement Gunicorn.
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("HOST", "127.0.0.1"),
    )
    parser.add_argument("--no-banner", action="store_true", help="Ne pas imprimer la bannière")
    parser.add_argument("--version", action="version", version=f"Toolbox Everything v{__version__}")
    return parser


def _build_app(print_banner: bool):
    # Active la bannière AVANT l'import de create_app pour qu'elle soit imprimée
    # une seule fois lors de la première création.
    if print_banner:
        os.environ["TOOLBOX_PRINT_BANNER"] = "1"

    from app.services.main import create_app

    return create_app()


# Objet exposé à Gunicorn (« run:app »). En lancement direct, on évite de
# construire inutilement une première app avant celle configurée par `main()`.
if __name__ != "__main__":
    app = _build_app(print_banner=False)


def main() -> None:
    args = _create_parser().parse_args()

    if not 1 <= args.port <= 65535:
        print(f"Erreur: port invalide ({args.port})", file=sys.stderr)
        sys.exit(2)

    # Pour le mode direct on re-crée l'app afin d'avoir la bannière et le flag debug.
    runtime_app = _build_app(print_banner=not args.no_banner)

    try:
        runtime_app.run(
            host=args.host,
            port=args.port,
            debug=args.dev,
            use_reloader=args.dev,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur.")
    except Exception as exc:  # noqa: BLE001
        print(f"Erreur au démarrage: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
