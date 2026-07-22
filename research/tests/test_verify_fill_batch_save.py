from __future__ import annotations

import unittest

from verify_fill_batch_save import (
    active_delivery_preserved,
    active_delivery_state,
    changed_slot_indexes,
    profit_entry_net,
    unique_new_profit_events,
)


class FillBatchSlotDiffTests(unittest.TestCase):
    def test_one_plus_one_in_five_slot_garage_changes_one_paired_index(self) -> None:
        before = {
            "vehicles": ["null"] * 5,
            "drivers": ["null"] * 5,
        }
        after = {
            "vehicles": ["vehicle.1", "null", "null", "null", "null"],
            "drivers": ["driver.1", "null", "null", "null", "null"],
        }
        self.assertEqual(changed_slot_indexes(before, after), [0])

    def test_two_plus_two_changes_exactly_two_paired_indexes(self) -> None:
        before = {
            "vehicles": ["null"] * 5,
            "drivers": ["null"] * 5,
        }
        after = {
            "vehicles": ["vehicle.1", "vehicle.2", "null", "null", "null"],
            "drivers": ["driver.1", "driver.2", "null", "null", "null"],
        }
        self.assertEqual(changed_slot_indexes(before, after), [0, 1])

    def test_three_plus_three_changes_exactly_three_paired_indexes(self) -> None:
        before = {
            "vehicles": ["null"] * 5,
            "drivers": ["null"] * 5,
        }
        after = {
            "vehicles": ["vehicle.1", "vehicle.2", "vehicle.3", "null", "null"],
            "drivers": ["driver.1", "driver.2", "driver.3", "null", "null"],
        }
        self.assertEqual(changed_slot_indexes(before, after), [0, 1, 2])

    def test_shape_mismatch_fails_closed(self) -> None:
        before = {"vehicles": ["null"] * 5, "drivers": ["null"] * 5}
        after = {"vehicles": ["vehicle.1"], "drivers": ["driver.1"]}
        self.assertEqual(changed_slot_indexes(before, after), [])


