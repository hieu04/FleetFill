# How FleetFill was built

This document records the path from the original gameplay problem to the first
verified unified automation run. It describes the current prototype, not a
claim that the final desktop application is complete.

## 1. Define the narrow problem

The starting problem was repetitive ETS2 company management: buying several
similarly configured trucks and hiring several drivers into garage slots one at
a time. The target workflow became: choose a quantity, find a garage with
capacity, buy matching trucks, and hire the same number of drivers into it.

Three implementation directions were considered:

- editing save data;
- automating the normal ETS2 interface;
- hooking undocumented game internals.

UI automation was selected for the first product direction. It performs the
same transactions the player performs and avoids making save editing the user
experience. Save decoding remained useful as a read-only verification method.

## 2. Establish a controlled test environment

A disposable copy of an established ETS2 profile was made so it already had
money, garages, dealers, and recruitment progress. Steam Cloud and World of
Trucks were disconnected from that profile. The game environment was fixed to
ETS2 1.60, English, 1920x1080 exclusive fullscreen, and 100% Windows scaling.

The original profile was not used for live development transactions.

## 3. Record and model the interface

Gameplay recordings and screenshots were collected for the driver-hiring and
truck-purchasing paths. They were sampled into storyboards to identify:

- stable controls and dialog positions;
- loading and fade states;
- driver cards and selection states;
- five garage slot states;
- purchase and confirmation prompts;
- garage and dealer map markers;
- screens whose contents move relative to the player's current location.

Relevant UI definition files were also inspected from `base_share.scs` using a
strict allowlist. This was research input; FleetFill does not replace or write
game archives.

## 4. Build read-only recognition first

The first Python tools only captured or loaded images. NumPy and Pillow were
used to measure screen regions, compare image patches, classify slot states,
and locate marker-shaped connected components. Annotated screenshots and JSON
reports made each decision inspectable.

Recognition gates reject incorrect resolution, wrong screens, fades, missing
controls, ambiguous markers, unexpected slot layouts, and excessive reference
distance.

## 5. Add one guarded action at a time

Input was introduced through narrow probes. Each probe owns one small action,
such as selecting a driver, opening a garage dialog, selecting a slot, or
confirming a purchase. The general pattern is:

1. capture and verify the starting screen;
2. move or click one known target;
3. move the pointer to a safe margin;
4. wait for the game transition;
5. capture and verify the expected result;
6. write evidence or abort.

This progression allowed harmless pointer and selection tests before any tool
was permitted to perform a transaction.

## 6. Solve dynamic maps

The garage and truck-dealer maps are centered relative to the player's world
position, so fixed city coordinates cannot be assumed. FleetFill instead
detects visible markers and inspects garage slot capacity after opening a
candidate.

If a suitable garage or filtered dealer is not visible, guarded drag probes pan
the map through a clear corridor. Image translation is measured after the pan,
and a saved locator can be replayed when the same garage must be selected later
in the batch.

## 7. Replace shared screenshot capture

Early research used ETS2's configured NVIDIA screenshot hotkey because it was a
convenient way to capture exclusive fullscreen. The integrated controller now
uses Pillow's direct Windows screen capture, normally taking tens of
milliseconds and producing no files in the user's NVIDIA screenshot folder.

## 8. Compose the batch controller

`ets2_batch_controller.py` composes the proven probes into truck, driver, and
unified `fill` phases. It validates the complete requested slot transition
before input, backs up the disposable profile autosave, checkpoints every
verified step, and writes an aggregate batch report.

The unified phase can:

- wake and recognize the home screen;
- navigate through Services to Truck Dealers;
- select the calibrated Scania brand/configuration;
- find or pan to a usable dealer;
- find a garage with the requested free capacity;
- buy the requested trucks into that garage;
- return home and navigate to Recruitment Agency;
- hire the requested drivers into the exact same garage;
- stop immediately if any expected state is not observed.

## 9. Verify the first unified live run independently

The first approved five-plus-five run completed 63 guarded steps. It selected
Stuttgart dynamically, bought five matching Scania Streamline Topline trucks,
and hired five drivers into them.

A separate before/after save verifier confirmed:

