"""Decrypt an ScsC-wrapped SII file into a separate plaintext research copy."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def load_crypto_module(path: Path):
    spec = importlib.util.spec_from_file_location("easy_scsmodmanager_crypto", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load crypto module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--crypto-module", type=Path, required=True)
    args = parser.parse_args()

    source = args.input.resolve()
    destination = args.output.resolve()
    data = source.read_bytes()
    if data.startswith(b"ScsC"):
        crypto = load_crypto_module(args.crypto_module.resolve())
        data = crypto.decrypt_scsc(data)
    known_magic = (b"SiiNunit", b"BSII")
    if not data.startswith(known_magic):
        raise ValueError(
            f"Unexpected SII format in {source}; decoded prefix is {data[:16]!r}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print(f"DECRYPTED_COPY: {destination}")
    print(f"PLAINTEXT_BYTES: {len(data)}")
    print(f"INNER_FORMAT: {'binary BSII' if data.startswith(b'BSII') else 'text SiiNunit'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