class ActiveDeliveryStateTests(unittest.TestCase):
    def test_world_of_trucks_job_and_parked_vehicle_are_stable(self) -> None:
        units = [
            (
                "economy",
                "_nameless.1",
                " stored_online_job_id: 147617646\n",
            ),
            (
                "player",
                "_nameless.2",
                """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: null
 current_bus_job: null
 selected_job: null
 assigned_truck: null
 truck_placement: (1, 2, 3) (1; 0, 0, 0)
 assigned_trailer: null
 trailer_placement: (4, 5, 6) (1; 0, 0, 0)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0) (1; 0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0) (1; 0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
""",
            ),
        ]
        state = active_delivery_state(units)
        self.assertEqual(state["active_kind"], "world_of_trucks")
        self.assertEqual(state["online_job_id"], "147617646")

    def test_job_or_vehicle_change_is_detected(self) -> None:
        player = """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: _nameless.abc
 current_bus_job: null
 selected_job: null
 assigned_truck: _nameless.def
 truck_placement: (1, 2, 3) (1; 0, 0, 0)
 assigned_trailer: null
 trailer_placement: (4, 5, 6) (1; 0, 0, 0)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0) (1; 0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0) (1; 0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
"""
        before = [
            ("economy", "_nameless.1", " stored_online_job_id: 0\n"),
            ("player", "_nameless.2", player),
            ("job", "_nameless.abc", " cargo: cargo.apples\n deadline: 42\n"),
            ("vehicle", "_nameless.def", " fuel_relative: 1\n"),
        ]
        after = [
            ("economy", "_nameless.9", " stored_online_job_id: 0\n"),
            (
                "player",
                "_nameless.8",
                player.replace("_nameless.abc", "_nameless.123").replace(
                    "_nameless.def", "_nameless.456"
                ),
            ),
            ("job", "_nameless.123", " cargo: cargo.pears\n deadline: 42\n"),
            ("vehicle", "_nameless.456", " fuel_relative: 1\n"),
        ]
        self.assertNotEqual(
            active_delivery_state(before), active_delivery_state(after)
        )

    def test_volatile_object_ids_do_not_create_false_change(self) -> None:
        player = """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: _nameless.abc
 current_bus_job: null
 selected_job: null
 assigned_truck: null
 truck_placement: (1, 2, 3) (1; 0, 0, 0)
 assigned_trailer: null
 trailer_placement: (4, 5, 6) (1; 0, 0, 0)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0) (1; 0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0) (1; 0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
"""
        before = [
            ("economy", "_nameless.1", " stored_online_job_id: 0\n"),
            ("player", "_nameless.2", player),
            (
                "job",
                "_nameless.abc",
                " cargo: cargo.apples\n trailer: _nameless.def\n",
            ),
        ]
        after = [
            ("economy", "_nameless.9", " stored_online_job_id: 0\n"),
            (
                "player",
                "_nameless.8",
                player.replace("_nameless.abc", "_nameless.123"),
            ),
            (
                "job",
                "_nameless.123",
                " cargo: cargo.apples\n trailer: _nameless.456\n",
            ),
        ]
        self.assertEqual(active_delivery_state(before), active_delivery_state(after))

    def test_world_of_trucks_job_may_materialize_on_save(self) -> None:
        player = """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: {job}
 current_bus_job: null
 selected_job: null
 assigned_truck: null
 truck_placement: (1, 2, 3) (1; 0, 0, 0)
 assigned_trailer: null
 trailer_placement: (4, 5, 6) (1; 0, 0, 0)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0) (1; 0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0) (1; 0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
"""
        before = [
            ("economy", "_nameless.1", " stored_online_job_id: 100\n"),
            ("player", "_nameless.2", player.format(job="null")),
        ]
        after = [
            ("economy", "_nameless.3", " stored_online_job_id: 200\n"),
            (
                "player",
                "_nameless.4",
                player.format(job="_nameless.5"),
            ),
            (
                "player_job",
                "_nameless.5",
                """ cargo: cargo.volvo_a25g
 source_company: company.volatile.blt.utena
 target_company: company.volatile.te_logistica.napoli
 total_fines: 2160
 is_trailer_loaded: true
 online_job_id: 200
""",
            ),
        ]
        self.assertTrue(
            active_delivery_preserved(
                active_delivery_state(before), active_delivery_state(after)
            )
        )

    def test_world_of_trucks_materialization_rejects_moved_vehicle(self) -> None:
        units = [
            ("economy", "_nameless.1", " stored_online_job_id: 100\n"),
            (
                "player",
                "_nameless.2",
                """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: null
 current_bus_job: null
 selected_job: null
 assigned_truck: null
 truck_placement: (1, 2, 3) (1; 0, 0, 0)
 assigned_trailer: null
 trailer_placement: (4, 5, 6) (1; 0, 0, 0)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0) (1; 0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0) (1; 0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
""",
            ),
        ]
        before = active_delivery_state(units)
        moved = active_delivery_state(
            [
                units[0],
                (
                    units[1][0],
                    units[1][1],
                    units[1][2].replace("(1, 2, 3)", "(9, 9, 9)"),
                ),
            ]
        )
        self.assertFalse(active_delivery_preserved(before, moved))

    def test_world_of_trucks_progress_may_refresh_on_clean_exit(self) -> None:
        player = """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: _nameless.abc
 current_bus_job: null
 selected_job: null
 assigned_truck: null
 truck_placement: (1, 2, 3) (1; 0, 0, 0)
 assigned_trailer: null
 trailer_placement: (4, 5, 6) (1; 0, 0, 0)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0) (1; 0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0) (1; 0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
"""
        before_job = """ cargo: cargo.volvo_a25g
 source_company: company.volatile.blt.utena
 target_company: company.volatile.te_logistica.napoli
 target_placement_medium: (1, 2, 3)
 target_placement_hard: (0, 0, 0)
 target_placement_rigid: (0, 0, 0)
 job_distance: 205
 fuel_consumed: 108
 last_reported_fuel: 1000
 total_fines: 2160
 is_trailer_loaded: true
 online_job_id: 147630899
"""
        after_job = before_job.replace(
            "target_placement_medium: (1, 2, 3)",
            "target_placement_medium: (0, 0, 0)",
        ).replace(
            "target_placement_hard: (0, 0, 0)",
            "target_placement_hard: (4, 5, 6)",
        ).replace("job_distance: 205", "job_distance: 617").replace(
            "fuel_consumed: 108", "fuel_consumed: 266"
        ).replace("last_reported_fuel: 1000", "last_reported_fuel: 842").replace(
            "total_fines: 2160", "total_fines: 0"
        )
        before = [
            ("economy", "_nameless.1", " stored_online_job_id: 147630899\n"),
            ("player", "_nameless.2", player),
            ("player_job", "_nameless.abc", before_job),
        ]
        after = [
            ("economy", "_nameless.3", " stored_online_job_id: 147630899\n"),
            ("player", "_nameless.4", player.replace(".abc", ".def")),
            ("player_job", "_nameless.def", after_job),
        ]
        self.assertTrue(
            active_delivery_preserved(
                active_delivery_state(before), active_delivery_state(after)
            )
        )

    def test_world_of_trucks_progress_refresh_rejects_route_change(self) -> None:
        units = [
            ("economy", "_nameless.1", " stored_online_job_id: 55\n"),
            (
                "player",
                "_nameless.2",
                """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: _nameless.abc
 current_bus_job: null
 selected_job: null
 assigned_truck: null
 truck_placement: (1, 2, 3)
 assigned_trailer: null
 trailer_placement: (4, 5, 6)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
""",
            ),
            (
                "player_job",
                "_nameless.abc",
                " cargo: cargo.apples\n target_company: company.a\n job_distance: 10\n is_trailer_loaded: true\n online_job_id: 55\n",
            ),
        ]
        before = active_delivery_state(units)
        after = active_delivery_state(
            [
                units[0],
                units[1],
                (
                    "player_job",
                    "_nameless.abc",
                    units[2][2].replace("company.a", "company.b").replace(
                        "job_distance: 10", "job_distance: 20"
                    ),
                ),
            ]
        )
        self.assertFalse(active_delivery_preserved(before, after))

    def test_world_of_trucks_existing_job_requires_same_online_id(self) -> None:
        base = [
            ("economy", "_nameless.1", " stored_online_job_id: 55\n"),
            (
                "player",
                "_nameless.2",
                """ my_vehicles_mode: truck
 assigned_vehicles_mode: truck
 current_job: _nameless.abc
 current_bus_job: null
 selected_job: null
 assigned_truck: null
 truck_placement: (1, 2, 3)
 assigned_trailer: null
 trailer_placement: (4, 5, 6)
 assigned_trailer_connected: true
 my_truck: null
 my_truck_placement: (0, 0, 0)
 my_truck_placement_valid: false
 my_trailer: null
 my_trailer_placement: (0, 0, 0)
 my_trailer_attached: false
 my_trailer_used: false
""",
            ),
            (
                "player_job",
                "_nameless.abc",
                " cargo: cargo.apples\n is_trailer_loaded: true\n online_job_id: 55\n",
            ),
        ]
        changed = [
            (base[0][0], base[0][1], base[0][2].replace("55", "56")),
            base[1],
            (base[2][0], base[2][1], base[2][2].replace("55", "56")),
        ]
        self.assertFalse(
            active_delivery_preserved(
                active_delivery_state(base), active_delivery_state(changed)
            )
        )


class ProfitReconciliationTests(unittest.TestCase):
    def test_new_employee_job_is_counted_once_when_save_duplicates_it(self) -> None:
        entry = """ revenue: 50000
 wage: 30000
 maintenance: 2000
 fuel: 1000
"""
        old_units = [("profit_log_entry", "old", " revenue: 1\n wage: 1\n maintenance: 0\n fuel: 0\n")]
        new_units = old_units + [
            ("profit_log_entry", "copy.1", entry),
            ("profit_log_entry", "copy.2", entry),
            ("profit_log_entry", "copy.3", entry),
        ]
        events = unique_new_profit_events(old_units, new_units)
        self.assertEqual(len(events), 1)
        self.assertEqual(profit_entry_net(events[0]), 17000)


if __name__ == "__main__":
    unittest.main()
