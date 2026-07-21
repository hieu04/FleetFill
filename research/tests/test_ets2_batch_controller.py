from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from ets2_batch_controller import (  # noqa: E402
    BatchAbort,
    BatchCancelled,
    DRIVER_HIRE_COST_EUR,
    TRUCK_PRICE_EUR,
    GarageState,
    ProbeRunner,
    build_parser,
    expected_state_arguments,
    run_driver_phase,
    run_fill_phase,
    run_plan,
    run_live,
    run_truck_phase,
    validate_company_preflight,
)


class CooperativeCancellationTests(unittest.TestCase):
    def test_live_controller_refuses_steam_cloud_profile_before_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "227300" / "remote" / "profiles" / "MAIN"
            (profile / "save" / "autosave").mkdir(parents=True)
            (profile / "profile.sii").write_text("profile", encoding="utf-8")
            run_dir = root / "run"
            args = build_parser().parse_args(
                [
                    "fill", "--execute", "--profile", str(profile),
                    "--occupied", "0", "--truck-present", "0", "--free", "5",
                    "--count", "1", "--start-stage", "home", "--dynamic-garage",
                    "--output-dir", str(run_dir),
                ]
            )
            output = io.StringIO()
            with redirect_stdout(output):
                result = run_live(args)

        self.assertEqual(result, 2)
        self.assertIn("Steam Cloud profiles require", output.getvalue())
        self.assertFalse(run_dir.exists())

    def test_probe_runner_stops_before_spawning_next_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cancel = root / "cancel.requested"
            cancel.touch()
            runner = ProbeRunner(root, root / "run", 0.0, 1.0, cancel)
            with self.assertRaisesRegex(BatchCancelled, "before guarded step 1"):
                runner.run("never", "never.py", [], "NEVER_REPORT")

    def test_live_controller_honors_preexisting_cancel_before_backup_or_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "profile"
            autosave = profile / "save" / "autosave"
            autosave.mkdir(parents=True)
            (autosave / "game.sii").write_text("test", encoding="utf-8")
            run_dir = root / "run"
            run_dir.mkdir()
            cancel = run_dir / "cancel.requested"
            cancel.touch()
            args = build_parser().parse_args(
                [
                    "fill", "--execute", "--profile", str(profile),
                    "--occupied", "0", "--truck-present", "0", "--free", "5",
                    "--count", "1", "--start-stage", "home", "--dynamic-garage",
                    "--output-dir", str(run_dir), "--cancel-file", str(cancel),
                ]
            )
            output = io.StringIO()
            with redirect_stdout(output):
                result = run_live(args)
        self.assertEqual(result, 2)
        self.assertIn("BATCH_CANCELLED", output.getvalue())
        self.assertFalse((run_dir / "preflight-backup").exists())


class FakeRunner:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.steps = []
        self.calls = []
        self.current_state = None

    def run(self, label, script, arguments, report_prefix, **_kwargs):
        self.calls.append((label, script, list(arguments), report_prefix))
        if report_prefix == "DEALER_BRAND_PROBE_REPORT":
            return {"detected_available_dealers": [{"center": [1505, 187]}]}
        if report_prefix in {
            "TRUCK_SLOT_PROBE_REPORT",
            "DRIVER_TO_TRUCK_SLOT_REPORT",
        }:
            return {"after": {"screenshot": "verified-identity.png"}}
        if report_prefix == "FIND_CAPACITY_GARAGE_REPORT":
            hiring = "hire" in arguments
            return {
                "found": {
                    "target_position": [1260, 186],
                    "slot_counts": {
                        "occupied": 0,
                        "truck_present": 5 if hiring else 0,
                        "free": 0 if hiring else 5,
                    },
                }
            }
        return {}


class AckFailRunner(FakeRunner):
    def run(self, label, script, arguments, report_prefix, **kwargs):
        if script == "ets2_ui_ack_purchase_prompt_probe.py":
            raise BatchAbort("simulated acknowledgement failure")
        return super().run(label, script, arguments, report_prefix, **kwargs)


