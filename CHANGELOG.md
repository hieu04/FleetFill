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

### Safety

- The desktop shell cannot start live controller input yet.
- Live plans require an explicit disposable profile and retain the controller's
  preflight-backup requirement.
