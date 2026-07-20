"""Verify one ETS2 hire by comparing two decoded plaintext save copies."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


UNIT_PATTERN = re.compile(r"(?ms)^(\w+) : ([^\s]+) \{\n(.*?)^\}")


def parse_units(text: str) -> list[tuple[str, str, str]]:
    return [match.groups() for match in UNIT_PATTERN.finditer(text)]


def scalar(body: str, name: str) -> str:
    match = re.search(rf"(?m)^ {re.escape(name)}: (.+)$", body)
    if not match:
        raise ValueError(f"Missing scalar {name!r}")
    return match.group(1)


def array(body: str, name: str) -> list[str]:
    count = int(scalar(body, name))
    values = re.findall(rf"(?m)^ {re.escape(name)}\[(\d+)\]: (.+)$", body)
    ordered = [value for _index, value in sorted(values, key=lambda item: int(item[0]))]
    if len(ordered) != count:
        raise ValueError(f"Array {name!r} declared {count}, decoded {len(ordered)}")
    return ordered


def find_unit(units: list[tuple[str, str, str]], unit_type: str, unit_id: str) -> str:
    for candidate_type, candidate_id, body in units:
        if candidate_type == unit_type and candidate_id == unit_id:
            return body
    raise ValueError(f"Missing unit {unit_type} : {unit_id}")


def find_owner(
    units: list[tuple[str, str, str]], field_name: str
) -> tuple[str, str, str]:
    for unit_type, unit_id, body in units:
        if re.search(rf"(?m)^ {re.escape(field_name)}: ", body):
            return unit_type, unit_id, body
    raise ValueError(f"No unit containing {field_name!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--garage", required=True)
    parser.add_argument("--slot", type=int, required=True, help="One-based garage slot")
    parser.add_argument("--expected-cost", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old_units = parse_units(args.old.read_text(encoding="utf-8", errors="replace"))
    new_units = parse_units(args.new.read_text(encoding="utf-8", errors="replace"))
    old_bank_type, old_bank_id, old_bank = find_owner(old_units, "money_account")
    new_bank_type, new_bank_id, new_bank = find_owner(new_units, "money_account")
    old_player_type, old_player_id, old_player = find_owner(old_units, "drivers")
    new_player_type, new_player_id, new_player = find_owner(new_units, "drivers")
    old_offer_type, old_offer_id, old_offer_owner = find_owner(
        old_units, "drivers_offer"
    )
    new_offer_type, new_offer_id, new_offer_owner = find_owner(
        new_units, "drivers_offer"
    )
    old_garage = find_unit(old_units, "garage", f"garage.{args.garage}")
    new_garage = find_unit(new_units, "garage", f"garage.{args.garage}")

    old_money = int(scalar(old_bank, "money_account"))
    new_money = int(scalar(new_bank, "money_account"))
    old_drivers = array(old_player, "drivers")
    new_drivers = array(new_player, "drivers")
    old_offers = array(old_offer_owner, "drivers_offer")
    new_offers = array(new_offer_owner, "drivers_offer")
    old_slots = array(old_garage, "drivers")
    new_slots = array(new_garage, "drivers")
    slot_index = args.slot - 1
    if not 0 <= slot_index < len(new_slots):
        raise ValueError(f"Slot {args.slot} is outside garage capacity {len(new_slots)}")
    hired_driver = new_slots[slot_index]

    checks = {
        # _nameless object IDs are regenerated on a normal save.  Their unit
        # types, not the ephemeral IDs, are the stable structural identity.
        "bank_unit_type_stable": old_bank_type == new_bank_type,
        "player_unit_type_stable": old_player_type == new_player_type,
        "offer_owner_unit_type_stable": old_offer_type == new_offer_type,
        "target_slot_was_free": old_slots[slot_index] == "null",
        "target_slot_now_has_driver": hired_driver != "null",
        "other_garage_slots_unchanged": all(
            old_value == new_value
            for index, (old_value, new_value) in enumerate(zip(old_slots, new_slots))
            if index != slot_index
        ),
        "driver_count_increased_by_one": len(new_drivers) == len(old_drivers) + 1,
        "driver_added_to_company": hired_driver in new_drivers and hired_driver not in old_drivers,
        "driver_removed_from_offers": hired_driver in old_offers and hired_driver not in new_offers,
        "money_deducted_exactly": old_money - new_money == args.expected_cost,
    }

    driver_body = find_unit(new_units, "driver_ai", hired_driver)
    hometown = scalar(driver_body, "hometown").strip('"')
    current_city = scalar(driver_body, "current_city").strip('"')
    checks["driver_hometown_matches_garage"] = hometown == args.garage
    checks["driver_current_city_matches_garage"] = current_city == args.garage

    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "garage": args.garage,
        "slot": args.slot,
        "hired_driver_id": hired_driver,
        "money": {
            "before": old_money,
            "after": new_money,
            "deducted": old_money - new_money,
        },
        "company_driver_count": {
            "before": len(old_drivers),
            "after": len(new_drivers),
        },
        "driver_offers_count": {
            "before": len(old_offers),
            "after": len(new_offers),
        },
        "garage_driver_slots": {
            "before": old_slots,
            "after": new_slots,
        },
        "driver_location": {
            "hometown": hometown,
            "current_city": current_city,
        },
        "source_files": {
            "before": str(args.old.resolve()),
            "after": str(args.new.resolve()),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"VERIFY_HIRE_REPORT: {args.output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
