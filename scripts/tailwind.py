#!/usr/bin/env python3
"""Installer, compiler et valider Tailwind CLI standalone."""

from __future__ import annotations

import argparse
import os
import platform
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path

TAILWIND_VERSION = os.environ.get("TAILWIND_VERSION", "4.3.3")
ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = ROOT / "bin"
VERSION_FILE = BIN_DIR / ".tailwind-version"
INPUT_CSS = ROOT / "app" / "static" / "css" / "input.css"
OUTPUT_CSS = ROOT / "app" / "static" / "css" / "tailwind.css"
CONFIG = ROOT / "tailwind.config.js"

CRITICAL_CLASSES = (
    ".hidden",
    ".flex",
    ".grid",
    ".lg\\:flex",
    ".max-w-7xl",
)


def _binary_name() -> str:
    return "tailwindcss.exe" if os.name == "nt" else "tailwindcss"


def binary_path() -> Path:
    return BIN_DIR / _binary_name()


def _platform_parts() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        tw_os = "macos"
    elif system == "linux":
        tw_os = "linux"
    elif system == "windows":
        tw_os = "windows"
    else:
        raise SystemExit(f"OS non supporte pour Tailwind standalone: {system}")

    if machine in {"x86_64", "amd64"}:
        tw_arch = "x64"
    elif machine in {"arm64", "aarch64"}:
        tw_arch = "arm64"
    else:
        raise SystemExit(f"Architecture non supportee pour Tailwind standalone: {machine}")

    return tw_os, tw_arch


def install(force: bool = False) -> Path:
    target = binary_path()
    installed_version = ""
    if VERSION_FILE.exists():
        installed_version = VERSION_FILE.read_text(encoding="utf-8").strip()

    if target.exists() and installed_version == TAILWIND_VERSION and not force:
        print(f"Tailwind CLI deja present: {target.relative_to(ROOT)}")
        return target

    tw_os, tw_arch = _platform_parts()
    suffix = ".exe" if tw_os == "windows" else ""
    url = (
        f"https://github.com/tailwindlabs/tailwindcss/releases/download/"
        f"v{TAILWIND_VERSION}/tailwindcss-{tw_os}-{tw_arch}{suffix}"
    )

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Telechargement Tailwind CLI v{TAILWIND_VERSION}: {url}")
    download = target.with_suffix(target.suffix + ".download")
    urllib.request.urlretrieve(url, download)  # noqa: S310 - URL controlee par la version.
    download.replace(target)

    if os.name != "nt":
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    VERSION_FILE.write_text(TAILWIND_VERSION + "\n", encoding="utf-8")
    print(f"Tailwind CLI installe: {target.relative_to(ROOT)}")
    return target


def _run_tailwind(args: list[str]) -> int:
    exe = install()
    command = [
        str(exe),
        "-c",
        str(CONFIG),
        "-i",
        str(INPUT_CSS),
        "-o",
        str(OUTPUT_CSS),
        *args,
    ]
    return subprocess.call(command, cwd=ROOT)


def build() -> int:
    print("Build Tailwind CSS -> app/static/css/tailwind.css")
    return _run_tailwind(["--minify"])


def watch() -> int:
    print("Tailwind watch mode -> app/static/css/tailwind.css")
    return _run_tailwind(["--watch"])


def check() -> int:
    if not OUTPUT_CSS.exists():
        print("CSS Tailwind manquant: app/static/css/tailwind.css", file=sys.stderr)
        return 1

    css = OUTPUT_CSS.read_text(encoding="utf-8", errors="replace")
    missing = [selector for selector in CRITICAL_CLASSES if selector not in css]
    if missing:
        print(
            "CSS Tailwind incomplet, classes critiques absentes: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    print("CSS Tailwind OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gestion Tailwind CLI standalone")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Telecharge le binaire Tailwind")
    install_parser.add_argument("--force", action="store_true", help="Retelcharger le binaire")

    subparsers.add_parser("build", help="Compile le CSS Tailwind minifie")
    subparsers.add_parser("watch", help="Compile Tailwind en continu")
    subparsers.add_parser("check", help="Valide le CSS Tailwind genere")

    args = parser.parse_args(argv)

    if args.command == "install":
        install(force=args.force)
        return 0
    if args.command == "build":
        return build()
    if args.command == "watch":
        return watch()
    if args.command == "check":
        return check()

    parser.error(f"Commande inconnue: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
