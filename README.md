# FleetFill

FleetFill is an experimental Windows automation tool for Euro Truck Simulator 2
company management. Its goal is to fill a garage in one guarded operation:
purchase matching trucks, hire available drivers, and assign both to the same
garage.

The repository contains the proven automation engine, its research tools, and
the first functional FleetFill desktop shell. Normal app launches cannot start
live game input. Separate, visibly armed developer launchers cover the
disposable test career and the certified exact 1+1, 2+2, 3+3, and 5+5 Steam
Cloud main-profile boundaries. Steam Cloud support also includes proven
identity, recovery-snapshot, sandbox-restore, and company preflights. The
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

The first real Steam Cloud safety preflight has also passed without sending any
game input. FleetFill proved the exact active cloud career and autosave, copied
and hash-verified the full authoritative profile, its Documents companion, and
Steam metadata, then decoded only the copy to prove sufficient money and 45
eligible empty garages. Normal main-profile automation remains locked.

That verified snapshot was subsequently reconstructed in an isolated sandbox:
all 104 cloud files, 9 companion files, and Steam metadata matched byte for
byte, with no live paths touched. The exact cloud controller preflight also ran
against a Steam-shaped copy of the snapshot and completed with zero UI steps
and zero transactions.

The graduated desktop boundary then completed a full real 5+5 run. It selected
an empty Munich garage and filled all five slots through 63 guarded UI steps.
The independent save audit verified the exact EUR 1,249,925 deduction, truck and
driver totals increasing from 139 to 144, five unique matching trucks, five
unique Munich-based drivers, and preservation of all 139 pre-existing truck
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
5. Garage and dealer markers are detected visually. If several fully visible
   dealer markers are available, FleetFill chooses the topmost marker, then the
   leftmost one as a deterministic tie-breaker. When a useful marker is not
   visible, the controller can pan the map and replay the measured locator.
6. Before a live batch, the controller copies the disposable profile's autosave
   and `profile.sii` into the local run evidence directory.
7. Separate read-only save inspection tools can compare before/after saves to
   confirm the game persisted exactly the intended company changes.
8. Steam Cloud careers use a distinct zero-input boundary that snapshots and
   hash-verifies every recovery surface before inspecting only the copied save.
9. Separately armed exact-count main-profile launchers repeat both the full
   snapshot and sandbox restore before their countdown; ordinary cloud-profile
   execution remains locked.

The controller composes many deliberately small probes rather than placing all
mouse clicks in one long macro. This makes each transition independently
checkable and gives the automation a safe place to stop.

## Repository layout

