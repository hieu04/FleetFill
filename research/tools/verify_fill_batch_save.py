"""Verify a complete FleetFill truck-plus-driver batch from two plaintext saves."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from verify_hire_save import array, find_owner, find_unit, parse_units, scalar
from verify_driver_truck_pair_save import accessory_paths
from verify_truck_batch_save import vehicle_details


PLAYER_DELIVERY_SCALARS = (
    "my_vehicles_mode",
    "assigned_vehicles_mode",
    "truck_placement",
    "trailer_placement",
    "assigned_trailer_connected",
    "my_truck_placement",
    "my_truck_placement_valid",
    "my_trailer_placement",
    "my_trailer_attached",
    "my_trailer_used",
)
PLAYER_DELIVERY_REFERENCES = (
    "current_job",
    "current_bus_job",
    "selected_job",
    "assigned_truck",
    "assigned_trailer",
    "my_truck",
    "my_trailer",
)
NAMELESS_ID_PATTERN = re.compile(r"_nameless(?:\.[0-9a-f]+)+", re.IGNORECASE)


def canonicalize_nameless_ids(text: str) -> str:
    """Replace volatile SII object IDs while preserving reference relationships."""

    replacements: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        if value not in replacements:
            replacements[value] = f"<nameless:{len(replacements)}>"
        return replacements[value]

    return NAMELESS_ID_PATTERN.sub(replace, text)


def referenced_unit_signature(
    units: list[tuple[str, str, str]], reference: str
) -> dict[str, str] | None:
    if reference == "null":
        return None
    for unit_type, unit_id, body in units:
        if unit_id == reference:
            return {
                "unit_type": unit_type,
                "body": canonicalize_nameless_ids(body),
            }
    raise ValueError(f"Missing referenced delivery unit {reference!r}")


def active_delivery_state(
    units: list[tuple[str, str, str]],
) -> dict[str, object]:
    """Build a stable description of the player's active delivery and vehicle."""

    _economy_type, _economy_id, economy = find_owner(
        units, "stored_online_job_id"
    )
    _player_type, _player_id, player = find_owner(units, "current_job")
    online_job_id = scalar(economy, "stored_online_job_id")
    current_job = scalar(player, "current_job")
    active_kind = (
        "world_of_trucks"
        if online_job_id != "0"
        else "local"
        if current_job != "null"
        else "none"
    )
    return {
        "active_kind": active_kind,
        "online_job_id": online_job_id,
        "player": {
            name: scalar(player, name) for name in PLAYER_DELIVERY_SCALARS
        },
        "references": {
            name: referenced_unit_signature(units, scalar(player, name))
            for name in PLAYER_DELIVERY_REFERENCES
        },
    }


