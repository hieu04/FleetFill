"""Qt Widgets implementation of the FleetFill desktop shell."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fleetfill import __version__
from fleetfill.domain import (
    DRIVER_HIRE_COST_EUR,
    MAIN_PROFILE_VALIDATION_BOUNDARIES,
    SUPPORTED_GAME_VERSION,
    SUPPORTED_LANGUAGE,
    SUPPORTED_RESOLUTION,
    TRUCK_PRICE_EUR,
    FillRequest,
    ProfileInfo,
    controller_arguments,
    controller_command_preview,
    decode_profile_folder_name,
    discover_local_profiles,
    discover_steam_cloud_profiles,
    validate_graduated_live_request,
    validate_live_validation_request,
    validate_main_profile_validation_request,
    validate_request,
    simulator_arguments,
)
from fleetfill.preflight import ProfilePreflight, assess_active_profile
from fleetfill.process import ControllerProcessSupervisor
from fleetfill.runner import (
    RunHistoryRecord,
    RunnerState,
    read_history_records,
    write_history_record,
)
from fleetfill.validation import verify_batch_run


def money(value: int) -> str:
    return f"€{value:,}"


def label(text: str, object_name: str | None = None, *, word_wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if object_name:
        widget.setObjectName(object_name)
    widget.setWordWrap(word_wrap)
    widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    return widget


def card_layout(*, amber: bool = False) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("amberCard" if amber else "card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(14)
    return frame, layout


def field_label(text: str) -> QLabel:
    widget = QLabel(text)
    widget.setStyleSheet("color: #aab0b5; font-size: 12px; font-weight: 600;")
    return widget


class SetupPage(QWidget):
    plan_changed = Signal()
    simulation_requested = Signal(object, object)
    live_validation_requested = Signal(object, object)
    cancel_requested = Signal()

    def __init__(
        self,
        project_root: Path,
        *,
        live_validation_enabled: bool = False,
        graduated_live_enabled: bool = False,
        main_profile_name: str | None = None,
        main_profile_slots: int = 1,
    ) -> None:
        super().__init__()
        if (
            main_profile_name
            and main_profile_slots not in MAIN_PROFILE_VALIDATION_BOUNDARIES
        ):
            raise ValueError("Main-profile validation supports only 1+1, 2+2, or 3+3")
        self.project_root = project_root
        self.live_validation_enabled = live_validation_enabled
        self.graduated_live_enabled = graduated_live_enabled
        self.main_profile_name = main_profile_name
        self.main_profile_slots = main_profile_slots
        self.live_execution_enabled = (
            live_validation_enabled or graduated_live_enabled or bool(main_profile_name)
        )
        self.run_is_simulation = True
        self.live_run_label = "Live validation"
        self.profiles: list[ProfileInfo] = []

        page = QVBoxLayout(self)
        page.setContentsMargins(32, 28, 32, 30)
        page.setSpacing(20)
        page.addWidget(label("Fill a garage", "pageTitle"))
        page.addWidget(
            label(
                "Review the batch here; live execution will return you to ETS2 fullscreen.",
                "muted",
            )
        )

        columns = QHBoxLayout()
        columns.setSpacing(18)
        page.addLayout(columns, 1)

        form_card, form = card_layout()
        form.setSpacing(11)
        form_card.setMinimumWidth(570)
        columns.addWidget(form_card, 3)
        form.addWidget(label("Batch setup", "sectionTitle"))
        form.addWidget(
            label(
                "FleetFill currently uses the verified ETS2 1.60 configuration.",
                "muted",
            )
        )

        form.addWidget(
            field_label(
                "Steam Cloud profile" if main_profile_name else "Disposable local profile"
            )
        )
        profile_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("profileCombo")
        self.profile_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.profile_combo.currentIndexChanged.connect(self._update_plan)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.setEnabled(not bool(main_profile_name))
        self.browse_button.clicked.connect(self._browse_profile)
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(self.browse_button)
        form.addLayout(profile_row)

        self.profile_path = label(
            "No Steam Cloud profile selected" if main_profile_name else "No local profile selected",
            "muted",
            word_wrap=True,
        )
        self.profile_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addWidget(self.profile_path)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        form.addLayout(grid)

        grid.addWidget(field_label("Garage"), 0, 0)
        grid.addWidget(field_label("Truck template"), 0, 1)
        self.garage_combo = QComboBox()
        self.garage_combo.addItem("Automatic — first empty garage")
        self.truck_combo = QComboBox()
        self.truck_combo.addItem("Scania Streamline Topline — €248,485")
        grid.addWidget(self.garage_combo, 1, 0)
        grid.addWidget(self.truck_combo, 1, 1)

        grid.addWidget(field_label("Slots to fill"), 2, 0)
        grid.addWidget(field_label("Driver policy"), 2, 1)
        self.slots_combo = QComboBox()
        for count in range(1, 6):
            self.slots_combo.addItem(f"{count} slot{'s' if count != 1 else ''}", count)
        fixed_slot_mode = live_validation_enabled or bool(main_profile_name)
        fixed_slot_count = main_profile_slots if main_profile_name else 1
        self.slots_combo.setCurrentIndex(fixed_slot_count - 1 if fixed_slot_mode else 4)
        self.slots_combo.setEnabled(not fixed_slot_mode)
        self.slots_combo.currentIndexChanged.connect(self._update_plan)
        self.driver_combo = QComboBox()
        self.driver_combo.addItem("First available")
        grid.addWidget(self.slots_combo, 3, 0)
        grid.addWidget(self.driver_combo, 3, 1)

        safety, safety_layout = card_layout(amber=True)
        safety_layout.setContentsMargins(16, 14, 16, 14)
        safety_title = label("◆  Guarded by preflight checks", "warningText")
        safety_title.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        safety_layout.addWidget(safety_title)
        safety_layout.addWidget(
            label(
                (
                    "A full cloud recovery snapshot and sandbox restore rehearsal are required before input."
                    if main_profile_name
                    else "A timestamped profile backup and dry-run plan are created before the first purchase."
                ),
                "muted",
                word_wrap=True,
            )
        )
        form.addWidget(safety)
        form.addStretch()

        review_card, review = card_layout()
        review_card.setMinimumWidth(330)
        review.setContentsMargins(20, 18, 20, 18)
        review.setSpacing(9)
        columns.addWidget(review_card, 2)
        review.addWidget(label("Review", "sectionTitle"))
        review.addWidget(label("Live estimate", "muted"))

        self.review_values: dict[str, QLabel] = {}
        for key, title in (
            ("garage", "Garage"),
            ("trucks", "Trucks"),
            ("drivers", "Drivers"),
            ("truck_cost", "Truck purchases"),
            ("hire_cost", "Hiring fees"),
        ):
            row = QHBoxLayout()
            row.addWidget(label(title, "muted"))
            value = QLabel("—")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(value, 1)
            review.addLayout(row)
            self.review_values[key] = value

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #343a3f;")
        review.addWidget(divider)
        total_row = QHBoxLayout()
        total_row.addWidget(label("Estimated total", "sectionTitle"))
        self.total_value = label("—", "warningText")
        self.total_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_row.addWidget(self.total_value, 1)
        review.addLayout(total_row)

        review.addWidget(label("Preflight", "sectionTitle"))
        self.profile_check = label("○  Choose a disposable profile", "muted")
        review.addWidget(self.profile_check)
        self.active_profile_check = label("○  Active ETS2 career not checked", "muted")
        self.active_profile_check.setWordWrap(True)
        review.addWidget(self.active_profile_check)
        review.addWidget(label("●  ETS2 1.60 / English", "successText"))
        review.addWidget(label("●  1920×1080 / 100% scaling", "successText"))
        review.addWidget(label("●  Backup required before input", "successText"))
        review.addStretch()

        self.review_button = QPushButton("Verify and review")
        self.review_button.setObjectName("primaryButton")
        self.review_button.clicked.connect(self._show_plan)
        review.addWidget(self.review_button)
        self.integration_note = label(
            (
                "Validation mode — exactly one truck and one driver."
                if live_validation_enabled
                else (
                    f"Main-profile validation — exactly one Steam Cloud {main_profile_slots}+{main_profile_slots}."
                    if main_profile_name
                    else (
                        "Live test mode — 1–5 slots on the disposable profile."
                        if graduated_live_enabled
                        else "Normal mode — live input remains locked."
                    )
                )
            ),
            "muted",
            word_wrap=True,
        )
        self.integration_note.setFixedHeight(34)
        review.addWidget(self.integration_note)

        self.run_status_card, run_status = card_layout(amber=True)
        self.run_status_title = label("Preparing FleetFill", "warningText")
        self.run_status_message = label("", "muted", word_wrap=True)
        self.cancel_button = QPushButton("Cancel safely")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        run_status.addWidget(self.run_status_title)
        run_status.addWidget(self.run_status_message)
        run_status.addWidget(self.cancel_button)
        self.run_status_card.setParent(self)
        self.run_status_card.setMinimumWidth(420)
        self.run_status_card.setMaximumWidth(560)
        self.run_status_card.hide()
        self.status_hide_timer = QTimer(self)
        self.status_hide_timer.setSingleShot(True)
        self.status_hide_timer.timeout.connect(self.run_status_card.hide)

        self._load_profiles()
        self._update_plan()

    def _load_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        if self.main_profile_name:
            self.profiles = [
                profile
                for profile in discover_steam_cloud_profiles()
                if profile.name == self.main_profile_name
            ]
        else:
            self.profiles = discover_local_profiles()
        for profile in self.profiles:
            self.profile_combo.addItem(profile.name, str(profile.path))
        if not self.profiles:
            self.profile_combo.addItem(
                "Named Steam Cloud profile not detected"
                if self.main_profile_name
                else "No local profiles detected",
                None,
            )
        else:
            if self.main_profile_name:
                self.profile_combo.setCurrentIndex(0)
            else:
                disposable_index = next(
                    (
                        index
                        for index, profile in enumerate(self.profiles)
                        if "automation test" in profile.name.casefold()
                    ),
                    0,
                )
                self.profile_combo.setCurrentIndex(disposable_index)
        self.profile_combo.blockSignals(False)

    def _browse_profile(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose disposable ETS2 profile",
            str(Path.home()),
        )
        if not selected:
            return
        path = Path(selected)
        display_name = decode_profile_folder_name(path.name)
        self.profile_combo.addItem(display_name, str(path))
        self.profile_combo.setCurrentIndex(self.profile_combo.count() - 1)

    def current_request(self) -> FillRequest:
        raw_path = self.profile_combo.currentData()
        return FillRequest(
            profile=Path(raw_path) if raw_path else None,
            slots=int(self.slots_combo.currentData() or 5),
        )

    def current_profile_info(self) -> ProfileInfo | None:
        request = self.current_request()
        if request.profile is None:
            return None
        for profile in self.profiles:
            if profile.path.resolve() == request.profile.resolve():
                return profile
        return ProfileInfo(self.profile_combo.currentText(), request.profile)

    def _update_plan(self) -> None:
        request = self.current_request()
        errors = validate_request(request)
        if request.profile:
            self.profile_path.setText(str(request.profile))
        else:
            self.profile_path.setText(
                "No Steam Cloud profile selected"
                if self.main_profile_name
                else "No local profile selected"
            )

        self.review_values["garage"].setText("Automatic")
        self.review_values["trucks"].setText(f"{request.slots} identical")
        self.review_values["drivers"].setText(str(request.slots))
        self.review_values["truck_cost"].setText(money(request.truck_cost_eur))
        self.review_values["hire_cost"].setText(money(request.driver_cost_eur))
        self.total_value.setText(money(request.total_cost_eur))
        self.review_button.setEnabled(not errors)
        if errors:
            self.profile_check.setObjectName("warningText")
            self.profile_check.setText(f"○  {errors[0]}")
        else:
            self.profile_check.setObjectName("successText")
            self.profile_check.setText(
                "●  Steam Cloud recovery surfaces ready"
                if self.main_profile_name
                else "●  Disposable profile ready"
            )
        self.profile_check.style().unpolish(self.profile_check)
        self.profile_check.style().polish(self.profile_check)
        self._show_active_profile_result(None)
        self.plan_changed.emit()

    def _show_active_profile_result(self, result: ProfilePreflight | None) -> None:
        if result is None:
            self.active_profile_check.setObjectName("muted")
            self.active_profile_check.setText("○  Active ETS2 career checked on review")
        elif result.passed:
            self.active_profile_check.setObjectName("successText")
            self.active_profile_check.setText(f"●  {result.summary}")
        else:
            self.active_profile_check.setObjectName("warningText")
            self.active_profile_check.setText("○  Active ETS2 career does not match")
        self.active_profile_check.style().unpolish(self.active_profile_check)
        self.active_profile_check.style().polish(self.active_profile_check)

    def show_run_status(self, state: RunnerState, message: str) -> None:
        """Expose transient progress without creating a permanent Running tab."""

        terminal_kind = "Simulation" if self.run_is_simulation else self.live_run_label
        titles = {
            RunnerState.PREFLIGHT: "Checking ETS2",
            RunnerState.COUNTDOWN: "Return to ETS2",
            RunnerState.RUNNING: "FleetFill is running",
            RunnerState.CANCEL_REQUESTED: "Stopping safely",
            RunnerState.CANCELLED: f"{terminal_kind} cancelled",
            RunnerState.SUCCEEDED: f"{terminal_kind} complete",
            RunnerState.FAILED: "FleetFill stopped",
            RunnerState.IDLE: "FleetFill is ready",
        }
        self.run_status_title.setText(titles[state])
        self.run_status_message.setText(message)
        cancellable = state in {RunnerState.COUNTDOWN, RunnerState.RUNNING}
        self.cancel_button.setVisible(cancellable)
        self.cancel_button.setEnabled(cancellable)
        self.status_hide_timer.stop()
        self.run_status_card.adjustSize()
        self._position_run_status()
        self.run_status_card.show()
        self.run_status_card.raise_()
        if state in {RunnerState.SUCCEEDED, RunnerState.CANCELLED, RunnerState.FAILED}:
            self.status_hide_timer.start(3500)

    def set_run_kind(
        self, *, simulated: bool, live_label: str = "Live validation"
    ) -> None:
        self.run_is_simulation = simulated
        self.live_run_label = live_label

    def _position_run_status(self) -> None:
        hint = self.run_status_card.sizeHint()
        width = min(560, max(420, self.width() - 64))
        height = hint.height()
        self.run_status_card.resize(width, height)
        self.run_status_card.move(
            max(24, self.width() - width - 32),
            max(24, self.height() - height - 28),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "run_status_card"):
            self._position_run_status()

    def _show_plan(self) -> None:
        request = self.current_request()
        errors = validate_request(request)
        if errors:
            QMessageBox.warning(self, "FleetFill preflight", "\n".join(errors))
            return
        profile = self.current_profile_info()
        assert profile is not None
        preflight = assess_active_profile(profile)
        self._show_active_profile_result(preflight)
        if not preflight.passed:
            message = QMessageBox(self)
            message.setWindowTitle("FleetFill stopped safely")
            message.setIcon(QMessageBox.Icon.Warning)
            message.setText("The active ETS2 career does not match this FleetFill plan.")
            message.setInformativeText(
                "No game input was sent.\n\n" + "\n".join(preflight.problems)
            )
            message.exec()
            return
        command = controller_command_preview(
            request,
            self.project_root,
            steam_cloud_profile=profile if self.main_profile_name else None,
        )
        message = QMessageBox(self)
        message.setWindowTitle("FleetFill safety check passed")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(
            f"{preflight.summary}. FleetFill will buy {request.slots} matching "
            f"trucks and hire {request.slots} drivers into the same empty garage."
        )
        message.setDetailedText(command)
        if self.live_execution_enabled:
            if self.live_validation_enabled:
                live_errors = validate_live_validation_request(
                    request, profile, enabled=True
                )
            elif self.main_profile_name:
                live_errors = validate_main_profile_validation_request(
                    request,
                    profile,
                    enabled=True,
                    expected_profile_name=self.main_profile_name,
                    expected_slots=self.main_profile_slots,
                )
            else:
                live_errors = validate_graduated_live_request(
                    request, profile, enabled=self.graduated_live_enabled
                )
            if live_errors:
                QMessageBox.warning(
                    self, "FleetFill validation locked", "\n".join(live_errors)
                )
                return
            mode_title = (
                "FleetFill live validation ready"
                if self.live_validation_enabled
                else (
                    f"FleetFill main-profile {self.main_profile_slots}+{self.main_profile_slots} validation ready"
                    if self.main_profile_name
                    else "FleetFill graduated live test ready"
                )
            )
            message.setWindowTitle(mode_title)
            message.setIcon(QMessageBox.Icon.Warning)
            message.setInformativeText(
                (
                    f"Estimated spend: {money(request.total_cost_eur)}\n\n"
                    "This WILL control the named Steam Cloud career after a "
                    "10-second countdown. It is restricted to exactly "
                    f"{request.slots} truck(s) and {request.slots} driver(s). A full "
                    "recovery snapshot, sandbox restore "
                    "rehearsal, balance check, and empty-garage check must pass first."
                    if self.main_profile_name
                    else (
                        f"Estimated spend: {money(request.total_cost_eur)}\n\n"
                        "This WILL control ETS2 after a 10-second countdown. It is "
                        f"restricted to {request.slots} truck(s) and {request.slots} "
                        "driver(s) on the disposable Automation Test career. A "
                        "timestamped backup and balance check are created first."
                    )
                )
            )
            run_button = message.addButton(
                (
                    (
                        f"Start {request.slots}+{request.slots} live validation"
                        if self.main_profile_name
                        else "Start 1+1 live validation"
                    )
                    if self.live_validation_enabled or self.main_profile_name
                    else f"Start {request.slots}+{request.slots} live test"
                ),
                QMessageBox.ButtonRole.AcceptRole,
            )
        else:
            message.setInformativeText(
                f"Estimated total: {money(request.total_cost_eur)}\n\n"
                "The normal app can test the desktop lifecycle with a no-input "
                "simulator. It will not click or control ETS2."
            )
            run_button = message.addButton(
                "Run safe simulation", QMessageBox.ButtonRole.AcceptRole
            )
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()
        if message.clickedButton() is run_button:
            if self.live_execution_enabled:
                self.live_validation_requested.emit(request, profile)
            else:
                self.simulation_requested.emit(request, profile)


class HistoryPage(QWidget):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.history_root = project_root / "research" / "output" / "desktop-runs"
        page = QVBoxLayout(self)
        page.setContentsMargins(32, 28, 32, 30)
        page.setSpacing(20)
        page.addWidget(label("History", "pageTitle"))
        page.addWidget(label("FleetFill app runs and their recovery records will appear here.", "muted"))
        empty_card, content = card_layout()
        self.history_title = label("No desktop-app runs yet", "sectionTitle")
        self.history_details = label("", "muted", word_wrap=True)
        content.addWidget(self.history_title)
        content.addWidget(self.history_details)
        content.addStretch()
        page.addWidget(empty_card, 1)
        self.refresh()

    def refresh(self) -> None:
        records = read_history_records(self.history_root)
        if not records:
            self.history_title.setText("No desktop-app runs yet")
            self.history_details.setText(
                "The verified Stuttgart 5+5 run belongs to controller research. "
                "New app runs will record their plan, checkpoints, final result, "
                "and backup location here."
            )
            return
        latest = records[0]
        kind = "Simulation" if latest.simulated else "Live run"
        self.history_title.setText(f"{kind}: {latest.state.replace('_', ' ').title()}")
        details = (
            f"{latest.created_at}  •  {latest.profile_name}  •  {latest.slots} slot(s)\n"
            f"Completed {latest.completed_transactions} of "
            f"{latest.requested_transactions} guarded actions."
        )
        if latest.error:
            details += f"\nReason: {latest.error}"
        if latest.report_path:
            details += f"\nReport: {latest.report_path}"
        if latest.backup_path:
            details += f"\nBackup: {latest.backup_path}"
        if latest.validation_passed is True:
            details += "\nRuntime evidence: Passed."
        elif latest.validation_passed is False:
            details += "\nRuntime evidence: Failed. Do not continue to larger batches."
        if latest.validation_report:
            details += f"\nValidation: {latest.validation_report}"
        if latest.save_audit_passed is True:
            details += "\nSave audit: Passed."
        elif latest.save_audit_passed is False:
            details += "\nSave audit: Failed. Do not continue to larger batches."
        elif latest.validation_passed is True:
            details += "\nSave audit: Pending clean ETS2 exit."
        if latest.save_audit_report:
            details += f"\nSave audit report: {latest.save_audit_report}"
        if latest.target_garage:
            details += f"\nVerified garage: {latest.target_garage}"
        self.history_details.setText(details)


class SettingsPage(QWidget):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        page = QVBoxLayout(self)
        page.setContentsMargins(32, 28, 32, 30)
        page.setSpacing(20)
        page.addWidget(label("Settings", "pageTitle"))
        page.addWidget(label("Compatibility and local storage for this calibrated build.", "muted"))

        compatibility, content = card_layout()
        content.addWidget(label("Verified game environment", "sectionTitle"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(13)
        rows = (
            ("Game version", f"ETS2 {SUPPORTED_GAME_VERSION}"),
            ("UI language", SUPPORTED_LANGUAGE),
            ("Resolution", SUPPORTED_RESOLUTION),
            ("Windows scaling", "100%"),
            ("Display mode", "Exclusive fullscreen"),
            ("Input", "Mouse and keyboard"),
        )
        for row, (title, value) in enumerate(rows):
            grid.addWidget(label(title, "muted"), row, 0)
            grid.addWidget(QLabel(value), row, 1)
        content.addLayout(grid)
        content.addStretch()
        page.addWidget(compatibility)

        storage, storage_content = card_layout()
        storage_content.addWidget(label("Local project storage", "sectionTitle"))
        path = label(str(project_root), "muted", word_wrap=True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        storage_content.addWidget(path)
        storage_content.addWidget(
            label(
                "Run evidence, screenshots, and profile backups stay local and are excluded from GitHub.",
                "muted",
                word_wrap=True,
            )
        )
        page.addWidget(storage)
        page.addStretch()


class MainWindow(QMainWindow):
    def __init__(
        self,
        project_root: Path,
        *,
        live_validation_enabled: bool = False,
        graduated_live_enabled: bool = False,
        main_profile_name: str | None = None,
        main_profile_slots: int = 1,
    ) -> None:
        super().__init__()
        if (
            main_profile_name
            and main_profile_slots not in MAIN_PROFILE_VALIDATION_BOUNDARIES
        ):
            raise ValueError("Main-profile validation supports only 1+1, 2+2, or 3+3")
        enabled_modes = sum(
            (bool(live_validation_enabled), bool(graduated_live_enabled), bool(main_profile_name))
        )
        if enabled_modes > 1:
            raise ValueError("Choose only one FleetFill live development mode")
        self.project_root = project_root
        self.live_validation_enabled = live_validation_enabled
        self.graduated_live_enabled = graduated_live_enabled
        self.main_profile_name = main_profile_name
        self.main_profile_slots = main_profile_slots
        self.live_execution_enabled = (
            live_validation_enabled or graduated_live_enabled or bool(main_profile_name)
        )
        self.supervisor = ControllerProcessSupervisor(self)
        self._active_run_dir: Path | None = None
        self._active_profile_name = ""
        self._active_slots = 0
        self._active_simulated = True
        self.setWindowTitle("FleetFill")
        self.setMinimumSize(1040, 680)
        self.resize(1180, 760)

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        shell = QVBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(76)
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(24, 14, 24, 14)
        top.setSpacing(12)
        brand_mark = label("FF", "brandMark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(44, 44)
        top.addWidget(brand_mark)
        brand_copy = QVBoxLayout()
        brand_copy.setSpacing(0)
        brand_copy.addWidget(label("FleetFill", "brandName"))
        brand_copy.addWidget(label("ETS2 garage automation", "muted"))
        top.addLayout(brand_copy)
        top.addStretch()
        mode = (
            "1+1 validation armed"
            if live_validation_enabled
            else (
                f"Main {main_profile_slots}+{main_profile_slots} validation armed"
                if main_profile_name
                else ("1–5 live test armed" if graduated_live_enabled else "Prototype")
            )
        )
        top.addWidget(label(f"●  {mode}  •  ETS2 1.60", "statusPill"))
        shell.addWidget(top_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        shell.addLayout(body, 1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(14, 24, 14, 18)
        nav.setSpacing(7)
        nav.addWidget(label("WORKSPACE", "muted"))
        nav.addSpacing(4)

        self.stack = QStackedWidget()
        self.setup_page = SetupPage(
            project_root,
            live_validation_enabled=live_validation_enabled,
            graduated_live_enabled=graduated_live_enabled,
            main_profile_name=main_profile_name,
            main_profile_slots=main_profile_slots,
        )
        self.history_page = HistoryPage(project_root)
        self.settings_page = SettingsPage(project_root)
        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.settings_page)
        self.setup_page.simulation_requested.connect(self._start_simulation)
        self.setup_page.live_validation_requested.connect(self._start_live_validation)
        self.setup_page.cancel_requested.connect(self.supervisor.request_cancel)
        self.supervisor.state_changed.connect(self.setup_page.show_run_status)
        self.supervisor.run_finished.connect(self._finish_run)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, title in enumerate(("Setup", "History", "Settings")):
            button = QPushButton(title)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, page=index: self._show_page(page)
            )
            group.addButton(button)
            nav.addWidget(button)
            self.nav_buttons.append(button)
        self.nav_buttons[0].setChecked(True)
        nav.addStretch()
        nav.addWidget(label(f"FleetFill {__version__}", "muted"))
        nav.addWidget(label("Development preview", "muted"))

        body.addWidget(sidebar)
        body.addWidget(self.stack, 1)

    def _show_page(self, page: int) -> None:
        if page == 1:
            self.history_page.refresh()
        self.stack.setCurrentIndex(page)

    def _start_simulation(self, request: FillRequest, profile: ProfileInfo) -> None:
        # The profile may have changed while the confirmation dialog was open.
        preflight = assess_active_profile(profile)
        self.setup_page._show_active_profile_result(preflight)
        if not preflight.passed:
            QMessageBox.warning(
                self,
                "FleetFill stopped safely",
                "The active profile changed. No process was started.\n\n"
                + "\n".join(preflight.problems),
            )
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = self.project_root / "research" / "output" / "desktop-runs" / f"{stamp}-simulation"
        command = simulator_arguments(request, run_dir)
        self._active_run_dir = run_dir
        self._active_profile_name = profile.name
        self._active_slots = request.slots
        self._active_simulated = True
        self.setup_page.set_run_kind(simulated=True)
        self.setup_page.review_button.setEnabled(False)
        self.setup_page.show_run_status(
            RunnerState.COUNTDOWN,
            "Starting the no-input lifecycle simulator. ETS2 will not be controlled.",
        )
        self.supervisor.start(
            command,
            run_dir,
            request.slots * 2,
            simulated=True,
        )

    def _start_live_validation(self, request: FillRequest, profile: ProfileInfo) -> None:
        """Start only a separately armed disposable-profile live path."""

        if self.live_validation_enabled:
            errors = validate_live_validation_request(request, profile, enabled=True)
            run_suffix = "live-validation"
            live_label = "Live validation"
        elif self.main_profile_name:
            errors = validate_main_profile_validation_request(
                request,
                profile,
                enabled=True,
                expected_profile_name=self.main_profile_name,
                expected_slots=self.main_profile_slots,
            )
            run_suffix = f"main-profile-{self.main_profile_slots}-validation"
            live_label = "Main-profile validation"
        else:
            errors = validate_graduated_live_request(
                request, profile, enabled=self.graduated_live_enabled
            )
            run_suffix = "live-test"
            live_label = "Live batch"
        preflight = assess_active_profile(profile)
        self.setup_page._show_active_profile_result(preflight)
        if errors or not preflight.passed:
            problems = [*errors, *preflight.problems]
            QMessageBox.warning(
                self,
                "FleetFill validation stopped safely",
                "No process was started.\n\n" + "\n".join(problems),
            )
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run_dir = (
            self.project_root
            / "research"
            / "output"
            / "desktop-runs"
            / f"{stamp}-{run_suffix}"
        )
        command = controller_arguments(
            request,
            self.project_root,
            run_dir,
            steam_cloud_profile=profile if self.main_profile_name else None,
        )
        self._active_run_dir = run_dir
        self._active_profile_name = profile.name
        self._active_slots = request.slots
        self._active_simulated = False
        self.setup_page.set_run_kind(simulated=False, live_label=live_label)
        self.setup_page.review_button.setEnabled(False)
        self.setup_page.show_run_status(
            RunnerState.COUNTDOWN,
            "Return to ETS2 now. Input begins after the controller's 10-second countdown.",
        )
        self.supervisor.start(
            command,
            run_dir,
            request.slots * 2,
            simulated=False,
            live_enabled=self.live_execution_enabled,
        )

    def _finish_run(self, model) -> None:
        self.setup_page.review_button.setEnabled(True)
        if self._active_run_dir is None:
            return
        validation_passed = None
        validation_report = None
        if not self._active_simulated:
            preflight_path = self._active_run_dir / "preflight.json"
            try:
                preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
                backup_payload = preflight.get("backup", {})
                backup = backup_payload.get("recovery_snapshot") or backup_payload.get("backup")
                if backup:
                    model.backup_path = Path(backup)
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
            if model.state == RunnerState.SUCCEEDED:
                try:
                    evidence = verify_batch_run(
                        self._active_run_dir, expected_count=self._active_slots
                    )
                    validation_passed = evidence.passed
                    validation_report = evidence.report_path
                    if evidence.passed:
                        self.setup_page.show_run_status(
                            RunnerState.SUCCEEDED,
                            "Runtime evidence passed. Exit ETS2 cleanly for the save audit.",
                        )
                    else:
                        model.error = "Runtime validation failed: " + ", ".join(
                            evidence.problems
                        )
                        self.setup_page.show_run_status(RunnerState.FAILED, model.error)
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                    validation_passed = False
                    model.error = f"Runtime validation could not be completed: {error}"
                    self.setup_page.show_run_status(RunnerState.FAILED, model.error)
        record = RunHistoryRecord.from_run(
            model,
            run_id=self._active_run_dir.name,
            profile_name=self._active_profile_name,
            slots=self._active_slots,
            simulated=self._active_simulated,
            validation_passed=validation_passed,
            validation_report=validation_report,
        )
        write_history_record(record, self._active_run_dir)
        self.history_page.refresh()


def build_window(
    project_root: Path,
    *,
    live_validation_enabled: bool = False,
    graduated_live_enabled: bool = False,
    main_profile_name: str | None = None,
    main_profile_slots: int = 1,
) -> MainWindow:
    return MainWindow(
        project_root,
        live_validation_enabled=live_validation_enabled,
        graduated_live_enabled=graduated_live_enabled,
        main_profile_name=main_profile_name,
        main_profile_slots=main_profile_slots,
    )