- money decreased by exactly EUR 1,249,925;
- the company gained exactly five trucks and five drivers;
- Stuttgart changed from five empty slots to five occupied slots;
- no unrelated garage occupancy shape changed;
- all 133 pre-existing vehicle configurations remained semantically identical;
- all five new truck configurations matched;
- all five drivers were removed from recruitment offers and assigned to
  Stuttgart;
- the new trucks had unique IDs, full fuel, zero odometer, and German plates.

The offline suite currently contains 46 passing unit tests for controller state
transitions, probe composition, marker rules, garage capacity classification,
map translation, locator replay, and home/service navigation.

## 10. Third-party components

The FleetFill UI automation logic and tests in this repository were developed
for this project and are released under the MIT License. Runtime image
recognition relies on the open-source Python packages NumPy and Pillow, while
the desktop shell uses PySide6/Qt for Python under its upstream license terms.

Research utilities also used:

- `sk-zk/Extractor` to read an allowlisted subset of SCS archives;
- `@trucky/sii-decrypt-ts` 1.0.0 in the local Node save-inspector helper;
- Easy SCS Mod Manager cryptography code as an explicitly supplied helper for
  some `ScsC` research copies;
- OpenCV only for optional video storyboard extraction.

Downloaded tools, their source trees, game archives, generated evidence, and
personal save data are excluded from Git. Their respective upstream licenses
apply to those components; they are not vendored as part of FleetFill's source
payload.

`THIRD_PARTY_NOTICES.md` records the direct and optional dependency licenses.
This source-level inventory is not by itself sufficient for a packaged Windows
release. Before producing an installer, the build must inventory the exact
PySide6/Qt and other binaries it includes, ship the applicable license texts and
notices, and satisfy the Qt LGPLv3 requirements for the distributed libraries.

## 11. What remains

The core controller is a prototype rather than an end-user application. The
remaining product work includes the FleetFill desktop UI, persistent settings,
history, guided preflight checks, fullscreen-friendly progress/error feedback,
more failure and compatibility testing, packaging, code signing decisions, and
a normal Windows installer.

## 12. Build the first desktop shell

The approved interface direction was implemented with PySide6 6.10.1 and Qt
Widgets. This keeps the existing Python automation engine and the Windows UI in
one language while retaining a supported path to a packaged `.exe`.

The first shell establishes the final navigation model:

- **Setup** automatically discovers local ETS2 profiles, prefers the disposable
  Automation Test copy, shows the calibrated garage/truck/driver policies,
  validates the profile/autosave, and calculates the exact cost;
- **History** reserves the durable record for future app-controlled runs and
  distinguishes them from earlier controller research;
- **Settings** records the currently verified ETS2 environment and local
  evidence policy.

There is deliberately no permanent Running tab. After the user starts a future
batch, ETS2 must remain in exclusive fullscreen; progress and completion will
therefore be transient states and notifications, with the durable result stored
under History.

The shell can build and display the exact guarded controller command, but it
cannot execute it yet. That lock ensures the subprocess boundary, cancellation,
checkpoint streaming, and failure recovery are implemented and tested before a
desktop button is capable of purchasing anything.

Nine new tests cover profile discovery, profile validation, price calculation,
controller argument construction, the three-page navigation contract, and the
default five-plus-five review. All 46 existing controller tests continue to
pass. The Setup, History, and Settings pages were rendered with the real Windows
Qt platform for visual QA at 1180x760.

## 13. Prove the active career before arming automation

The profile picker identifies which folder FleetFill would back up; it cannot
switch the career loaded inside ETS2. That difference is safety-critical because
the same UI controller would otherwise operate on whichever career the player
last opened.

The desktop preflight therefore reads the current ETS2 log and accepts only the
latest coherent sequence:

1. `Set profile finished` names the chosen FleetFill profile;
2. `Profile type` is exactly `PC_local`;
3. `New profile selected` confirms the same name;
4. a later `Loading save` path uses `/home/profiles/<exact-folder-id>/`;
5. ETS2 is currently running and the log does not predate that process.

The parser deliberately discards evidence from earlier profile selections. A
test-to-main sequence fails even when the earlier test selection was valid, and
selecting a career without entering it fails because no later save load exists.
The check is read-only and sends no window input.

