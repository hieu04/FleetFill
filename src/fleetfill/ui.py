"""Qt Widgets implementation of the FleetFill desktop shell."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
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
    SUPPORTED_GAME_VERSION,
    SUPPORTED_LANGUAGE,
    SUPPORTED_RESOLUTION,
    TRUCK_PRICE_EUR,
    FillRequest,
    ProfileInfo,
    controller_command_preview,
    decode_profile_folder_name,
    discover_local_profiles,
    validate_request,
)
from fleetfill.preflight import ProfilePreflight, assess_active_profile
from fleetfill.runner import RunnerState


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

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
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

        form.addWidget(field_label("Disposable local profile"))
        profile_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setObjectName("profileCombo")
        self.profile_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.profile_combo.currentIndexChanged.connect(self._update_plan)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_profile)
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(browse)
        form.addLayout(profile_row)

        self.profile_path = label("No local profile selected", "muted", word_wrap=True)
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
        self.slots_combo.setCurrentIndex(4)
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
                "A timestamped profile backup and dry-run plan are created before the first purchase.",
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
        integration_note = label(
            "Plan-only build — live input remains locked.",
            "muted",
            word_wrap=True,
        )
        integration_note.setFixedHeight(34)
        review.addWidget(integration_note)

        self.run_status_card, run_status = card_layout(amber=True)
        self.run_status_title = label("Preparing FleetFill", "warningText")
        self.run_status_message = label("", "muted", word_wrap=True)
        run_status.addWidget(self.run_status_title)
        run_status.addWidget(self.run_status_message)
        self.run_status_card.hide()
        page.addWidget(self.run_status_card)

        self._load_profiles()
        self._update_plan()

    def _load_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profiles = discover_local_profiles()
        for profile in self.profiles:
            self.profile_combo.addItem(profile.name, str(profile.path))
        if not self.profiles:
            self.profile_combo.addItem("No local profiles detected", None)
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
        return ProfileInfo(self.profile_combo.currentText(), request.profile)

    def _update_plan(self) -> None:
        request = self.current_request()
        errors = validate_request(request)
        if request.profile:
            self.profile_path.setText(str(request.profile))
        else:
            self.profile_path.setText("No local profile selected")

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
            self.profile_check.setText("●  Disposable profile ready")
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

        titles = {
            RunnerState.PREFLIGHT: "Checking ETS2",
            RunnerState.COUNTDOWN: "Return to ETS2",
            RunnerState.RUNNING: "FleetFill is running",
            RunnerState.CANCEL_REQUESTED: "Stopping safely",
            RunnerState.SUCCEEDED: "Garage filled",
            RunnerState.FAILED: "FleetFill stopped",
            RunnerState.IDLE: "FleetFill is ready",
        }
        self.run_status_title.setText(titles[state])
        self.run_status_message.setText(message)
        self.run_status_card.show()

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
        command = controller_command_preview(request, self.project_root)
        message = QMessageBox(self)
        message.setWindowTitle("FleetFill safety check passed")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(
            f"{preflight.summary}. FleetFill will buy {request.slots} matching "
            f"trucks and hire {request.slots} drivers into the same empty garage."
        )
        message.setInformativeText(
            f"Estimated total: {money(request.total_cost_eur)}\n\n"
            "The desktop shell is not permitted to start live input yet. "
            "Controller integration is the next guarded milestone."
        )
        message.setDetailedText(command)
        message.exec()


class HistoryPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        page = QVBoxLayout(self)
        page.setContentsMargins(32, 28, 32, 30)
        page.setSpacing(20)
        page.addWidget(label("History", "pageTitle"))
        page.addWidget(label("FleetFill app runs and their recovery records will appear here.", "muted"))
        empty_card, content = card_layout()
        content.addWidget(label("No desktop-app runs yet", "sectionTitle"))
        content.addWidget(
            label(
                "The verified Stuttgart 5+5 run belongs to controller research. New app runs will record their plan, checkpoints, final result, and backup location here.",
                "muted",
                word_wrap=True,
            )
        )
        content.addStretch()
        page.addWidget(empty_card, 1)


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
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
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
        top.addWidget(label("●  Prototype  •  ETS2 1.60", "statusPill"))
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
        self.setup_page = SetupPage(project_root)
        self.history_page = HistoryPage()
        self.settings_page = SettingsPage(project_root)
        self.stack.addWidget(self.setup_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.settings_page)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []
        for index, title in enumerate(("Setup", "History", "Settings")):
            button = QPushButton(title)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, page=index: self.stack.setCurrentIndex(page))
            group.addButton(button)
            nav.addWidget(button)
            self.nav_buttons.append(button)
        self.nav_buttons[0].setChecked(True)
        nav.addStretch()
        nav.addWidget(label(f"FleetFill {__version__}", "muted"))
        nav.addWidget(label("Development preview", "muted"))

        body.addWidget(sidebar)
        body.addWidget(self.stack, 1)


def build_window(project_root: Path) -> MainWindow:
    return MainWindow(project_root)
