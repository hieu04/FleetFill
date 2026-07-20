"""Verify an ETS2 multi-truck purchase by comparing decoded plaintext saves."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_hire_save import array, find_owner, find_unit, parse_units, scalar
from verify_truck_purchase_save import garage_occupancy


def vehicle_details(
    units: list[tuple[str, str, str]], vehicle_id: str
) -> dict[str, object]:
    body = find_unit(units, "vehicle", vehicle_id)
    accessory_ids = array(body, "accessories")
    unit_by_id = {unit_id: (unit_type, unit_body) for unit_type, unit_id, unit_body in units}
    paths: list[str] = []
    for accessory_id in accessory_ids:
        unit_type, accessory_body = unit_by_id[accessory_id]
        if unit_type.endswith("accessory"):
            paths.append(scalar(accessory_body, "data_path").strip('"'))
    return {
        "vehicle_id": vehicle_id,
        "accessory_count": len(accessory_ids),
        "accessory_paths": paths,
        "license_plate": scalar(body, "license_plate").strip('"'),
        "fuel_relative": scalar(body, "fuel_relative"),
        "odometer": scalar(body, "odometer"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--garage", required=True)
    parser.add_argument("--slots", type=int, nargs="+", required=True)
    parser.add_argument("--expected-cost", type=int, required=True)
    parser.add_argument("--expected-plate-country", default="france")
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
    slot_indexes = [slot - 1 for slot in args.slots]
    if len(set(slot_indexes)) != len(slot_indexes):
        raise ValueError("--slots must not contain duplicates")
    if any(index < 0 or index >= len(new_vehicles) for index in slot_indexes):
        raise ValueError(f"A requested slot is outside garage capacity {len(new_vehicles)}")

    purchased_ids = [new_vehicles[index] for index in slot_indexes]
    purchased = [vehicle_details(new_units, vehicle_id) for vehicle_id in purchased_ids]
    old_occupancy = garage_occupancy(old_units)
    new_occupancy = garage_occupancy(new_units)
    occupancy_delta = {
        garage: new_occupancy.get(garage, 0) - count
        for garage, count in old_occupancy.items()
        if new_occupancy.get(garage, 0) != count
    }
    expected_accessories = set(args.expected_accessory)
    accessory_sets = [set(vehicle["accessory_paths"]) for vehicle in purchased]
    checks = {
        "bank_unit_type_stable": old_bank_type == new_bank_type,
        "player_unit_type_stable": old_player_type == new_player_type,
        "money_deducted_exactly": old_money - new_money == args.expected_cost,
        "company_truck_count_increased_by_batch": len(new_trucks)
        == len(old_trucks) + len(slot_indexes),
        "target_slots_were_free": all(old_vehicles[index] == "null" for index in slot_indexes),
        "target_slots_now_have_unique_vehicles": all(value != "null" for value in purchased_ids)
        and len(set(purchased_ids)) == len(purchased_ids),
        "new_vehicles_are_in_company_trucks": all(value in new_trucks for value in purchased_ids),
        "other_target_garage_slot_occupancy_unchanged": all(
            (old_value == "null") == (new_value == "null")
            for index, (old_value, new_value) in enumerate(zip(old_vehicles, new_vehicles))
            if index not in slot_indexes
        ),
        "garage_driver_slots_unchanged": old_drivers == new_drivers,
        "only_target_garage_occupancy_increased": occupancy_delta
        == {garage_id: len(slot_indexes)},
        "all_new_vehicles_have_zero_odometer": all(
            vehicle["odometer"] == "0" for vehicle in purchased
        ),
        "all_new_vehicles_have_full_fuel": all(
            vehicle["fuel_relative"] == "1" for vehicle in purchased
        ),
        "all_plates_match_garage_country": all(
            f"|{args.expected_plate_country}" in str(vehicle["license_plate"])
            for vehicle in purchased
        ),
        "all_expected_accessories_present": all(
            expected_accessories.issubset(accessories) for accessories in accessory_sets
        ),
        "all_new_truck_configurations_match": all(
            accessories == accessory_sets[0] for accessories in accessory_sets[1:]
        ),
    }
    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "garage": args.garage,
        "slots": args.slots,
        "money": {
            "before": old_money,
            "after": new_money,
            "deducted": old_money - new_money,
        },
        "company_truck_count": {"before": len(old_trucks), "after": len(new_trucks)},
        "garage_vehicle_slots": {"before": old_vehicles, "after": new_vehicles},
        "garage_driver_slots": {"before": old_drivers, "after": new_drivers},
        "garage_occupancy_delta": occupancy_delta,
        "purchased_vehicles": purchased,
        "expected_accessories": args.expected_accessory,
        "expected_plate_country": args.expected_plate_country,
        "source_files": {
            "before": str(args.old.resolve()),
            "after": str(args.new.resolve()),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"VERIFY_TRUCK_BATCH_REPORT: {args.output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