class PannedFallbackRunner(FakeRunner):
    def run(self, label, script, arguments, report_prefix, **kwargs):
        if report_prefix == "FIND_CAPACITY_GARAGE_REPORT":
            self.calls.append((label, script, list(arguments), report_prefix))
            return {"found": None}
        if report_prefix == "FIND_AFTER_PAN_REPORT":
            self.calls.append((label, script, list(arguments), report_prefix))
            hiring = "hire" in arguments
            return {
                "found": {
                    "target_position": [1427, 261],
                    "slot_counts": {
                        "occupied": 0,
                        "truck_present": 5 if hiring else 0,
                        "free": 0 if hiring else 5,
                    },
                },
                "locator": {
                    "pan_path": [
                        {
                            "button": "right",
                            "start": [1380, 610],
                            "end": [1080, 610],
                            "observed_translation": {
                                "dx": -302,
                                "dy": 0,
                                "matched_markers": 11,
                            },
                        }
                    ],
                    "marker_position": [1427, 261],
                    "slot_counts": {
                        "occupied": 0,
                        "truck_present": 5 if hiring else 0,
                        "free": 0 if hiring else 5,
                    },
                },
            }
        return super().run(label, script, arguments, report_prefix, **kwargs)


class NoVisibleDealerRunner(FakeRunner):
    def run(self, label, script, arguments, report_prefix, **kwargs):
        if report_prefix == "DEALER_BRAND_PROBE_REPORT":
            self.calls.append((label, script, list(arguments), report_prefix))
            return {"detected_available_dealers": []}
        return super().run(label, script, arguments, report_prefix, **kwargs)


def live_args(phase: str, count: int, state: GarageState) -> SimpleNamespace:
    return SimpleNamespace(
        phase=phase,
        count=count,
        card=1,
        garage_x=1120,
        garage_y=206,
        garage_label="Reims",
        start_stage="dealer-map" if phase == "trucks" else "driver-list",
        initial_card_selected=False,
        dynamic_garage=False,
        require_empty_garage=False,
        occupied=state.occupied,
        truck_present=state.truck_present,
        free=state.free,
    )


class GarageStateTests(unittest.TestCase):
    def test_reims_finish_plan(self):
        state = GarageState(occupied=1, truck_present=1, free=3)
        for _ in range(3):
            state = state.buy_truck()
        self.assertEqual(state, GarageState(occupied=1, truck_present=4, free=0))
        for _ in range(4):
            state = state.hire_driver()
        self.assertEqual(state, GarageState(occupied=5, truck_present=0, free=0))

    def test_rejects_invalid_capacity(self):
        with self.assertRaises(ValueError):
            GarageState(occupied=1, truck_present=1, free=2)

    def test_rejects_truck_overfill(self):
        with self.assertRaises(ValueError):
            GarageState(occupied=5, truck_present=0, free=0).buy_truck()

    def test_rejects_hire_without_waiting_truck(self):
        with self.assertRaises(ValueError):
            GarageState(occupied=2, truck_present=0, free=3).hire_driver()

    def test_expected_fingerprint_arguments(self):
        self.assertEqual(
            expected_state_arguments(GarageState(1, 2, 2)),
            [
                "--expected-occupied",
                "1",
                "--expected-truck-present",
                "2",
                "--expected-free",
                "2",
            ],
        )


class CompanyPreflightTests(unittest.TestCase):
    def company(self, *, money: int = 2_000_000, empty: bool = True) -> dict:
        return {
            "money_eur": money,
            "large_garages": [
                {
                    "id": "garage.test",
                    "occupied": 0 if empty else 1,
                    "truck_present": 0,
                    "free": 5 if empty else 4,
                    "invalid_driver_only": 0,
                }
            ],
        }

    def test_accepts_affordable_batch_with_empty_large_garage(self) -> None:
        result = validate_company_preflight(self.company(), 5)
        self.assertEqual(result["planned_cost_eur"], 1_249_925)
        self.assertEqual(result["empty_large_garages"], ["garage.test"])

    def test_rejects_insufficient_balance(self) -> None:
        with self.assertRaisesRegex(BatchAbort, "Insufficient company balance"):
            validate_company_preflight(self.company(money=1_000_000), 5)

    def test_rejects_save_without_empty_large_garage(self) -> None:
        with self.assertRaisesRegex(BatchAbort, "no completely empty"):
            validate_company_preflight(self.company(empty=False), 1)


