"""FleetFill desktop entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from fleetfill.theme import APP_STYLESHEET
from fleetfill.ui import build_window


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FleetFill desktop application")
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="Render the initial window to a PNG and exit (visual QA helper)",
    )
    parser.add_argument(
        "--page",
        choices=("setup", "history", "settings"),
        default="setup",
        help="Initial page, primarily for visual QA",
    )
    live_group = parser.add_mutually_exclusive_group()
    live_group.add_argument(
        "--live-validation",
        action="store_true",
        help="Arm the disposable-profile one-truck/one-driver validation path",
    )
    live_group.add_argument(
        "--live-test",
        action="store_true",
        help="Arm guarded one-to-five batches on the disposable test profile",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.screenshot and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    app = QApplication(sys.argv[:1])
    app.setApplicationName("FleetFill")
    app.setOrganizationName("FleetFill")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    window = build_window(
        project_root(),
        live_validation_enabled=args.live_validation,
        graduated_live_enabled=args.live_test,
    )
    page_index = {"setup": 0, "history": 1, "settings": 2}[args.page]
    window.stack.setCurrentIndex(page_index)
    window.nav_buttons[page_index].setChecked(True)
    window.show()

    if args.screenshot:
        destination = args.screenshot.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        def capture() -> None:
            window.grab().save(str(destination), "PNG")
            print(f"FLEETFILL_SCREENSHOT: {destination}")
            app.quit()

        QTimer.singleShot(300, capture)

    return app.exec()
