"""Verify a complete FleetFill truck-plus-driver batch from two plaintext saves."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_hire_save import array, find_owner, find_unit, parse_units, scalar
from verify_driver_truck_pair_save import accessory_paths
from verify_truck_batch_save import vehicle_details


def garage_arrays(units: list[tuple[str, str, str]]) -> dict[str, dict[str, list[str]]]:
    result = {}
    for unit_type, unit_id, body in units:
        if unit_type != "garage":
            continue
        vehicles = array(body, "vehicles")
        drivers = array(body, "drivers")
        if vehicles and len(vehicles) == len(drivers):
            result[unit_id] = {"vehicles": vehicles, "drivers": drivers}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--expected-cost", type=int, required=True)
    parser.add_argument("--expected-plate-country")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old_units = parse_units(args.old.read_text(encoding="utf-8", errors="replace"))
    new_units = parse_units(args.new.read_text(encoding="utf-8", errors="replace"))
    _old_bank_type, _old_bank_id, old_bank = find_owner(old_units, "money_account")
    _new_bank_type, _new_bank_id, new_bank = find_owner(new_units, "money_account")
    _old_player_type, _old_player_id, old_player = find_owner(old_units, "trucks")
    _new_player_type, _new_player_id, new_player = find_owner(new_units, "trucks")
    _old_offer_type, _old_offer_id, _old_offers = find_owner(old_units, "drivers_offer")
    _new_offer_type, _new_offer_id, new_offers = find_owner(new_units, "drivers_offer")

    old_money = int(scalar(old_bank, "money_account"))
    new_money = int(scalar(new_bank, "money_account"))
    old_trucks = array(old_player, "trucks")
    new_trucks = array(new_player, "trucks")
    old_drivers = array(old_player, "drivers")
    new_drivers = array(new_player, "drivers")
    offered_after = set(array(new_offers, "drivers_offer"))
    added_drivers = sorted(set(new_drivers) - set(old_drivers))

    old_garages = garage_arrays(old_units)
    new_garages = garage_arrays(new_units)
    changed = [
        garage_id
        for garage_id in sorted(set(old_garages) & set(new_garages))
        if [value != "null" for value in old_garages[garage_id]["vehicles"]]
        != [value != "null" for value in new_garages[garage_id]["vehicles"]]
        or [value != "null" for value in old_garages[garage_id]["drivers"]]
        != [value != "null" for value in new_garages[garage_id]["drivers"]]
    ]
    target_id = changed[0] if len(changed) == 1 else None
    target_city = target_id.removeprefix("garage.") if target_id else None
    old_target = old_garages.get(target_id, {"vehicles": [], "drivers": []})
    new_target = new_garages.get(target_id, {"vehicles": [], "drivers": []})

    target_vehicle_ids = new_target["vehicles"]
    target_driver_ids = new_target["drivers"]
    vehicles = [
        vehicle_details(new_units, vehicle_id)
        for vehicle_id in target_vehicle_ids
        if vehicle_id != "null"
    ]
    accessory_sets = [set(vehicle["accessory_paths"]) for vehicle in vehicles]
    drivers = []
    for driver_id in target_driver_ids:
        if driver_id == "null":
            continue
        body = find_unit(new_units, "driver_ai", driver_id)
        drivers.append(
            {
                "driver_id": driver_id,
                "hometown": scalar(body, "hometown").strip('"'),
                "current_city": scalar(body, "current_city").strip('"'),
            }
        )

    unrelated_driver_slots_unchanged = True
    unrelated_vehicle_occupancy_unchanged = True
    preexisting_vehicle_configs_preserved = True
    compared_preexisting_vehicles = 0
    for garage_id in sorted(set(old_garages) & set(new_garages)):
        if garage_id == target_id:
            continue
        old_garage = old_garages[garage_id]
        new_garage = new_garages[garage_id]
        if old_garage["drivers"] != new_garage["drivers"]:
            unrelated_driver_slots_unchanged = False
        old_shape = [value != "null" for value in old_garage["vehicles"]]
        new_shape = [value != "null" for value in new_garage["vehicles"]]
        if old_shape != new_shape:
            unrelated_vehicle_occupancy_unchanged = False
            continue
        for old_vehicle, new_vehicle in zip(
            old_garage["vehicles"], new_garage["vehicles"]
        ):
            if old_vehicle == "null":
                continue
            compared_preexisting_vehicles += 1
            if accessory_paths(old_units, old_vehicle) != accessory_paths(
                new_units, new_vehicle
            ):
                preexisting_vehicle_configs_preserved = False

    checks = {
        "money_deducted_exactly": old_money - new_money == args.expected_cost,
        "company_truck_count_increased": len(new_trucks) == len(old_trucks) + args.count,
        "company_driver_count_increased": len(new_drivers) == len(old_drivers) + args.count,
        "exactly_one_garage_changed": len(changed) == 1,
        "target_was_completely_empty": old_target["vehicles"] == ["null"] * args.count
        and old_target["drivers"] == ["null"] * args.count,
        "target_is_completely_filled": len(target_vehicle_ids) == args.count
        and len(target_driver_ids) == args.count
        and all(value != "null" for value in target_vehicle_ids + target_driver_ids),
        "target_trucks_are_unique": len(set(target_vehicle_ids)) == args.count,
        "target_drivers_are_unique": len(set(target_driver_ids)) == args.count,
        "target_trucks_are_in_company_fleet": all(
            vehicle_id in new_trucks for vehicle_id in target_vehicle_ids
        ),
        "new_company_drivers_match_target": added_drivers == sorted(target_driver_ids),
        "unrelated_driver_slots_unchanged": unrelated_driver_slots_unchanged,
        "unrelated_vehicle_occupancy_unchanged": unrelated_vehicle_occupancy_unchanged,
        "all_preexisting_vehicle_configs_preserved": preexisting_vehicle_configs_preserved,
        "hired_drivers_removed_from_offers": all(
            driver_id not in offered_after for driver_id in target_driver_ids
        ),
        "all_trucks_have_zero_odometer": all(
            vehicle["odometer"] == "0" for vehicle in vehicles
        ),
        "all_trucks_have_full_fuel": all(
            vehicle["fuel_relative"] == "1" for vehicle in vehicles
        ),
        "all_truck_configurations_match": bool(accessory_sets)
        and all(paths == accessory_sets[0] for paths in accessory_sets[1:]),
        "all_driver_hometowns_match_target": all(
            driver["hometown"] == target_city for driver in drivers
        ),
        "all_driver_current_cities_match_target": all(
            driver["current_city"] == target_city for driver in drivers
        ),
    }
    if args.expected_plate_country:
        checks["all_plates_match_target_country"] = all(
            f"|{args.expected_plate_country}" in vehicle["license_plate"]
            for vehicle in vehicles
        )

    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "target_garage": target_id,
        "target_city": target_city,
        "changed_garages": changed,
        "money": {
            "before": old_money,
            "after": new_money,
            "deducted": old_money - new_money,
        },
        "company_trucks": {"before": len(old_trucks), "after": len(new_trucks)},
        "company_drivers": {"before": len(old_drivers), "after": len(new_drivers)},
        "garage_before": old_target,
        "garage_after": new_target,
        "new_trucks": vehicles,
        "new_drivers": drivers,
        "preexisting_vehicles_compared": compared_preexisting_vehicles,
        "source_files": {
            "before": str(args.old.resolve()),
            "after": str(args.new.resolve()),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"VERIFY_FILL_BATCH_REPORT: {args.output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