The Setup page runs this gate when the user chooses **Verify and review** and
shows either the exact local-autosave proof or a stop reason. A separate pure
Python supervised-run model now owns preflight, countdown, running,
cancel-requested, succeeded, and failed states. It consumes the controller's
`BATCH_*` output protocol and `batch-report.json` checkpoints without depending
on Qt, making failure and cancellation behavior testable before live execution.

The transient progress card follows the earlier design decision not to create a
permanent Running tab: it appears only for an active/recent run, while durable
results will eventually belong in History. Live process launch remains locked.
The desktop/safety suite now has 27 tests; combined with 46 controller tests,
the offline suite contains 73 passing tests.

## 14. Supervise the process before enabling live input

FleetFill now has a Qt `QProcess` boundary that keeps the interface responsive
while a controller runs. It reads the merged output stream, polls
`batch-report.json` only after complete atomic replacements, updates the
transient Setup status, and persists a separate `desktop-run.json` summary for
History. Generated run records remain under ignored local output storage.

The first executable behind this boundary is intentionally a simulator. It
creates the same ready/running/completed or cancelled checkpoint sequence as the
controller but imports no recognition probe and sends no window input. Process
integration tests launch this real child process and verify both completion and
cancellation during countdown. Attempts to pass a real command through the
supervisor still raise the central live-execution lock.

Cancellation is cooperative rather than a blind process kill. The desktop
creates `cancel.requested`; the batch controller checks it before each guarded
probe and throughout its initial countdown. If cancellation arrives while a
probe is already confirming a purchase or hire, that probe finishes, the caller
updates and checkpoints the garage state, and the marker stops the next probe.
This preserves an honest recovery record and avoids abandoning a child process
mid-click. A pre-existing marker stops before the profile backup or any input.

History currently shows the latest durable desktop run with its simulation/live
identity, profile, requested slots, completed actions, result, error, and report
path. There is still no permanent Running tab. The app/safety suite contains 35
tests and the controller suite contains 48, for 83 offline tests in total.

The remaining live boundary is one controlled one-truck/one-driver validation on
the disposable profile. Its backup, progress, final report, and save result must
all agree before the desktop live lock is removed for normal batches.

The first manual simulator run exposed a layout regression: placing the status
card in the Setup page's vertical layout reduced the form columns until field
labels overlapped. The status card is now a floating child positioned on resize,
so it cannot affect layout geometry. Terminal simulation, cancellation, and
failure notices auto-dismiss after a short confirmation period; active runs
retain the visible cooperative-cancel control. The success title also says
**Simulation complete** rather than implying that a real garage was modified.

## 15. Isolate the first desktop-controlled live validation

The normal FleetFill launcher remains live-input locked. A separate developer
launcher arms only the first supervised one-truck/one-driver run and makes that
state visible in the top status pill and Setup note. Its policy is intentionally
stricter than the eventual product:

1. the selected and active career must be exactly `ETS2 Automation Test`;
2. the request is fixed at one truck and one driver;
3. the controller must dynamically locate a completely empty five-slot garage;
4. the profile backup and shared cancellation marker must exist before input;
5. the existing ten-second fullscreen return countdown remains in place.

The desktop repeats the active-profile proof immediately before process launch,
then runs the real controller through the already-tested `QProcess` supervisor.
History distinguishes this from a simulation and records the controller report,
backup path, and runtime validation report. Runtime validation requires one
successful truck-confirm probe, one successful driver-confirm probe, two total
guarded actions, and the exact EUR 249,985 planned spend.

Runtime evidence alone cannot prove what ETS2 persisted. The save verifier was
generalized for a one-pair change inside a five-slot garage: four untouched
slots must remain untouched, exactly one truck/driver pair must appear, all
other garages must retain their occupancy and driver arrays, and pre-existing
truck configurations must remain identical. A separate finalizer refuses to
run while ETS2 is open, copies the stable post-exit autosave without modifying
the profile, decodes the before/after copies, and runs that semantic audit.

The app suite now contains 42 tests and the controller/save-audit suite contains
54, for 96 passing offline tests. No live input was sent while implementing or
testing this boundary. The next step is the explicitly supervised real 1+1 run;
general one-to-five desktop execution remains locked until its runtime and save
evidence both pass.

## 16. Complete the real desktop 1+1 validation

The armed desktop boundary completed its first real run on the disposable local
career. It dynamically selected a completely empty Salzburg garage and finished
all 19 guarded UI transitions without an abort:

