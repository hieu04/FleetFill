"""Verify a batch of drivers hired into existing ETS2 truck slots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_driver_truck_pair_save import accessory_paths, occupancy
from verify_hire_save import array, find_owner, find_unit, parse_units, scalar


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--garage", required=True)
    parser.add_argument("--slots", type=int, nargs="+", required=True)
    parser.add_argument("--expected-cost", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old_units = parse_units(args.old.read_text(encoding="utf-8", errors="replace"))
    new_units = parse_units(args.new.read_text(encoding="utf-8", errors="replace"))
    old_bank_type, _old_bank_id, old_bank = find_owner(old_units, "money_account")
    new_bank_type, _new_bank_id, new_bank = find_owner(new_units, "money_account")
    old_player_type, _old_player_id, old_player = find_owner(old_units, "drivers")
    new_player_type, _new_player_id, new_player = find_owner(new_units, "drivers")
    _old_offer_type, _old_offer_id, old_offer_owner = find_owner(old_units, "drivers_offer")
    _new_offer_type, _new_offer_id, new_offer_owner = find_owner(new_units, "drivers_offer")
    garage_id = f"garage.{args.garage}"
    old_garage = find_unit(old_units, "garage", garage_id)
    new_garage = find_unit(new_units, "garage", garage_id)

    old_money = int(scalar(old_bank, "money_account"))
    new_money = int(scalar(new_bank, "money_account"))
    old_company_drivers = array(old_player, "drivers")
    new_company_drivers = array(new_player, "drivers")
    old_company_trucks = array(old_player, "trucks")
    new_company_trucks = array(new_player, "trucks")
    new_offers = array(new_offer_owner, "drivers_offer")
    old_driver_slots = array(old_garage, "drivers")
    new_driver_slots = array(new_garage, "drivers")
    old_vehicle_slots = array(old_garage, "vehicles")
    new_vehicle_slots = array(new_garage, "vehicles")
    indexes = [slot - 1 for slot in args.slots]
    if len(set(indexes)) != len(indexes):
        raise ValueError("--slots must not contain duplicates")
    if any(index < 0 or index >= len(new_driver_slots) for index in indexes):
        raise ValueError(f"A requested slot is outside garage capacity {len(new_driver_slots)}")

    hired_ids = [new_driver_slots[index] for index in indexes]
    added_company_drivers = sorted(set(new_company_drivers) - set(old_company_drivers))
    old_vehicle_occupancy = occupancy(old_units, "vehicles")
    new_vehicle_occupancy = occupancy(new_units, "vehicles")
    old_driver_occupancy = occupancy(old_units, "drivers")
    new_driver_occupancy = occupancy(new_units, "drivers")
    driver_occupancy_delta = {
        garage: sum(new_driver_occupancy[garage]) - sum(shape)
        for garage, shape in old_driver_occupancy.items()
        if sum(new_driver_occupancy[garage]) != sum(shape)
    }

    driver_details = []
    for slot, driver_id in zip(args.slots, hired_ids):
        body = find_unit(new_units, "driver_ai", driver_id)
        driver_details.append(
            {
                "slot": slot,
                "driver_id": driver_id,
                "hometown": scalar(body, "hometown").strip('"'),
                "current_city": scalar(body, "current_city").strip('"'),
            }
        )

    paired_configurations = []
    for slot, index in zip(args.slots, indexes):
        before_paths = accessory_paths(old_units, old_vehicle_slots[index])
        after_paths = accessory_paths(new_units, new_vehicle_slots[index])
        paired_configurations.append(
            {
                "slot": slot,
                "before_vehicle_id": old_vehicle_slots[index],
                "after_vehicle_id": new_vehicle_slots[index],
                "accessory_count": len(after_paths),
                "preserved": before_paths == after_paths,
            }
        )

    checks = {
        "bank_unit_type_stable": old_bank_type == new_bank_type,
        "player_unit_type_stable": old_player_type == new_player_type,
        "money_deducted_exactly": old_money - new_money == args.expected_cost,
        "company_driver_count_increased_by_batch": len(new_company_drivers)
        == len(old_company_drivers) + len(indexes),
        "company_truck_count_unchanged": len(new_company_trucks) == len(old_company_trucks),
        "target_driver_slots_were_free": all(old_driver_slots[index] == "null" for index in indexes),
        "target_driver_slots_now_have_unique_drivers": all(value != "null" for value in hired_ids)
        and len(set(hired_ids)) == len(hired_ids),
        "new_company_driver_set_matches_target_slots": added_company_drivers == sorted(hired_ids),
        "hired_drivers_removed_from_final_offers": all(driver_id not in new_offers for driver_id in hired_ids),
        "other_target_garage_driver_slots_unchanged": all(
            old_value == new_value
            for index, (old_value, new_value) in enumerate(zip(old_driver_slots, new_driver_slots))
            if index not in indexes
        ),
        "all_garage_vehicle_occupancy_unchanged": old_vehicle_occupancy == new_vehicle_occupancy,
        "only_target_garage_driver_occupancy_increased": driver_occupancy_delta
        == {garage_id: len(indexes)},
        "all_paired_truck_configurations_preserved": all(
            pair["preserved"] for pair in paired_configurations
        ),
        "all_driver_hometowns_match_garage": all(
            driver["hometown"] == args.garage for driver in driver_details
        ),
        "all_driver_current_cities_match_garage": all(
            driver["current_city"] == args.garage for driver in driver_details
        ),
    }
    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "garage": args.garage,
        "slots": args.slots,
        "money": {"before": old_money, "after": new_money, "deducted": old_money - new_money},
        "company_driver_count": {"before": len(old_company_drivers), "after": len(new_company_drivers)},
        "company_truck_count": {"before": len(old_company_trucks), "after": len(new_company_trucks)},
        "garage_driver_slots": {"before": old_driver_slots, "after": new_driver_slots},
        "garage_vehicle_slots": {"before": old_vehicle_slots, "after": new_vehicle_slots},
        "driver_occupancy_delta": driver_occupancy_delta,
        "hired_drivers": driver_details,
        "paired_trucks": paired_configurations,
        "source_files": {"before": str(args.old.resolve()), "after": str(args.new.resolve())},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"VERIFY_DRIVER_BATCH_REPORT: {args.output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
