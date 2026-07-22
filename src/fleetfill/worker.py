"""Console worker used by packaged FleetFill controller and probe subprocesses."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

# These imports make the dynamically dispatched probe dependencies visible to
# frozen-build analysis without importing the Qt GUI into the worker process.
import numpy  # noqa: F401
from PIL import Image, ImageGrab  # noqa: F401

import fleetfill.domain  # noqa: F401
import fleetfill.preflight  # noqa: F401
import fleetfill.profile_safety  # noqa: F401


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("FleetFillWorker requires a Python script or '-m module'.", file=sys.stderr)
        return 2

    if arguments[0] == "-m":
        if len(arguments) < 2:
            print("FleetFillWorker -m requires a module name.", file=sys.stderr)
            return 2
        module = arguments[1]
        sys.argv = [module, *arguments[2:]]
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        return 0

    script = Path(arguments[0]).resolve()
    if not script.is_file() or script.suffix.casefold() != ".py":
        print(f"FleetFillWorker cannot run script: {script}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), *arguments[1:]]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