- one saved Scania Streamline Topline was purchased;
- one recruitment-agency driver was assigned to that truck in the same garage;
- the controller recorded two of two intended transactions and EUR 249,985 of
  expected spend;
- the runtime evidence validator passed every backup, scope, step, transaction,
  and cost check.

After ETS2 exited normally, the independent finalizer decoded the encrypted
before/after autosaves and passed every semantic check. Money changed from EUR
76,537,256 to EUR 76,287,271. Company truck and driver totals each changed from
138 to 139. Salzburg changed from five empty paired slots to exactly one paired
truck/driver slot plus four untouched empty slots. All unrelated garage arrays
and all 138 pre-existing truck configurations were preserved. The new truck had
zero odometer and full fuel, and the hired driver was removed from the offers
list with Salzburg as both hometown and current city.

The run also exposed a harmless reporting artifact: dynamic selection retained
the old fixed-garage placeholder label `Reims` even though visual identity and
the persisted save both pointed to Salzburg. Dynamic runtime reports now use a
neutral label, while the post-exit audit writes the authoritative garage ID back
into History. History also refreshes when opened so evidence finalized by the
external post-exit tool becomes visible without restarting FleetFill.

This completes the small live-validation gate. Normal one-to-five desktop input
remains locked while the proven safeguards are carried into the general launch
policy.

## 17. Graduate the proven boundary to one-to-five test batches

The successful 1+1 run justified widening batch size, but not widening profile
scope. A new graduated developer launcher therefore enables one through five
slots only for `ETS2 Automation Test`. The original 1+1 validation launcher
retains its exact single-slot lock, and the normal FleetFill launcher still
cannot cross the live-input boundary.

Runtime evidence now derives its required truck confirmations, driver
confirmations, total guarded actions, and expected spend from the selected batch
size. The post-exit finalizer likewise reads the count from preflight evidence
and invokes the semantic verifier with the matching expected cost, allowing the
same audit path to prove a complete 5+5 result.

The controller also closes a product-safety gap before the countdown. After
creating its timestamped profile backup, it decodes only that copy and records a
company summary. A fill run is refused before UI input unless the balance covers
the full truck-plus-hiring cost and the save contains a completely empty
five-slot garage. A read-only smoke test against the encrypted pre-validation
backup proved the pipeline with EUR 76,537,256 available, EUR 1,249,925 required
for 5+5, and 41 qualifying empty garages.

The app suite now contains 47 tests and the controller/save-audit suite contains
58, for 105 passing offline tests. The next user-assisted step is the full 5+5
desktop test on the disposable profile, followed by a clean-exit save audit.

## 18. Prove the full desktop 5+5 path

The graduated launcher completed its full five-truck/five-driver desktop test
on the disposable local career. Preflight found EUR 76,287,271 available,
calculated the exact EUR 1,249,925 batch cost, and identified 40 completely
empty five-slot garages before allowing input. The controller then completed
all 63 guarded UI steps and recorded ten of ten intended transactions.

After a normal ETS2 exit, the independent finalizer decoded stable before/after
autosave copies and passed every semantic check. Money changed from EUR
76,287,271 to EUR 75,037,346, while company truck and driver totals each changed
from 139 to 144. Munich changed from five empty paired slots to five occupied
paired slots. The five trucks had unique IDs and an identical 37-accessory
configuration, full fuel, and zero odometer. The five hired drivers had unique
IDs, Munich as both hometown and current city, and were removed from recruitment
offers.

The audit also compared all 139 pre-existing vehicles and every unrelated garage
array and found no changes. This proves the intended full batch size on the
calibrated local profile. The next boundary is safe Steam Cloud/main-profile
discovery, backup, and active-career validation; that broader input scope remains
locked until it has equivalent evidence.

## 19. Establish the Steam Cloud zero-input boundary

Steam Cloud careers have two local recovery surfaces rather than one. The full
company profile and saves are authoritative under Steam's per-user app storage,
while the ETS2 Documents tree contains a smaller companion directory for local
controls and configuration. Steam also tracks synchronization state in
`remotecache.vdf`. Treating only the Documents companion as the save would have
produced an incomplete and misleading backup.

