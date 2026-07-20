# ETS2 bulk-management research

This folder contains read-only research tools for the ETS2 1.60 UI workflow.

## Targeted UI inspection

`tools/inspect-ets2-ui.ps1` uses the self-contained `sk-zk/Extractor` binary and
an explicit allowlist. It reads `base_share.scs` and writes only relevant UI
definitions to `research/output/ets2-ui`. It never writes to the game directory.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\research\tools\inspect-ets2-ui.ps1 -Mode List
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\research\tools\inspect-ets2-ui.ps1 -Mode Extract
```

The extractor download and all generated research output are ignored by Git.
The downloaded ZIP SHA-256 is
`C8564DDE4E691FBEFB2FE96345CF246929F71E1AE6E916630EF096DDA96013DE`;
the extracted executable SHA-256 is
`1CEBE577A98650D2072D832155114C3B698C4F2322D70DB6AB7B3CF4F125F55A`.

Add `-VerifyArchive` to either command when a full SHA-256 pass over the 8.5 GB
`base_share.scs` archive is useful. It is omitted by default to keep inspection fast.

## Video storyboards

`tools/extract-video-storyboard.py` samples timestamped frames from a recording
and assembles them into 4-by-4 contact sheets for workflow analysis. Generated
frames are stored under `research/output` and do not alter the source video.

## Read-only UI dry run

`tools/ets2_ui_dry_run.py` recognizes the Recruitment Agency and garage-selection
screens at the verified 1920x1080 layout. It annotates driver cards, garage slots,
and the final confirmation button, but contains no mouse or keyboard input code.

```powershell
python .\research\tools\ets2_ui_dry_run.py --validate-recordings
python .\research\tools\ets2_ui_dry_run.py --image screenshot.png
python .\research\tools\ets2_ui_dry_run.py --capture --delay 5 --expected recruitment_agency
python .\research\tools\ets2_ui_dry_run.py --nvidia-capture --delay 10 --expected recruitment_agency
```

The NVIDIA mode verifies that ETS2 is the foreground window, sends only Alt+F1,
waits for a new stable PNG in the configured screenshot directory, and analyzes
that file. It performs no gameplay input.

`tools/ets2_ui_pointer_probe.py` is the next safety stage. It captures the
Recruitment Agency, moves the pointer to driver card 1, captures the hover state,
and returns the pointer to a safe margin. It contains no mouse-click call.

`tools/ets2_ui_select_probe.py` performs exactly one guarded click on driver card
1, moves the pointer away, and verifies that card 1 remains selected. It never
clicks Hire Driver or performs a transaction.

`tools/ets2_ui_open_garage_probe.py` requires card 1 to be selected, clicks only
Hire Driver, and verifies that the garage dialog opens with five locked slots.
It has no garage, slot, or confirmation target.

## Guarded batch controller prototype

`tools/ets2_batch_controller.py` composes the individually verified probes into
resumable truck and driver phases. It does not contain raw mouse coordinates for
transactions; each input remains owned by its narrow probe and recognition gate.
Every live run creates a preflight autosave backup, per-step evidence, and an
aggregate `batch-report.json` checkpoint.

The current prototype is deliberately restricted to saved fleet card 1, the
verified Scania Streamline Topline priced at EUR 248,485. It can navigate from
the main menu to Truck Dealers, return home after purchasing, open Recruitment
Agency, and complete both phases against one dynamically located garage. It can
also resume from several positively verified intermediate screens.

Validate the current Reims completion plan without sending input:

```powershell
python .\research\tools\ets2_batch_controller.py plan `
  --occupied 1 --truck-present 1 --free 3 --trucks 3 --drivers 4
```

The unified live phase starts from the visible home menu, dynamically finds a
garage with enough capacity, buys the trucks, then hires the same number of
drivers. It requires an explicit disposable local profile path so the preflight
backup cannot silently target a machine-specific profile:

```powershell
python .\research\tools\ets2_batch_controller.py fill --execute `
  --profile "C:\path\to\disposable-profile" `
  --occupied 0 --truck-present 0 --free 5 --count 5 --card 1 `
  --start-stage home --dynamic-garage
```

If a batch wrapper is interrupted after a verified reversible setup step, the
truck phase can resume from `scania-selected`, `dealer-selected`,
`online-purchase-stock`, or `fleet-configurations`. The operator must use only
the stage positively established by the preceding evidence; every subsequent
screen is still reverified by its owning probe.

The remembered marker coordinate is always matched against a freshly detected
garage icon and the complete expected slot fingerprint before it is clicked.
Any loading frame, popup, identity change, missing marker, unexpected slot, or
failed acknowledgement aborts the batch.

## Read-only save inspection

`tools/decrypt_scs_file.py` turns an encrypted `ScsC` SII file into a separate
plaintext research copy. It never overwrites the source save.

Binary `BSII` copies can then be converted to text with
`tools/save-inspector/decode-bsii.mjs`. The local helper pins the zero-runtime-
dependency `@trucky/sii-decrypt-ts` package to version 1.0.0.
