"""
Central orchestrator that runs one or more scraper modules (e.g., theori, enki).

Usage examples:
    python main.py                 # run all configured scrapers
    python main.py theori enki     # run specific scrapers
    python main.py --list          # show configured scrapers
    python main.py --dry-run       # propagate the dry-run flag to scrapers
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import traceback
from typing import Iterable, List, Sequence

from sync_utils import load_env

DEFAULT_SCRAPER_MODULES: Sequence[str] = ("theori", "enki")
SCRAPER_ENV_VAR = "JOB_SCRAPER_MODULES"


def configured_modules() -> List[str]:
    """Return the scraper modules defined via env var or fall back to defaults."""
    env_value = os.getenv(SCRAPER_ENV_VAR, "")
    if env_value.strip():
        return [part.strip() for part in env_value.split(",") if part.strip()]
    return list(DEFAULT_SCRAPER_MODULES)


def import_entrypoint(module_name: str):
    """Import a scraper module and return its main() callable."""
    module = importlib.import_module(module_name)
    entrypoint = getattr(module, "main", None)
    if not callable(entrypoint):
        raise AttributeError(f"Module '{module_name}' does not expose a callable main().")
    return entrypoint


def run_modules(modules: Iterable[str], fail_fast: bool = False) -> List[str]:
    """Run each module sequentially, collecting failures."""
    failures: List[str] = []
    for module_name in modules:
        print(f"[MAIN] Running scraper '{module_name}'...")
        try:
            entrypoint = import_entrypoint(module_name)
            entrypoint()
            print(f"[MAIN] Finished '{module_name}'.")
        except Exception:  # noqa: BLE001 - surface the full traceback
            failures.append(module_name)
            print(f"[ERROR] Scraper '{module_name}' failed:", file=sys.stderr)
            traceback.print_exc()
            if fail_fast:
                break
    return failures


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one or more scraper modules (e.g., theori, enki)."
    )
    parser.add_argument(
        "modules",
        nargs="*",
        metavar="MODULE",
        help="Specific scraper modules to run (omit to run all configured modules).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured scraper modules and exit.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first scraper failure.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Propagate the dry-run flag to each scraper (they inspect sys.argv).",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    available = configured_modules()

    if args.list:
        print("[MAIN] Configured scraper modules:")
        for name in available:
            print(f"  - {name}")
        return 0

    targets = args.modules or available
    if not targets:
        print("[ERROR] No scraper modules specified or configured.", file=sys.stderr)
        return 1

    # Ensure .env values are available before any scraper runs.
    load_env()

    failures = run_modules(targets, fail_fast=args.fail_fast)
    if failures:
        print(
            "[MAIN] Finished with failures in: " + ", ".join(failures),
            file=sys.stderr,
        )
        return 1

    print("[MAIN] All scrapers finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