FleetFill now discovers the authoritative app `227300` profile without embedding
an account number or career name. A cloud profile carries its storage type,
Documents root, companion path, and Steam metadata path. Active-career proof is
storage-aware: local profiles require `PC_local` and `/home/profiles`, while a
cloud preflight requires `PC_steam_cloud` and `/steam/profiles`, always with the
exact folder ID and a save loaded after selection.

The recovery snapshot copies the complete authoritative cloud profile, the
Documents companion, and Steam metadata. It hashes every source before copying,
hashes the sources again afterward to detect races, and verifies every copied
file by SHA-256. The first real closed-game snapshot verified 104 cloud files,
9 companion files, and the metadata file. A later active-career zero-input run
passed the exact Steam identity proof, repeated the snapshot, and decoded only
the copied autosave. That copy contained sufficient balance for the planned 1+1
and 45 completely empty large garages. The report recorded `input_sent: false`.

A deliberate closed-game test also proved the opposite path: stale local-career
evidence was rejected, no snapshot was created, and no input was sent. The old
batch controller now explicitly refuses Steam Cloud profile paths. The full
offline suite contains 54 desktop/domain tests and 59 controller/save tests, for
113 passing tests. Main-profile live input remains locked until a separate 1+1
launcher and equivalent post-exit audit boundary are reviewed.

## 20. Rehearse recovery and isolate the main-profile 1+1 gate

A backup is not proven merely because it can be copied. FleetFill now writes a
snapshot content manifest containing the relative path, size, and SHA-256 of
every authoritative profile and Documents companion file plus Steam metadata.
The recovery rehearsal accepts only a snapshot whose creation report passed,
refuses an existing destination, verifies the snapshot against its embedded
manifest, reconstructs all three surfaces in a new sandbox, and hashes the
result independently. It has no operation that overwrites a live Steam path.

The first rehearsal used the verified real main-profile snapshot from the
zero-input milestone. It reconstructed all 104 cloud files, 9 companion files,
and the metadata file byte for byte while recording `live_paths_touched: false`.
The older snapshot predated embedded manifests, so the rehearsal derived its
expected hashes from that already verified copy; all future snapshots embed the
manifest directly.

The controller gained a `--preflight-only` mode to exercise the exact recovery
and company path without reaching its countdown. A Steam-shaped isolated copy
of the real snapshot passed the fresh snapshot, sandbox restore, EUR 249,985
1+1 affordability, and 45-empty-garage checks. The resulting checkpoint had
status `preflight_completed`, zero completed transactions, and zero UI steps.

Finally, the desktop now has a separate named Steam Cloud validation mode. It
forces one slot, disables browsing, requires the exact discovered cloud career
and loaded autosave, passes every recovery surface explicitly to the controller,
and carries a cloud flag that the controller accepts only for one unified 1+1
fill. Normal, local 1+1, and disposable one-to-five launchers cannot cross this
policy accidentally. Runtime validation and the post-exit finalizer now use an
explicit autosave evidence path so both local and full cloud snapshot layouts
resolve correctly.

The first active-trip baseline exposed an important distinction: a World of
Trucks contract has `current_job: null` in the local player unit and is instead
represented by a nonzero `stored_online_job_id` in the economy unit. The batch
save verifier now handles both online and ordinary local jobs. It fingerprints
the active job object, assigned truck and trailer objects, connection state, and
parked placements while canonicalizing volatile `_nameless` identifiers. This
makes a changed cargo/job/vehicle state fail the audit without treating a normal
save-time ID regeneration as damage.

The offline suite at this boundary contained 61 desktop/domain tests and 66
controller/save tests. A zero-input snapshot of the parked main profile
correctly identified its active World of Trucks contract and passed the new
fingerprint path.

## 21. Certify the first real main-profile 1+1

The first two attempts demonstrated the value of stopping before transactions.
The first reached the dealer map but rejected it because the main profile's
bright custom truck showed through the translucent map and exceeded a
recording-distance threshold. The recognizer was changed to require UI-owned
structure instead: the dealer title, selected brand, brand rail, and rendered
map. The second attempt reached My Fleet Configurations but captured its four
cards while they were still gray loading placeholders. That fixed delay became
read-only polling with a hard timeout. Both attempts recorded zero purchases and
zero hires.