def active_delivery_summary(state: dict[str, object]) -> dict[str, object]:
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    references = state["references"]
    assert isinstance(references, dict)
    return {
        "active_kind": state["active_kind"],
        "online_job_id": state["online_job_id"],
        "referenced_unit_types": {
            name: value["unit_type"] if value else None
            for name, value in references.items()
        },
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def active_delivery_preserved(
    before: dict[str, object], after: dict[str, object]
) -> bool:
    """Accept stable local jobs and ETS2's online-job materialization transition."""

    if before == after:
        return True
    if not (
        before["active_kind"] == after["active_kind"] == "world_of_trucks"
    ):
        return False
    if before["player"] != after["player"]:
        return False
    before_refs = before["references"]
    after_refs = after["references"]
    assert isinstance(before_refs, dict) and isinstance(after_refs, dict)
    for name in PLAYER_DELIVERY_REFERENCES:
        if name == "current_job":
            continue
        if before_refs[name] != after_refs[name]:
            return False

    before_job = before_refs["current_job"]
    after_job = after_refs["current_job"]
    if before_job is None and after_job is None:
        return True
    if before_job is None and after_job is not None:
        body = after_job["body"]
        return (
            after_job["unit_type"] == "player_job"
            and re.search(r"(?m)^ online_job_id: (\d+)$", body) is not None
            and re.search(r"(?m)^ is_trailer_loaded: true$", body) is not None
        )
    if before_job is None or after_job is None:
        return False

    def without_online_id(job: dict[str, str]) -> dict[str, str]:
        return {
            "unit_type": job["unit_type"],
            "body": re.sub(
                r"(?m)^ online_job_id: \d+$",
                " online_job_id: <online>",
                job["body"],
            ),
        }

    return without_online_id(before_job) == without_online_id(after_job)


def profit_entry_net(body: str) -> int:
    return (
        int(scalar(body, "revenue"))
        - int(scalar(body, "wage"))
        - int(scalar(body, "maintenance"))
        - int(scalar(body, "fuel"))
    )


def unique_new_profit_events(
    old_units: list[tuple[str, str, str]],
    new_units: list[tuple[str, str, str]],
) -> list[str]:
    """Return semantic employee jobs added while ETS2 advanced company time."""

    old_entries = {
        body for unit_type, _unit_id, body in old_units if unit_type == "profit_log_entry"
    }
    new_entries = {
        body for unit_type, _unit_id, body in new_units if unit_type == "profit_log_entry"
    }
    return sorted(new_entries - old_entries)


def active_job_fines(state: dict[str, object]) -> int:
    references = state["references"]
    assert isinstance(references, dict)
    job = references["current_job"]
    if job is None:
        return 0
    match = re.search(r"(?m)^ total_fines: (\d+)$", job["body"])
    return int(match.group(1)) if match else 0


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


def changed_slot_indexes(
    old_target: dict[str, list[str]], new_target: dict[str, list[str]]
) -> list[int]:
    """Return garage indexes whose paired truck/driver assignment changed."""

    old_vehicles = old_target.get("vehicles", [])
    old_drivers = old_target.get("drivers", [])
    new_vehicles = new_target.get("vehicles", [])
    new_drivers = new_target.get("drivers", [])
    if not (
        len(old_vehicles)
        == len(old_drivers)
        == len(new_vehicles)
        == len(new_drivers)
    ):
        return []
    return [
        index
        for index in range(len(old_vehicles))
        if old_vehicles[index] != new_vehicles[index]
        or old_drivers[index] != new_drivers[index]
    ]


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
    old_delivery = active_delivery_state(old_units)
    new_delivery = active_delivery_state(new_units)
    _old_bank_type, _old_bank_id, old_bank = find_owner(old_units, "money_account")
    _new_bank_type, _new_bank_id, new_bank = find_owner(new_units, "money_account")
    _old_player_type, _old_player_id, old_player = find_owner(old_units, "trucks")
    _new_player_type, _new_player_id, new_player = find_owner(new_units, "trucks")
    _old_offer_type, _old_offer_id, _old_offers = find_owner(old_units, "drivers_offer")
    _new_offer_type, _new_offer_id, new_offers = find_owner(new_units, "drivers_offer")

    old_money = int(scalar(old_bank, "money_account"))
    new_money = int(scalar(new_bank, "money_account"))
    _old_economy_type, _old_economy_id, old_economy = find_owner(
        old_units, "trucks_bought_online"
    )
    _new_economy_type, _new_economy_id, new_economy = find_owner(
        new_units, "trucks_bought_online"
    )
    old_online_purchases = int(scalar(old_economy, "trucks_bought_online"))
    new_online_purchases = int(scalar(new_economy, "trucks_bought_online"))
    new_profit_events = unique_new_profit_events(old_units, new_units)
    employee_profit = sum(profit_entry_net(body) for body in new_profit_events)
    newly_booked_fines = max(
        0, active_job_fines(new_delivery) - active_job_fines(old_delivery)
    )
    reconciled_balance = (
        old_money - args.expected_cost + employee_profit - newly_booked_fines
    )
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

    target_indexes = changed_slot_indexes(old_target, new_target)
    target_vehicle_ids = [new_target["vehicles"][index] for index in target_indexes]
    target_driver_ids = [new_target["drivers"][index] for index in target_indexes]
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
        "active_delivery_and_vehicle_preserved": active_delivery_preserved(
            old_delivery, new_delivery
        ),
        "company_balance_reconciled": new_money == reconciled_balance,
        "online_truck_purchase_counter_increased": new_online_purchases
        == old_online_purchases + args.count,
        "company_truck_count_increased": len(new_trucks) == len(old_trucks) + args.count,
        "company_driver_count_increased": len(new_drivers) == len(old_drivers) + args.count,
        "exactly_one_garage_changed": len(changed) == 1,
        "target_was_completely_empty": len(old_target["vehicles"]) >= args.count
        and all(value == "null" for value in old_target["vehicles"])
        and all(value == "null" for value in old_target["drivers"]),
        "target_received_exact_batch": len(target_indexes) == args.count
        and all(
            old_target["vehicles"][index] == "null"
            and old_target["drivers"][index] == "null"
            and new_target["vehicles"][index] != "null"
            and new_target["drivers"][index] != "null"
            for index in target_indexes
        ),
        "unchanged_target_slots_preserved": all(
            old_target["vehicles"][index] == new_target["vehicles"][index]
            and old_target["drivers"][index] == new_target["drivers"][index]
            for index in range(len(old_target["vehicles"]))
            if index not in target_indexes
        ),
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
            "batch_cost": args.expected_cost,
            "employee_profit_during_run": employee_profit,
            "newly_booked_active_job_fines": newly_booked_fines,
            "reconciled_after": reconciled_balance,
        },
        "new_employee_profit_events": len(new_profit_events),
        "online_truck_purchases": {
            "before": old_online_purchases,
            "after": new_online_purchases,
        },
        "company_trucks": {"before": len(old_trucks), "after": len(new_trucks)},
        "company_drivers": {"before": len(old_drivers), "after": len(new_drivers)},
        "garage_before": old_target,
        "garage_after": new_target,
        "changed_slot_indexes": target_indexes,
        "new_trucks": vehicles,
        "new_drivers": drivers,
        "preexisting_vehicles_compared": compared_preexisting_vehicles,
        "active_delivery": {
            "before": active_delivery_summary(old_delivery),
            "after": active_delivery_summary(new_delivery),
        },
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
