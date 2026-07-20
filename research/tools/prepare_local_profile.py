"""Inspect or rename ETS2 profile metadata without touching save-game data.

The ScsC decoder is loaded from the locally inspected Easy SCS ModManager
source tree, so this utility does not duplicate or silently alter that logic.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path


SAFE_INSPECTION_KEYS = ("profile_name", "steam", "cloud", "user_profile")


def load_crypto_module(path: Path):
    spec = importlib.util.spec_from_file_location("easy_scsmodmanager_crypto", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load crypto module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_profile(path: Path, crypto_module) -> str:
    data = path.read_bytes()
    if data.startswith(b"ScsC"):
        data = crypto_module.decrypt_scsc(data)
    if not data.startswith(b"SiiNunit"):
        raise ValueError(f"Unexpected profile format in {path}")
    return data.decode("utf-8")


def inspect(text: str) -> None:
    for number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if any(key in lowered for key in SAFE_INSPECTION_KEYS):
            print(f"{number}: {line.strip()}")


def rename_profile(text: str, old_name: str, new_name: str) -> str:
    pattern = re.compile(
        r'(?m)^(\s*profile_name\s*:\s*)(?:"([^"\r\n]*)"|([^\s\r\n]+))(\s*)$'
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"Expected one profile_name field, found {len(matches)}")
    existing_name = matches[0].group(2) or matches[0].group(3)
    if existing_name != old_name:
        raise ValueError(
            f"Expected profile name {old_name!r}, found {existing_name!r}"
        )
    if '"' in new_name or "\n" in new_name or "\r" in new_name:
        raise ValueError("The new profile name contains an unsupported character")
    return pattern.sub(
        lambda match: f'{match.group(1)}"{new_name}"{match.group(4)}',
        text,
        count=1,
    )


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_bytes(text.encode("utf-8"))
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--crypto-module", type=Path, required=True)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--old-name")
    parser.add_argument("--new-name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    crypto_module = load_crypto_module(args.crypto_module.resolve())
    text = read_profile(args.input.resolve(), crypto_module)

    if args.inspect:
        inspect(text)

    rename_requested = any((args.old_name, args.new_name, args.output))
    if rename_requested:
        if not all((args.old_name, args.new_name, args.output)):
            parser.error("--old-name, --new-name, and --output must be used together")
        updated = rename_profile(text, args.old_name, args.new_name)
        write_atomic(args.output.resolve(), updated)
        print(f"WROTE_LOCAL_PROFILE_METADATA: {args.output.resolve()}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