The third supervised run completed all guarded steps and reported two of two
transactions. Its independent post-exit audit proved that Valmiera changed from
five empty paired slots to one paired truck/driver slot. The new Scania
Streamline had the expected 37-accessory configuration, full fuel, zero
odometer, and a Latvian plate. The new driver had Valmiera as both hometown and
current city and was removed from recruitment offers. All 123 pre-existing
truck configurations and every unrelated garage remained unchanged.

The audit also corrected two assumptions that do not hold for a large active
company. ETS2 advanced game time in the management workflow, allowing nine
semantic employee jobs to add EUR 136,883 and booking EUR 2,160 of active-job
fines. The final balance therefore reconciled exactly as EUR 82,153,204 minus
the EUR 249,985 batch, plus employee profit, minus fines: EUR 82,037,942. The
online truck-purchase counter independently increased from 130 to 131.

Finally, ETS2 saved the World of Trucks contract differently after the run. The
preflight copy held a nonzero online job ID with `current_job: null`; the clean
exit materialized a `player_job` and refreshed that ID. The captured pre-run
home screen and post-run job object both identify the same Volvo A25G cargo from
Utena to Naples. Truck and trailer placements were bit-for-bit identical, the
trailer stayed connected and loaded, and cargo damage remained zero. The
verifier now recognizes this safe online-job materialization while still
rejecting moved vehicles, detached trailers, lost jobs, or changed local-job
objects.

The completed boundary has 61 desktop/domain tests and 72 controller/save tests,
for 133 passing tests, plus the full recorded truck-screen transition suite.

## 22. Put the proven suites behind the main-branch gate

After the guarded main-profile boundary passed, the repository moved from
manual-only verification to continuous integration. A Windows GitHub Actions
workflow now installs FleetFill on Python 3.12 and runs the same two commands
used during local development: 61 desktop/domain tests followed by the
controller/save-audit suite.

The workflow runs for every pull request, every push to `main`, and manual
dispatches. It has read-only repository permissions, cancels superseded runs,
and exposes one stable branch-protection context named `Windows test suite`
under the `FleetFill tests` workflow. The active `Protect main` ruleset now
requires that check without requiring the branch to be retested against every
new `main` commit. Recorded UI transitions remain a separate hardware-calibrated
validation because they depend on the real ETS2 fullscreen environment and must
not run on a generic hosted worker.

The first hosted run also added a portability regression test to the gate.
GitHub's Windows temporary directory was presented with an 8.3 short-path user
segment, while FleetFill deliberately canonicalized the supplied home path.
Two fixture assertions now compare canonical paths, matching the discovery API
contract without weakening its profile-identity checks.

The next hosted run exposed the intended boundary between portable tests and
private visual evidence. Six home-navigation tests and one truck-dealer test
use ignored ETS2 screenshots under `research/output`; uploading those files to
CI would violate the repository's evidence policy. Those seven tests now
declare their local recording dependency and report as skipped when it is
absent. The branch gate therefore enforces 126 portable tests, while calibrated
local development continues to enforce all 133 plus the recorded transition
suite. The corrected hosted run passed with 126 tests and seven declared skips.

## 23. Isolate the main-profile 2+2 boundary

The certified 1+1 Steam Cloud path remains unchanged. FleetFill now exposes a
second developer-only app flag and PowerShell launcher that force exactly two
trucks and two drivers. The UI fixes the selector at two, shows the EUR 499,970
estimate, and names the mode as 2+2 so it cannot be confused with the original
validation.

The controller uses a new `--allow-steam-cloud-two-validation` authorization.
It is mutually exclusive with the 1+1 flag and is accepted only for a unified
count-two fill. Wrong counts, non-cloud profiles, missing recovery surfaces,
insufficient balance, or the absence of a completely empty five-slot garage all
stop before countdown or input. Counts above two remain locked for main
profiles.

Existing recovery and audit components were already count-aware: the zero-input
preflight accepts `-Count 2`, the recovery snapshot and sandbox reconstruction
cover the same three Steam surfaces, runtime evidence expects four completed
actions, and the deep save verifier requires exactly two paired slot changes
while preserving the other three slots, unrelated garages, pre-existing truck
configurations, and any active delivery.