```text
research/tools/ets2_batch_controller.py   Unified truck/driver orchestrator
research/tools/ets2_ui_*_probe.py         Screen-specific guarded actions
research/tools/ets2_*_icon_detector.py    Garage and dealer visual detection
research/tools/verify_*_save.py           Read-only save verification
research/tools/main_profile_preflight.py  Zero-input Steam Cloud safety proof
research/tools/rehearse_main_profile_restore.py  Sandbox recovery proof
research/tools/save-inspector/            BSII save decoding helper
src/fleetfill/profile_safety.py            Stable cloud snapshot verification
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

The same two suites run automatically on Windows for every pull request and
every push to `main`. CI enforces 168 portable tests; seven calibrated visual
tests report as skipped because their private ETS2 recording evidence remains
in ignored local output. The full local run contains 175 tests. The required
status-check context is `Windows test suite`, produced by the `FleetFill tests`
workflow.

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

The next graduated developer launcher allows one to five slots while retaining
the disposable-profile restriction:

```powershell
.\scripts\run-fleetfill-live-test.ps1
```

Before its countdown, the controller decodes only the timestamped backup copy,
proves the company can afford the entire requested batch, and proves that the
save contains at least one completely empty large garage. The normal launcher
and main/Steam Cloud profiles remain live-input locked.

The separate main-profile preflight contains no automation call. It requires an
exact active `PC_steam_cloud` career and a save written during the current ETS2
process. It copies the complete cloud profile plus its Documents companion and
Steam metadata, verifies every copied file by SHA-256, and inspects only the
freshest copied current-session save:

```powershell
.\scripts\run-main-profile-preflight.ps1 -ProfileName "Your career name"
```

This command does not move the mouse or unlock the batch controller. If World of
Trucks has synchronized newer live state, save once and return to the home screen;
FleetFill fails closed until that state exists in a recoverable save slot.

The certified developer-only launcher is restricted to exactly one truck and
one driver on an explicitly named Steam Cloud career:

```powershell
.\scripts\run-fleetfill-main-validation.ps1 -ProfileName "Your career name"
```

That 1+1 path has passed its real runtime and post-exit semantic audit. Before
every countdown, the controller still creates a fresh full snapshot, verifies
its embedded content manifest, reconstructs it in a sandbox, inspects the
copied company state, and proves sufficient balance plus an empty large garage.

The certified 2+2 boundary is a separate launcher fixed to exactly two trucks
and two drivers:

```powershell
.\scripts\run-fleetfill-main-two-validation.ps1 -ProfileName "Your career name"
```

The certified exact-count launchers use mutually exclusive controller
authorization flags, and none can request another boundary's count. The 2+2 path
has passed its supervised four-action runtime and independent post-exit semantic
save audit. The separately armed 3+3 and 5+5 boundaries are documented below.

The next graduated boundary is a separate launcher fixed to exactly three
trucks and three drivers:

```powershell
.\scripts\run-fleetfill-main-three-validation.ps1 -ProfileName "Your career name"
```

It uses a third mutually exclusive authorization and cannot request any count
other than three. Its first supervised six-action run completed successfully,
but the deep audit found that its preflight autosave predated the live World of
Trucks state by more than twelve hours. FleetFill now requires and records a save
written during the current game process. The synchronized repeat then passed all
six actions and every post-exit invariant, certifying the 3+3 boundary.
Main-profile counts four and five remain input-locked.

The certified maximum-capacity boundary is isolated in a separate launcher fixed to
exactly five trucks and five drivers:

```powershell
.\scripts\run-fleetfill-main-five-validation.ps1 -ProfileName "Your career name"
```

It uses its own mutually exclusive authorization and cannot request one through
four slots. Four remains unavailable because it adds no state boundary beyond
certified 3+3; 5+5 uniquely proves that one empty large garage becomes completely
full. Its zero-input preflight, supervised ten-action run, and independent
post-exit audit have all passed on the synchronized main profile.

The shell uses PySide6 6.10.1 and already provides the approved Setup, History,
and Settings navigation. Setup discovers local ETS2 profiles, prefers the
disposable Automation Test profile, validates the selected autosave, calculates
the exact truck-and-driver estimate, and exposes a guarded review workflow.
Before review, the local live launchers prove from the current `game.log.txt`
that ETS2 is running, the selected career is `PC_local`, and the matching local
autosave was loaded after selection. The zero-input cloud boundary separately
requires `PC_steam_cloud`, Steam storage, the exact cloud folder ID, and a save
written after the current ETS2 process began. A stale log or save, wrong storage
type, different folder, or merely highlighted career fails closed.

The Qt process supervisor launches a no-input lifecycle simulator, streams
its output and checkpoint file without freezing the UI, supports cooperative
cancellation, and writes durable History records. The real controller uses the
same cancellation marker between guarded probes. Normal desktop execution is
still centrally locked; only the explicit 1+1, 2+2, 3+3, and 5+5 validation
launchers can cross their exact live boundaries.

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

Guarded one-to-five desktop batches have passed both runtime and independent
post-exit save audits on the disposable local profile. The separately armed
Steam Cloud main-profile boundaries at 1+1, 2+2, 3+3, and 5+5 have passed real
runtime and post-exit semantic audits. The original 1+1 filled one Valmiera slot
while preserving all 123 pre-existing trucks, unrelated garages, and the parked
World of Trucks delivery. The separate 2+2 boundary filled two Aarhus slots
with matching trucks and drivers while preserving the active World of Trucks
delivery and all unrelated company state. The isolated 3+3 boundary is now
certified as well: its synchronized repeat filled three Kiel slots, reconciled
the exact EUR 749,955 cost, and preserved the complete World of Trucks delivery
fingerprint plus all 129 pre-existing trucks. The certified 5+5 maximum boundary
filled all five Kaliningrad slots, reconciled EUR 1,249,925 exactly, preserved all
132 pre-existing truck configurations, and kept the World of Trucks delivery
fingerprint byte-for-byte equivalent. Normal main-profile input remains locked;
only those explicitly armed exact boundaries can send input, and count four is
intentionally unavailable.
Packaging follows later.

FleetFill is an unofficial community project and is not affiliated with SCS
Software. Euro Truck Simulator 2 is a trademark of its respective owner.

## License

FleetFill's original source code is available under the [MIT License](LICENSE).
Its dependencies remain under their respective licenses; see
[Third-party notices](THIRD_PARTY_NOTICES.md). A future packaged Windows release
must also include and comply with the applicable PySide6/Qt LGPLv3 materials.
