# Changelog

All notable FleetFill development milestones are recorded here. The project has
not produced a public release yet.

## Unreleased

### Added

- First PySide6 desktop application shell with ETS2-inspired charcoal and amber
  styling.
- Final Setup, History, and Settings navigation structure.
- Automatic discovery and readable naming of local ETS2 profiles.
- Disposable-profile and autosave validation.
- Dynamic one-to-five slot estimates using the verified truck and hiring costs.
- Plan-only preview of the guarded unified controller command.
- Nine desktop/domain tests in addition to the existing 46 controller tests.
- Windows-rendered screenshot mode for repeatable visual QA.
- Read-only active-career proof derived from ETS2's latest coherent profile
  selection, profile type, and loaded-save path.
- Windows process-start correlation so an old matching log cannot satisfy the
  current-session preflight.
- Supervised run states for preflight, countdown, progress checkpoints,
  cancellation, success, aborts, and report discovery.
- Transient in-app progress surface without adding a permanent Running tab.
- Eighteen safety/runner tests, bringing the desktop-side suite to 27 tests and
  the full offline suite to 73 tests.
- MIT licensing for FleetFill's original source, package metadata, and a
  third-party dependency notice with a Qt/LGPL packaging gate.
- Responsive Qt process supervision with streamed controller output and polled
  JSON checkpoints.
- A real no-input lifecycle simulator covering countdown, progress, completion,
  failure, and cancellation without controlling ETS2.
- Durable simulation records displayed on the History page.
- Cooperative controller cancellation between guarded probes, preserving the
  checkpoint for a transaction that finishes while cancellation is pending.
- Ten additional lifecycle, History, cancellation, and command-boundary tests,
  bringing the offline suite to 83 tests.
- Floating terminal/progress notifications that no longer compress the Setup
  form and automatically dismiss after success, cancellation, or failure.
- A separately armed one-truck/one-driver desktop validation launcher; normal
  FleetFill launches remain live-input locked.
- Exact validation gates for the disposable `ETS2 Automation Test` career, one
  slot, active local autosave, and a completely empty five-slot garage.
- Immediate runtime evidence validation and History links for the controller
  report, timestamped backup, and validation report.
- A post-exit, read-only save finalizer that copies stable evidence and audits a
  one-slot change within a five-slot garage.
- Successful real desktop 1+1 validation in Salzburg: 19 guarded UI steps, an
  exact EUR 249,985 deduction, one new truck, one new driver, and no unrelated
  garage or pre-existing truck configuration changes.
- Save-audit garage identity is written back into durable History, and opening
  History refreshes evidence finalized while the app remained running.
- A separate graduated live-test launcher that enables one-to-five batches only
  on the disposable Automation Test profile while normal mode remains locked.
- Pre-input company inspection from the timestamped backup, including exact
  balance sufficiency and existence of a completely empty large garage.
- Generalized runtime and post-exit evidence validation for batch sizes one
  through five.
- Nine additional policy, UI-mode, company-preflight, runtime, and finalizer
  tests, bringing the full offline suite to 105 tests.
- Successful real desktop 5+5 validation in Munich: 63 guarded UI steps, an
  exact EUR 1,249,925 deduction, five new matching trucks, five new drivers, and
  no unrelated garage or pre-existing truck configuration changes.
- Steam Cloud profile discovery from Steam's authoritative userdata tree, with
  exact cloud type, storage, folder, and loaded-autosave identity checks.
- Complete Steam Cloud recovery snapshots covering the authoritative profile,
  Documents companion, and `remotecache.vdf`, with before/after stability and
  copied-file SHA-256 verification.
- A zero-input main-profile preflight that inspects only the verified copy and
  passed its first real active-career, snapshot, balance, and garage-capacity
  proof.
- Eight additional cloud discovery, identity, snapshot, and controller-lock
  tests, bringing the full offline suite to 113 tests.
- Persistent per-file snapshot manifests and sandbox-only restore rehearsal
  with tamper detection and refusal to overwrite an existing destination.
- Successful real-snapshot recovery rehearsal covering 104 cloud files, 9
  Documents companion files, and Steam metadata without touching live paths.
- A controller `--preflight-only` mode that proved the complete cloud snapshot,
  restore, balance, and empty-garage path with zero probes or transactions.
- A separately armed, explicitly named main-profile launcher restricted to one
  truck and one driver, with full recovery and company checks before countdown.
- Eleven additional recovery, policy, UI, argument, and finalizer tests,
  bringing the full offline suite to 124 tests.
- Thirteen validation, policy, launcher, discovery, and save-audit tests,
  bringing the full offline suite to 96 tests.

### Safety

- Normal desktop launches cannot start live controller input. Only the explicit
  validation launcher can start the tightly limited, now-proven 1+1 run.
- Graduated one-to-five live batches remain restricted to the disposable local
  Automation Test profile; Steam Cloud and main-profile input remain locked.
- The existing live controller explicitly refuses Steam Cloud profile paths;
  the main-profile preflight has no automation call and always records whether
  input was sent.
- Steam Cloud controller access requires a separate explicit flag, exact 1+1
  fill scope, profile identity, companion path, metadata path, fresh snapshot,
  and successful sandbox restore rehearsal.
- Live plans require an explicit disposable profile and retain the controller's
  preflight-backup requirement.
- Choosing a profile folder is not treated as proof of the active game career;
  mismatched, cloud, unloaded, stale, and ambiguous states stop before input.
- The desktop supervisor refuses real controller commands while the live lock is
  set; only the no-input simulator is launchable in this milestone.