The completed boundary now contains 69 desktop/domain tests and 87
controller/save-audit tests, for 156 passing local tests. Seven calibrated
visual tests continue to require ignored local recordings, so hosted CI will
enforce 149 portable tests. Its exact zero-input preflight, supervised
four-action run, and independent post-exit save audit have now passed.

## 24. Handle multiple visible truck dealers

The first supervised 2+2 attempt stopped safely before any purchase because the
player-position-dependent dealer map exposed multiple valid Scania markers. The
original marker probe required exactly one visible dealer, which was unnecessarily
strict once the detector could already distinguish complete available markers.

The marker probe now accepts one or more fully visible available dealers and uses
a deterministic topmost-then-leftmost policy. It still stops before clicking when
no marker exists, a dealer is already selected, or Buy Online is already enabled.
The change preserves the transaction boundary while supporting different player
positions and map views.

## 25. Wait for online truck cards to finish loading

The second supervised 2+2 attempt passed dealer selection and reached Online
Truck Purchase, then stopped before any purchase because all four truck-image
panels were still blank after the fixed 1.5-second transition delay. The screen
identity was correct, but its visual-integrity check correctly remained false.

The transition probe now polls without further input for up to the configured
capture timeout. It accepts only the dealer map during the initial transition or
the Online Truck Purchase screen while its cards render. A fully loaded purchase
screen continues the batch; any other screen stops immediately, and blank cards
that outlast the timeout remain a safe failure.

## 26. Compare World of Trucks jobs semantically after clean exit

The successful 2+2 runtime initially failed one conservative post-exit check even
though every garage, fleet, driver, balance, and vehicle invariant passed. The
active World of Trucks job retained its ID, cargo, route, loaded trailer, and
player vehicle placements. Clean exit merely persisted live progress that the
pre-run autosave did not contain: distance, fuel tracking, fines, and destination
parking variants.

The save verifier now treats only those known World of Trucks progress and parking
fields as volatile. When both saves already contain the job object, the top-level
online job ID must remain identical. Cargo, source and destination companies,
loaded state, player truck/trailer placements, attachment state, and all other job
fields remain exact semantic invariants.

## 27. Certify the main-profile 2+2 boundary

The corrected third attempt completed all 30 guarded UI steps and all four
transactions. It bought two identical Scania Streamline Topline trucks and hired
two drivers into slots zero and one of the previously empty Aarhus garage.
Runtime validation passed before ETS2 exited.

The clean post-exit audit then proved that exactly one garage changed, company
truck and driver counts each rose by two, the online-purchase counter rose by
two, all 124 pre-existing vehicle configurations remained intact, and every
unrelated garage slot was unchanged. Both new trucks have matching 37-accessory
configurations, full fuel, and zero odometer; both drivers are based in Aarhus.

The EUR 499,970 batch cost reconciled exactly with EUR 183,241 of employee income
earned while management screens advanced company time. The active World of
Trucks job retained the same ID, cargo, route, loaded trailer, attachment state,
and player vehicle placements. With runtime and semantic audits both passing,
the exact 2+2 Steam Cloud boundary is certified; counts three through five remain
input-locked on main profiles.

## 28. Isolate the main-profile 3+3 boundary

After merging the certified 2+2 work through pull request 8, FleetFill added a
third explicit main-profile boundary without exposing a general cloud-profile
slot selector. The desktop flag, PowerShell launcher, UI lock, domain validator,
and controller authorization all force exactly three trucks and three drivers.
The three cloud authorizations are mutually exclusive, and counts four and five
remain unreachable on main profiles.

The recovery and audit pipeline remains count-aware. Zero-input preflight plans
EUR 749,955, runtime evidence expects six completed transactions, and the clean
exit verifier requires exactly three paired slot changes in one previously empty
five-slot garage while preserving its other two slots and all unrelated state.

The initial offline 3+3 boundary had 74 desktop/domain tests and 91
controller/save-audit tests. The fresh-session baseline hardening raised those
counts to 76 and 92, for 168 passing local tests. Seven private visual-recording
tests remain declared skips on hosted runners, so CI enforces 161 portable tests.
The boundary is not live-certified until its zero-input preflight, supervised
runtime, and independent clean-exit audit all pass.

## 29. Require a save written by the current Steam Cloud session