class PhaseCompositionTests(unittest.TestCase):
    def test_truck_phase_composes_proven_probes(self):
        initial = GarageState(1, 1, 3)
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_truck_phase(runner, live_args("trucks", 3, initial), initial)
        self.assertEqual(final, GarageState(1, 4, 0))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts.count("ets2_ui_confirm_truck_purchase_probe.py"), 3)
        self.assertEqual(scripts.count("ets2_ui_ack_purchase_prompt_probe.py"), 3)
        self.assertEqual(scripts[-1], "ets2_ui_ack_purchase_prompt_probe.py")

    def test_truck_phase_can_resume_after_scania_selection(self):
        initial = GarageState(1, 1, 3)
        args = live_args("trucks", 1, initial)
        args.start_stage = "scania-selected"
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_truck_phase(runner, args, initial)
        self.assertEqual(final, GarageState(1, 2, 2))
        scripts = [call[1] for call in runner.calls]
        self.assertNotIn("ets2_ui_dealer_brand_probe.py", scripts)
        self.assertEqual(scripts[0], "ets2_ui_dealer_marker_probe.py")

    def test_truck_phase_can_start_from_home(self):
        initial = GarageState(1, 1, 3)
        args = live_args("trucks", 1, initial)
        args.start_stage = "home"
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_truck_phase(runner, args, initial)
        self.assertEqual(final, GarageState(1, 2, 2))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts[0], "ets2_ui_open_service_destination_probe.py")
        self.assertEqual(runner.calls[0][2], ["--destination", "truck_dealers"])

    def test_truck_phase_pans_when_filtered_dealer_is_not_visible(self):
        initial = GarageState(1, 1, 3)
        args = live_args("trucks", 1, initial)
        with tempfile.TemporaryDirectory() as temp:
            runner = NoVisibleDealerRunner(Path(temp))
            final = run_truck_phase(runner, args, initial)
        self.assertEqual(final, GarageState(1, 2, 2))
        scripts = [call[1] for call in runner.calls]
        self.assertIn("ets2_ui_dealer_filtered_pan_probe.py", scripts)
        self.assertNotIn("ets2_ui_dealer_marker_probe.py", scripts)
        self.assertLess(
            scripts.index("ets2_ui_dealer_filtered_pan_probe.py"),
            scripts.index("ets2_ui_open_online_purchase_probe.py"),
        )

    def test_truck_phase_verifies_persisted_card_selection(self):
        initial = GarageState(1, 2, 2)
        args = live_args("trucks", 2, initial)
        args.start_stage = "fleet-configurations"
        args.initial_card_selected = True
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_truck_phase(runner, args, initial)
        self.assertEqual(final, GarageState(1, 4, 0))
        scripts = [call[1] for call in runner.calls]
        self.assertNotIn("ets2_ui_fleet_truck_select_probe.py", scripts)
        self.assertEqual(
            scripts.count("ets2_ui_verify_selected_fleet_truck.py"), 2
        )

    def test_truck_phase_discovers_then_reuses_dynamic_garage(self):
        initial = GarageState(0, 0, 5)
        args = live_args("trucks", 2, initial)
        args.dynamic_garage = True
        args.garage_x = None
        args.garage_y = None
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_truck_phase(runner, args, initial)
        self.assertEqual(final, GarageState(0, 2, 3))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts.count("ets2_ui_find_capacity_garage_probe.py"), 1)
        self.assertEqual(scripts.count("ets2_ui_reselect_truck_garage_probe.py"), 1)
        self.assertEqual((args.garage_x, args.garage_y), (1260, 186))

    def test_validation_discovery_explicitly_requires_all_five_free_slots(self):
        initial = GarageState(0, 0, 5)
        args = live_args("trucks", 1, initial)
        args.dynamic_garage = True
        args.require_empty_garage = True
        args.garage_x = None
        args.garage_y = None
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            run_truck_phase(runner, args, initial)
        discovery = next(
            call for call in runner.calls
            if call[1] == "ets2_ui_find_capacity_garage_probe.py"
        )
        self.assertEqual(
            discovery[2][discovery[2].index("--required") + 1], "5"
        )

    def test_truck_phase_falls_back_to_pan_and_replays_locator(self):
        initial = GarageState(0, 0, 5)
        args = live_args("trucks", 2, initial)
        args.dynamic_garage = True
        args.garage_x = None
        args.garage_y = None
        with tempfile.TemporaryDirectory() as temp:
            runner = PannedFallbackRunner(Path(temp))
            final = run_truck_phase(runner, args, initial)
            locator_path = Path(args.garage_locator_report)
            self.assertTrue(locator_path.is_file())
        self.assertEqual(final, GarageState(0, 2, 3))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts.count("ets2_ui_find_after_pan_probe.py"), 1)
        self.assertEqual(scripts.count("ets2_ui_replay_pan_locator_probe.py"), 1)
        replay = next(
            call for call in runner.calls
            if call[1] == "ets2_ui_replay_pan_locator_probe.py"
        )
        self.assertIn("--expected-truck-present", replay[2])
        self.assertEqual(
            replay[2][replay[2].index("--expected-truck-present") + 1], "1"
        )

    def test_driver_phase_composes_proven_probes(self):
        initial = GarageState(1, 4, 0)
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_driver_phase(runner, live_args("drivers", 4, initial), initial)
        self.assertEqual(final, GarageState(5, 0, 0))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts.count("ets2_ui_confirm_driver_to_truck_probe.py"), 4)
        self.assertEqual(scripts.count("ets2_ui_driver_to_truck_slot_probe.py"), 4)

    def test_driver_phase_can_start_from_home(self):
        initial = GarageState(1, 4, 0)
        args = live_args("drivers", 1, initial)
        args.start_stage = "home"
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_driver_phase(runner, args, initial)
        self.assertEqual(final, GarageState(2, 3, 0))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts[0], "ets2_ui_open_service_destination_probe.py")
        self.assertEqual(scripts[1], "ets2_ui_open_hire_driver_probe.py")
        self.assertEqual(runner.calls[0][2], ["--destination", "recruitment_agency"])

    def test_driver_phase_discovers_then_reuses_dynamic_garage(self):
        initial = GarageState(0, 5, 0)
        args = live_args("drivers", 5, initial)
        args.dynamic_garage = True
        args.garage_x = None
        args.garage_y = None
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_driver_phase(runner, args, initial)
        self.assertEqual(final, GarageState(5, 0, 0))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts.count("ets2_ui_find_capacity_garage_probe.py"), 1)
        self.assertEqual(scripts.count("ets2_ui_reselect_hire_garage_probe.py"), 4)
        self.assertEqual((args.garage_x, args.garage_y), (1260, 186))

    def test_driver_phase_falls_back_to_pan_and_replays_locator(self):
        initial = GarageState(0, 5, 0)
        args = live_args("drivers", 2, initial)
        args.dynamic_garage = True
        args.garage_x = None
        args.garage_y = None
        with tempfile.TemporaryDirectory() as temp:
            runner = PannedFallbackRunner(Path(temp))
            final = run_driver_phase(runner, args, initial)
        self.assertEqual(final, GarageState(2, 3, 0))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts.count("ets2_ui_find_after_pan_probe.py"), 1)
        self.assertEqual(scripts.count("ets2_ui_replay_pan_locator_probe.py"), 1)
        replay = next(
            call for call in runner.calls
            if call[1] == "ets2_ui_replay_pan_locator_probe.py"
        )
        self.assertEqual(
            replay[2][replay[2].index("--expected-occupied") + 1], "1"
        )

    def test_confirmed_truck_is_checkpointed_before_acknowledgement(self):
        initial = GarageState(1, 1, 3)
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            runner = AckFailRunner(run_dir)
            with self.assertRaises(BatchAbort):
                run_truck_phase(runner, live_args("trucks", 1, initial), initial)
            checkpoint = __import__("json").loads(
                (run_dir / "batch-report.json").read_text(encoding="utf-8")
            )
        self.assertEqual(
            checkpoint["garage"]["state"],
            {"occupied": 1, "truck_present": 2, "free": 2},
        )
        self.assertEqual(runner.current_state, GarageState(1, 2, 2))

    def test_fill_phase_reuses_one_dynamic_garage_for_trucks_and_drivers(self):
        initial = GarageState(0, 0, 5)
        args = live_args("fill", 5, initial)
        args.dynamic_garage = True
        args.garage_x = None
        args.garage_y = None
        args.start_stage = "home"
        with tempfile.TemporaryDirectory() as temp:
            runner = FakeRunner(Path(temp))
            final = run_fill_phase(runner, args, initial)
        self.assertEqual(final, GarageState(5, 0, 0))
        scripts = [call[1] for call in runner.calls]
        self.assertEqual(scripts.count("ets2_ui_find_capacity_garage_probe.py"), 1)
        self.assertEqual(scripts.count("ets2_ui_confirm_truck_purchase_probe.py"), 5)
        self.assertEqual(scripts.count("ets2_ui_confirm_driver_to_truck_probe.py"), 5)
        self.assertEqual(scripts.count("ets2_ui_return_home_probe.py"), 1)
        self.assertEqual(scripts.count("ets2_ui_reselect_truck_garage_probe.py"), 4)
        self.assertEqual(scripts.count("ets2_ui_reselect_hire_garage_probe.py"), 5)

    def test_fill_phase_replays_panned_garage_across_both_phases(self):
        initial = GarageState(0, 0, 5)
        args = live_args("fill", 2, initial)
        args.dynamic_garage = True
        args.garage_x = None
        args.garage_y = None
        args.start_stage = "home"
        with tempfile.TemporaryDirectory() as temp:
            runner = PannedFallbackRunner(Path(temp))
            final = run_fill_phase(runner, args, initial)
        self.assertEqual(final, GarageState(2, 0, 3))
        replays = [
            call for call in runner.calls
            if call[1] == "ets2_ui_replay_pan_locator_probe.py"
        ]
        self.assertEqual(len(replays), 3)
        self.assertEqual(
            sum("truck" in call[2] for call in replays),
            1,
        )
        self.assertEqual(
            sum("hire" in call[2] for call in replays),
            2,
        )


