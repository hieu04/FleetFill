# ETS2 1.60 UI-first research findings

Research target: ETS2 1.60.1.1007, English UI, 1920×1080 exclusive fullscreen,
Windows display scale 100%.

## What the recordings establish

The game already exposes an important piece of the desired workflow: Online Truck
Purchase has a **My Fleet Configurations** category. An owned truck configuration
can therefore serve as the repeated template without recreating its specification
or editing a save.

The two recorded transaction paths are:

1. Truck: Services > Truck Dealers > select dealer brand > Buy online > My Fleet
   Configurations > select a configuration > Purchase > select garage > select
   target slot > OK.
2. Driver: Services > Recruitment Agency > Hire a driver > select a driver > Hire
   Driver > select garage > select target slot > OK.

Both paths converge on the same `garage_selection.sii` screen. That gives an
automation prototype one reusable garage-and-slot assignment routine.

## Relevant archive structure

The management UI is in `base_share.scs`, a HashFS v2 archive—not `base.scs`.
The targeted inspector extracted 49 relevant files without writing to the game
installation. Important definitions include:

- `/ui/recruit.sii` and `/ui/driver_view.sii`
- `/ui/recruitment_overview.sii` and `/ui/recruitment_map.sii`
- `/ui/garage_selection.sii` and `/ui/garage_selection_map.sii`
- `/ui/truck_dealer_offer.sii` and the other truck-dealer screens
- `/ui/copy_truck_table.sii`
- `/ui/company_manager/*`

The `.sii` files define layout, component types, bounds, and numeric control IDs.
They do not contain hire or purchase business logic. That logic is implemented by
native handlers such as `recruit_hdl`, `garage_sel_hdl`, and
`truck_dealer_online_hdl`. This is strong evidence that a normal UI mod can move or
reskin controls, but cannot add a new mass-hire transaction by itself.

## Stable anchors found in 1.60

The UI uses a virtual 1440×900 coordinate space. At 1920×1080 with the current
settings, the observed transform is a 1.2 scale with a 96-pixel horizontal offset:

```text
screen_x = 96 + (virtual_x * 1.2)
screen_y = (900 - virtual_y) * 1.2
```

Verified controls:

| Screen | Native control | ID | Virtual bounds | Observed screen result |
|---|---|---:|---|---|
| Recruit | Hire Driver | 300 | x 411–1029, y 52–82 | x 589–1331, y 982–1018 |
| Garage selection | OK | 100 | x 638–802, y 31–61 | center (960, 1025) |
| Garage selection | Close | 110 | x 1212–1242, y 853–883 | center (1568, 38) |
| Garage selection | Slot 1 | 1000 | x 455–545, y 77–167 | center (696, 934) |
| Garage selection | Slot 2 | 1001 | x 565–655, y 77–167 | center (828, 934) |
| Garage selection | Slot 3 | 1002 | x 675–765, y 77–167 | center (960, 934) |
| Garage selection | Slot 4 | 1003 | x 785–875, y 77–167 | center (1092, 934) |
| Garage selection | Slot 5 | 1004 | x 895–985, y 77–167 | center (1224, 934) |

`driver_view.sii` supplies one 533×272 radio-button card template (ID 10001),
which the native handler repeats to form the visible 2×2 driver grid. The truck
offer screen likewise contains dynamic runtime content, so its visible Purchase
half-button should be detected from the rendered screen rather than inferred from
the enclosing ID 300 bounds.

## Architectural conclusion

UI automation is now the best first prototype, with three rules:

1. Reuse **My Fleet Configurations** for identical trucks.
2. Drive a state machine using screen recognition, not a blind timed click list.
3. Use archive-derived bounds as search regions, while confirming enabled/selected
   states from pixels before every irreversible click.

The first useful prototype should begin on an already-open Recruitment Agency or
Online Truck Purchase screen. It should select one item, assign one empty slot,
and stop before OK. This dry transaction validates scaling, screen recognition,
and slot-state detection without changing the profile. Full menu navigation and
five-item loops can be added after that proof succeeds.

## Remaining unknowns to test safely

- What confirmation screen appears after OK for a truck purchase on 1.60.
- Whether the game returns to the offer/list screen in a consistent state after a
  completed transaction.
- Whether an internal `ui` console command can open these native screens directly.
- How a selected garage map position changes after zooming, panning, or map DLC
  changes; garage selection must not rely on one permanent map coordinate.

These should be tested on a disposable local profile with no Steam Cloud sync.

## Live dry-run and one-hire findings

The disposable `ETS2 Automation Test` profile was confirmed by `game.log.txt` as
`PC_local`. Two live 1920x1080 screenshots passed the read-only recognizer:

- Recruitment Agency: four driver cards found, with no card initially selected.
- Garage selection: Lyon selected, slot 1 selected and slots 2-5 free.

The recognizer performed zero input actions. Direct GDI/Pillow screen capture was
blocked by exclusive fullscreen, while NVIDIA screenshots remained available.
The input prototype therefore needs either an exclusive-fullscreen-compatible
capture path or a temporary borderless-window mode; blind clicks remain excluded.

One controlled hire established the successful-transaction loop. After the final
OK, ETS2 fades for roughly half a second, returns to the same Recruitment Agency
screen, removes the hired candidate, and inserts a replacement candidate. Full
Services-menu navigation is not required between hires.

The pre/post autosave comparison verified:

- `money_account`: 80,290,031 -> 80,288,531 (the expected 1,500 fee)
- company driver count: 121 -> 122
- `driver.353` removed from `drivers_offer` and added to company `drivers`
- `driver.353` hometown/current city set to `lyon`
- `garage.lyon` slot 1 changed from `null` to `driver.353`
- Lyon slots 2-5 and all five vehicle slots remained `null`

Only `profile.sii`, `profile.bak.sii`, `save/autosave/game.sii`, and
`save/autosave/info.sii` changed. No profile files were added or removed.
