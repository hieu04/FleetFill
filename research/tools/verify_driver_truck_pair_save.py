"""Verify a driver hire into an already occupied ETS2 truck slot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_hire_save import array, find_owner, find_unit, parse_units, scalar


def occupancy(
    units: list[tuple[str, str, str]], field: str
) -> dict[str, tuple[bool, ...]]:
    result = {}
    for unit_type, unit_id, body in units:
        if unit_type == "garage":
            result[unit_id] = tuple(value != "null" for value in array(body, field))
    return result


def accessory_paths(
    units: list[tuple[str, str, str]], vehicle_id: str
) -> list[str]:
    vehicle = find_unit(units, "vehicle", vehicle_id)
    paths = []
    by_id = {unit_id: (unit_type, body) for unit_type, unit_id, body in units}
    for accessory_id in array(vehicle, "accessories"):
        unit_type, body = by_id[accessory_id]
        if not unit_type.endswith("accessory"):
            raise ValueError(f"Unexpected vehicle child type {unit_type}")
        paths.append(scalar(body, "data_path").strip('"'))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--garage", required=True)
    parser.add_argument("--slot", type=int, required=True)
    parser.add_argument("--expected-cost", type=int, required=True)
    parser.add_argument("--expected-driver-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old_units = parse_units(args.old.read_text(encoding="utf-8", errors="replace"))
    new_units = parse_units(args.new.read_text(encoding="utf-8", errors="replace"))
    old_bank_type, _old_bank_id, old_bank = find_owner(old_units, "money_account")
    new_bank_type, _new_bank_id, new_bank = find_owner(new_units, "money_account")
    old_player_type, _old_player_id, old_player = find_owner(old_units, "drivers")
    new_player_type, _new_player_id, new_player = find_owner(new_units, "drivers")
    _old_offer_type, _old_offer_id, old_offer_owner = find_owner(
        old_units, "drivers_offer"
    )
    _new_offer_type, _new_offer_id, new_offer_owner = find_owner(
        new_units, "drivers_offer"
    )
    garage_id = f"garage.{args.garage}"
    old_garage = find_unit(old_units, "garage", garage_id)
    new_garage = find_unit(new_units, "garage", garage_id)
    old_money = int(scalar(old_bank, "money_account"))
    new_money = int(scalar(new_bank, "money_account"))
    old_company_drivers = array(old_player, "drivers")
    new_company_drivers = array(new_player, "drivers")
    old_company_trucks = array(old_player, "trucks")
    new_company_trucks = array(new_player, "trucks")
    old_offers = array(old_offer_owner, "drivers_offer")
    new_offers = array(new_offer_owner, "drivers_offer")
    old_driver_slots = array(old_garage, "drivers")
    new_driver_slots = array(new_garage, "drivers")
    old_vehicle_slots = array(old_garage, "vehicles")
    new_vehicle_slots = array(new_garage, "vehicles")
    slot_index = args.slot - 1
    hired_driver = new_driver_slots[slot_index]
    old_vehicle = old_vehicle_slots[slot_index]
    new_vehicle = new_vehicle_slots[slot_index]

    old_vehicle_occupancy = occupancy(old_units, "vehicles")
    new_vehicle_occupancy = occupancy(new_units, "vehicles")
    old_driver_occupancy = occupancy(old_units, "drivers")
    new_driver_occupancy = occupancy(new_units, "drivers")
    driver_occupancy_delta = {
        garage: sum(new_driver_occupancy[garage]) - sum(shape)
        for garage, shape in old_driver_occupancy.items()
        if sum(new_driver_occupancy[garage]) != sum(shape)
    }
    old_accessories = accessory_paths(old_units, old_vehicle)
    new_accessories = accessory_paths(new_units, new_vehicle)
    driver_body = find_unit(new_units, "driver_ai", hired_driver)
    hometown = scalar(driver_body, "hometown").strip('"')
    current_city = scalar(driver_body, "current_city").strip('"')

    checks = {
        "bank_unit_type_stable": old_bank_type == new_bank_type,
        "player_unit_type_stable": old_player_type == new_player_type,
        "money_deducted_exactly": old_money - new_money == args.expected_cost,
        "company_driver_count_increased_by_one": len(new_company_drivers)
        == len(old_company_drivers) + 1,
        "company_truck_count_unchanged": len(new_company_trucks)
        == len(old_company_trucks),
        "target_driver_slot_was_free": old_driver_slots[slot_index] == "null",
        "target_driver_slot_now_filled": hired_driver != "null",
        "driver_added_to_company": hired_driver in new_company_drivers,
        "driver_removed_from_offers": hired_driver in old_offers
        and hired_driver not in new_offers,
        "target_truck_present_before": old_vehicle != "null",
        "target_truck_present_after": new_vehicle != "null",
        "all_garage_vehicle_occupancy_unchanged": old_vehicle_occupancy
        == new_vehicle_occupancy,
        "only_reims_driver_occupancy_increased": driver_occupancy_delta
        == {garage_id: 1},
        "other_reims_driver_slots_unchanged": all(
            (old_value == "null") == (new_value == "null")
            for index, (old_value, new_value) in enumerate(
                zip(old_driver_slots, new_driver_slots)
            )
            if index != slot_index
        ),
        "paired_truck_configuration_preserved": old_accessories == new_accessories,
        "driver_hometown_matches_garage": hometown == args.garage,
        "driver_current_city_matches_garage": current_city == args.garage,
    }
    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "ui_verified_driver_label": args.expected_driver_label,
        "hired_driver_id": hired_driver,
        "garage": args.garage,
        "slot": args.slot,
        "money": {
            "before": old_money,
            "after": new_money,
            "deducted": old_money - new_money,
        },
        "company_driver_count": {
            "before": len(old_company_drivers),
            "after": len(new_company_drivers),
        },
        "company_truck_count": {
            "before": len(old_company_trucks),
            "after": len(new_company_trucks),
        },
        "reims_driver_slots": {
            "before": old_driver_slots,
            "after": new_driver_slots,
        },
        "reims_vehicle_slots": {
            "before": old_vehicle_slots,
            "after": new_vehicle_slots,
        },
        "driver_occupancy_delta": driver_occupancy_delta,
        "paired_vehicle": {
            "before_id": old_vehicle,
            "after_id": new_vehicle,
            "accessory_count": len(new_accessories),
            "configuration_preserved": old_accessories == new_accessories,
        },
        "driver_location": {"hometown": hometown, "current_city": current_city},
        "source_files": {
            "before": str(args.old.resolve()),
            "after": str(args.new.resolve()),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"VERIFY_DRIVER_TRUCK_PAIR_REPORT: {args.output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
