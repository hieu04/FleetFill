# FleetFill

FleetFill is an experimental Windows automation tool for Euro Truck Simulator 2
company management. Its goal is to fill a garage in one guarded operation:
purchase matching trucks, hire available drivers, and assign both to the same
garage.

The repository contains the proven automation engine, its research tools, and
the first functional FleetFill desktop shell. Normal app launches cannot start
live game input. A separate, visibly armed developer launcher is restricted to
the first one-truck/one-driver validation on the disposable test career. The
Windows installer has not been built.

For the chronological build story, see
[`docs/development-process.md`](docs/development-process.md).

## Current status

The unified workflow has completed one real end-to-end run on ETS2 1.60 using
the following calibrated environment:

- English UI
- 1920x1080 exclusive fullscreen
- Windows display scaling at 100%
- Mouse and keyboard menu navigation
- Local single-player profile with Steam Cloud and World of Trucks disconnected
- Saved fleet configuration card 1: Scania Streamline Topline, EUR 248,485

That live run dynamically selected an empty garage, purchased five matching
trucks, returned through the main menu, opened recruitment, and hired five
drivers into the same garage. An independent before/after save audit verified
the exact money change, five new trucks, five new drivers, unchanged unrelated
garages, and preserved configurations for all pre-existing trucks.

The desktop validation boundary has also completed its first real 1+1 run. The
armed app selected an empty Salzburg garage, bought one truck, hired one driver,
and completed all 19 guarded UI steps. The post-exit audit verified the exact
EUR 249,985 deduction, fleet and driver increases from 138 to 139, one paired
garage slot change, and preservation of all 138 pre-existing truck
configurations and every unrelated garage.

This is still a calibrated prototype. It should not be treated as compatible
with other ETS2 versions, resolutions, UI languages, truck cards, or profiles
until those combinations have their own recognition evidence and tests.

## How it works

FleetFill is a guarded visual state machine, not a save editor and not a game
memory hook.

1. It captures the current fullscreen image directly with Pillow.
2. Each narrow probe recognizes one expected ETS2 screen using fixed regions,
   color/shape measurements, and reference-image distances.
3. A probe sends at most the mouse action it owns, then captures again and
   verifies the resulting screen.
4. The batch controller advances only after the probe writes verifiable JSON
   evidence. Unexpected screens, slot states, prompts, or marker identities
   abort the run.
5. Garage and dealer markers are detected visually. When a useful marker is not
   visible, the controller can pan the map and replay the measured locator.
6. Before a live batch, the controller copies the disposable profile's autosave
   and `profile.sii` into the local run evidence directory.
7. Separate read-only save inspection tools can compare before/after saves to
   confirm the game persisted exactly the intended company changes.

The controller composes many deliberately small probes rather than placing all
mouse clicks in one long macro. This makes each transition independently
checkable and gives the automation a safe place to stop.

## Repository layout

```text
research/tools/ets2_batch_controller.py   Unified truck/driver orchestrator
research/tools/ets2_ui_*_probe.py         Screen-specific guarded actions
research/tools/ets2_*_icon_detector.py    Garage and dealer visual detection
research/tools/verify_*_save.py           Read-only save verification
research/tools/save-inspector/            BSII save decoding helper
research/tests/                            Controller and save-audit tests
research/ui-first-findings.md              Research notes and decisions
research/output/                           Local evidence; ignored by Git
```

## Development setup

Use Python 3.12 on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install --no-deps --editable .
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest discover -s research\tests -p "test_*.py" -v
```

Launch the current desktop shell:

```powershell
.\scripts\run-fleetfill.ps1
```

That normal launcher remains input-locked and offers only the no-input
lifecycle simulator. During supervised development, the deliberately narrow
validation launcher is:

```powershell
.\scripts\run-fleetfill-validation.ps1
```

Validation mode is visibly labelled, forces exactly one slot, requires the
career name `ETS2 Automation Test`, repeats the active local-profile preflight,
requires a completely empty five-slot garage, creates a backup, and retains the
10-second return-to-game countdown. It is not the general one-to-five product
unlock.

The shell uses PySide6 6.10.1 and already provides the approved Setup, History,
and Settings navigation. Setup discovers local ETS2 profiles, prefers the
disposable Automation Test profile, validates the selected autosave, calculates
the exact truck-and-driver estimate, and exposes a guarded review workflow.
Before review, FleetFill now proves from the current `game.log.txt` that ETS2 is
running, the most recently selected career is the chosen profile, its type is
`PC_local`, and the matching local autosave was loaded after selection. A stale
log, cloud career, different folder, or merely highlighted career fails closed.

The Qt process supervisor launches a no-input lifecycle simulator, streams
its output and checkpoint file without freezing the UI, supports cooperative
cancellation, and writes durable History records. The real controller uses the
same cancellation marker between guarded probes. Normal desktop execution is
still centrally locked; only the explicit 1+1 validation launcher can cross the
live boundary.

The save-inspector helper uses Node.js and a pinned dependency:

```powershell
cd research\tools\save-inspector
npm install
```

## Safe controller usage

Planning is read-only and sends no game input:

```powershell
python research\tools\ets2_batch_controller.py plan `
  --occupied 0 --truck-present 0 --free 5 --trucks 5 --drivers 5
```

A live command requires both `--execute` and an explicit disposable local
profile path. Do not point it at an irreplaceable profile. Keep ETS2 at the
tested UI settings and ensure the requested starting screen/state is correct.
The desktop app additionally checks that the exact local career is active; the
profile picker alone does not switch or control the career loaded inside ETS2.
When supplied, `--cancel-file` is checked before every guarded probe. The current
probe is allowed to finish and checkpoint any completed transaction before the
controller stops, avoiding an unsafe mid-click process kill.

## Privacy and source control

Generated screenshots, decoded saves, profile backups, downloaded extractors,
videos, and run evidence are ignored by Git. Review `git status` before every
commit. Never add files from an ETS2 profile or `research/output` to a public
repository.

## Project direction

The deliberately small desktop 1+1 validation has passed both its immediate
runtime checks and independent post-exit save audit. The next engineering gate
is deciding how to graduate that proven boundary into normal one-to-five
execution without weakening the profile, backup, cancellation, or evidence
requirements. Packaging and a Windows installer follow.

FleetFill is an unofficial community project and is not affiliated with SCS
Software. Euro Truck Simulator 2 is a trademark of its respective owner.

## License

FleetFill's original source code is available under the [MIT License](LICENSE).
Its dependencies remain under their respective licenses; see
[Third-party notices](THIRD_PARTY_NOTICES.md). A future packaged Windows release
must also include and comply with the applicable PySide6/Qt LGPLv3 materials.
