"""Packaged fixed-scope FleetFill personal beta entry point."""

from __future__ import annotations

import sys

from fleetfill.application import main


if __name__ == "__main__":
    raise SystemExit(main(["--personal-beta", *sys.argv[1:]]))
