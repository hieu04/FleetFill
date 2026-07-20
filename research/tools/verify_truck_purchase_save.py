"""Verify one ETS2 truck purchase by comparing decoded plaintext saves."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_hire_save import array, find_owner, find_unit, parse_units, scalar


def garage_occupancy(units: list[tuple[str, str, str]]) -> dict[str, int]:
    result = {}
    for unit_type, unit_id, body in units:
        if unit_type == "garage":
            result[unit_id] = sum(value != "null" for value in array(body, "vehicles"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--garage", required=True)
    parser.add_argument("--slot", type=int, required=True, help="One-based garage slot")
    parser.add_argument("--expected-cost", type=int, required=True)
    parser.add_argument("--expected-accessory", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old_units = parse_units(args.old.read_text(encoding="utf-8", errors="replace"))
    new_units = parse_units(args.new.read_text(encoding="utf-8", errors="replace"))
    old_bank_type, _old_bank_id, old_bank = find_owner(old_units, "money_account")
    new_bank_type, _new_bank_id, new_bank = find_owner(new_units, "money_account")
    old_player_type, _old_player_id, old_player = find_owner(old_units, "trucks")
    new_player_type, _new_player_id, new_player = find_owner(new_units, "trucks")
    garage_id = f"garage.{args.garage}"
    old_garage = find_unit(old_units, "garage", garage_id)
    new_garage = find_unit(new_units, "garage", garage_id)

    old_money = int(scalar(old_bank, "money_account"))
    new_money = int(scalar(new_bank, "money_account"))
    old_trucks = array(old_player, "trucks")
    new_trucks = array(new_player, "trucks")
    old_vehicles = array(old_garage, "vehicles")
    new_vehicles = array(new_garage, "vehicles")
    old_drivers = array(old_garage, "drivers")
    new_drivers = array(new_garage, "drivers")
    slot_index = args.slot - 1
    if not 0 <= slot_index < len(new_vehicles):
        raise ValueError(f"Slot {args.slot} is outside garage capacity {len(new_vehicles)}")
    purchased_vehicle = new_vehicles[slot_index]
    vehicle_body = find_unit(new_units, "vehicle", purchased_vehicle)
    accessory_ids = array(vehicle_body, "accessories")
    accessory_paths = []
    for accessory_id in accessory_ids:
        for unit_type, unit_id, body in new_units:
            if unit_id == accessory_id and unit_type.endswith("accessory"):
                accessory_paths.append(scalar(body, "data_path").strip('"'))
                break

    old_occupancy = garage_occupancy(old_units)
    new_occupancy = garage_occupancy(new_units)
    occupancy_delta = {
        garage: new_occupancy.get(garage, 0) - count
        for garage, count in old_occupancy.items()
        if new_occupancy.get(garage, 0) != count
    }
    checks = {
        "bank_unit_type_stable": old_bank_type == new_bank_type,
        "player_unit_type_stable": old_player_type == new_player_type,
        "money_deducted_exactly": old_money - new_money == args.expected_cost,
        "company_truck_count_increased_by_one": len(new_trucks) == len(old_trucks) + 1,
        "target_slot_was_free": old_vehicles[slot_index] == "null",
        "target_slot_now_has_vehicle": purchased_vehicle != "null",
        "new_vehicle_is_in_company_trucks": purchased_vehicle in new_trucks,
        # ETS2 regenerates _nameless object IDs on an ordinary save, so compare
        # the stable occupied/free shape rather than literal vehicle IDs.
        "other_target_garage_slot_occupancy_unchanged": all(
            (old_value == "null") == (new_value == "null")
            for index, (old_value, new_value) in enumerate(
                zip(old_vehicles, new_vehicles)
            )
            if index != slot_index
        ),
        "garage_driver_slots_unchanged": old_drivers == new_drivers,
        "only_reims_occupancy_increased": occupancy_delta == {garage_id: 1},
        "new_vehicle_has_zero_odometer": scalar(vehicle_body, "odometer") == "0",
        "new_vehicle_has_full_fuel": scalar(vehicle_body, "fuel_relative") == "1",
        "plate_country_matches_france": "|france" in scalar(vehicle_body, "license_plate"),
        "all_expected_accessories_present": all(
            expected in accessory_paths for expected in args.expected_accessory
        ),
    }
    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "garage": args.garage,
        "slot": args.slot,
        "purchased_vehicle_id": purchased_vehicle,
        "money": {
            "before": old_money,
            "after": new_money,
            "deducted": old_money - new_money,
        },
        "company_truck_count": {"before": len(old_trucks), "after": len(new_trucks)},
        "garage_vehicle_slots": {"before": old_vehicles, "after": new_vehicles},
        "garage_driver_slots": {"before": old_drivers, "after": new_drivers},
        "garage_occupancy_delta": occupancy_delta,
        "vehicle": {
            "accessory_count": len(accessory_ids),
            "accessory_paths": accessory_paths,
            "license_plate": scalar(vehicle_body, "license_plate").strip('"'),
            "fuel_relative": scalar(vehicle_body, "fuel_relative"),
            "odometer": scalar(vehicle_body, "odometer"),
        },
        "expected_accessories": args.expected_accessory,
        "source_files": {
            "before": str(args.old.resolve()),
            "after": str(args.new.resolve()),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"VERIFY_TRUCK_PURCHASE_REPORT: {args.output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
