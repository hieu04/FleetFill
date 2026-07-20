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
for this project. Runtime image recognition currently relies on the open-source
Python packages NumPy and Pillow.

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
