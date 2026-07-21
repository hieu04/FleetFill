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

### Safety

- The desktop shell cannot start live controller input yet.
- Live plans require an explicit disposable profile and retain the controller's
  preflight-backup requirement.
- Choosing a profile folder is not treated as proof of the active game career;
  mismatched, cloud, unloaded, stale, and ambiguous states stop before input.
- The desktop supervisor refuses real controller commands while the live lock is
  set; only the no-input simulator is launchable in this milestone.