class PlanCommandTests(unittest.TestCase):
    def test_plan_reports_cost_and_final_state(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "plan",
                "--occupied",
                "1",
                "--truck-present",
                "1",
                "--free",
                "3",
                "--trucks",
                "3",
                "--drivers",
                "4",
            ]
        )
        output = io.StringIO()
        with redirect_stdout(output):
            result = run_plan(args)
        self.assertEqual(result, 0)
        payload = __import__("json").loads(output.getvalue())
        self.assertEqual(payload["final"], {"occupied": 5, "truck_present": 0, "free": 0})
        self.assertEqual(
            payload["expected_spend_eur"],
            3 * TRUCK_PRICE_EUR + 4 * DRIVER_HIRE_COST_EUR,
        )

    def test_live_truck_parser_rejects_unverified_card(self):
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "trucks",
                    "--garage-x",
                    "1120",
                    "--garage-y",
                    "206",
                    "--occupied",
                    "1",
                    "--truck-present",
                    "1",
                    "--free",
                    "3",
                    "--count",
                    "1",
                    "--card",
                    "2",
                ]
            )

    def test_fill_parser_accepts_guarded_home_workflow(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "fill",
                "--occupied",
                "0",
                "--truck-present",
                "0",
                "--free",
                "5",
                "--count",
                "5",
                "--dynamic-garage",
            ]
        )
        self.assertEqual(args.phase, "fill")
        self.assertEqual(args.start_stage, "home")
        self.assertTrue(args.dynamic_garage)


if __name__ == "__main__":
    unittest.main()
