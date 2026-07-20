"""Summarize company money, trucks, drivers, and garage slot states."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_hire_save import array, find_owner, parse_units, scalar


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("save", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.save.resolve()
    units = parse_units(source.read_text(encoding="utf-8", errors="replace"))
    _bank_type, _bank_id, bank = find_owner(units, "money_account")
    _player_type, _player_id, player = find_owner(units, "trucks")

    garages = []
    for unit_type, unit_id, body in units:
        if unit_type != "garage":
            continue
        vehicles = array(body, "vehicles")
        drivers = array(body, "drivers")
        if not vehicles or len(vehicles) != len(drivers):
            continue
        occupied = sum(
            vehicle != "null" and driver != "null"
            for vehicle, driver in zip(vehicles, drivers)
        )
        truck_present = sum(
            vehicle != "null" and driver == "null"
            for vehicle, driver in zip(vehicles, drivers)
        )
        free = sum(
            vehicle == "null" and driver == "null"
            for vehicle, driver in zip(vehicles, drivers)
        )
        invalid_driver_only = sum(
            vehicle == "null" and driver != "null"
            for vehicle, driver in zip(vehicles, drivers)
        )
        garages.append(
            {
                "id": unit_id,
                "city": unit_id.removeprefix("garage."),
                "capacity": len(vehicles),
                "occupied": occupied,
                "truck_present": truck_present,
                "free": free,
                "invalid_driver_only": invalid_driver_only,
                "vehicles": vehicles,
                "drivers": drivers,
            }
        )
    garages.sort(key=lambda item: item["city"])
    summary = {
        "source": str(source),
        "money_eur": int(scalar(bank, "money_account")),
        "company_truck_count": len(array(player, "trucks")),
        "company_driver_count": len(array(player, "drivers")),
        "garage_count": len(garages),
        "large_garages": [garage for garage in garages if garage["capacity"] == 5],
        "all_garages": garages,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"COMPANY_SAVE_REPORT: {args.output.resolve()}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