The first supervised 3+3 attempt completed all six guarded transactions and put
three matching truck/driver pairs into one empty garage. Its deep audit correctly
refused certification because the recovery baseline was not current: plain
`autosave` had last been written more than twelve hours before the run. World of
Trucks had since synchronized a different active contract into memory, so clean
exit persisted a different job ID, four kilometres of live progress, a EUR 4,940
offence, and EUR 65 of other pre-existing session activity. None of those changes
belonged to FleetFill, but the stale before-image could not prove that fact.

FleetFill now requires a save slot written after the current ETS2 process began
before any cloud-profile input is authorized. It searches every save slot rather
than assuming plain `autosave`, records the selected slot as `baseline_save` in
the recovery evidence, inspects that copied slot for balance and garage capacity,
and compares it with the normal clean-exit autosave afterward. If World of Trucks
has synchronized but ETS2 has not saved the resulting live state, preflight stops
and instructs the operator to save once and return to the home screen.

The verifier still rejects a changed World of Trucks job ID; no delivery invariant
was weakened to make the inconclusive attempt pass. The first 3+3 batch is retained
as successful transaction evidence, while certification waits for a repeat from a
fresh, synchronized baseline.

## 30. Certify the main-profile 3+3 boundary

The synchronized repeat completed all six guarded transactions and filled slots
zero through two of the previously empty Kiel garage. Its EUR 749,955 deduction
reconciled exactly, the online truck-purchase counter rose from 136 to 139, and
company truck and driver counts rose from 129 to 132 and 127 to 130 respectively.

All three new Scania Streamline Topline trucks share the same 37-accessory
configuration, full fuel, and zero odometer. Their three drivers are based in
Kiel. Every unrelated garage slot and all 129 pre-existing truck configurations
remained unchanged.

Most importantly, the fresh baseline and clean-exit save contain the same World
of Trucks job ID and identical complete delivery fingerprints. Runtime validation
and every semantic save invariant passed, so the exact 3+3 Steam Cloud boundary
is certified. Counts four and five remain input-locked pending the next isolated
maximum-capacity boundary.

## 31. Isolate the maximum main-profile 5+5 boundary

The next graduated step deliberately skips 4+4. Certified 3+3 has already proven
multiple repeated purchases and hires while leaving unused slots intact; 4+4
would repeat that same state shape. A 5+5 run reaches a distinct boundary: it
consumes all five free truck slots, pairs all five drivers, and leaves the target
garage completely full.

FleetFill therefore adds one separate desktop flag, launcher, and controller
authorization fixed to count five. It remains mutually exclusive with 1+1, 2+2,
and 3+3, while count four stays rejected in the domain, desktop, and controller.
The UI locks the quantity at five and shows the exact EUR 1,249,925 estimate.

The established fresh-session save, full Steam Cloud recovery snapshot, sandbox
restore rehearsal, balance proof, and empty-garage requirement all remain in
force. Runtime evidence must contain ten successful actions. The semantic audit
must find five unique matching trucks and five unique hired drivers across all
five paired indexes of one previously empty garage, with no unrelated changes.
The boundary remains offline-only until those live and post-exit checks pass.

The isolated maximum boundary has 80 desktop/domain tests and 95
controller/save-audit tests, for 175 passing local tests. Seven calibrated visual
tests remain declared skips on hosted runners, so CI enforces 168 portable tests.

## 32. Certify the maximum main-profile 5+5 boundary

The maximum-capacity run completed all ten guarded transactions and filled every
paired slot of the previously empty Kaliningrad garage. Company truck and driver
counts each rose by five, from 132 to 137 trucks and from 130 to 135 drivers, and
the online truck-purchase counter rose from 139 to 144.

The exact EUR 1,249,925 batch cost reconciled with no intervening employee income
or newly booked fines. All five new Scania Streamline Topline trucks have unique
vehicle IDs, the same 37-accessory configuration, full fuel, and zero odometer.
All five new drivers have unique IDs and are based in Kaliningrad. Every unrelated
garage slot and all 132 pre-existing truck configurations remained unchanged.

The fresh manual-save baseline and clean-exit autosave retain World of Trucks job
ID `147641210` with an identical complete delivery fingerprint. Runtime evidence
and every semantic save invariant passed. The distinct maximum-capacity Steam
Cloud boundary is therefore certified, while count four remains intentionally
unauthorized because it adds no state shape beyond the already certified 3+3
boundary.
