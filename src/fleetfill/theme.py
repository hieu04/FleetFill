"""ETS2-inspired Qt stylesheet for FleetFill."""

APP_STYLESHEET = r"""
* {
    font-family: "Segoe UI";
    font-size: 14px;
    color: #e8eaec;
}
QMainWindow, QWidget#appRoot {
    background: #111315;
}
QFrame#topBar {
    background: #181b1e;
    border-bottom: 1px solid #2a2f33;
}
QFrame#sidebar {
    background: #15181a;
    border-right: 1px solid #292e32;
}
QLabel#brandMark {
    background: #f5a800;
    color: #17191b;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 800;
    padding: 8px;
}
QLabel#brandName {
    font-size: 21px;
    font-weight: 700;
}
QLabel#pageTitle {
    font-size: 25px;
    font-weight: 700;
}
QLabel#sectionTitle {
    font-size: 16px;
    font-weight: 650;
}
QLabel#muted, QLabel.muted {
    color: #969da3;
}
QLabel#successText {
    color: #68c78c;
}
QLabel#warningText {
    color: #f5a800;
}
QLabel#statusPill {
    background: #20262a;
    border: 1px solid #343b40;
    border-radius: 13px;
    color: #c8cdd1;
    padding: 5px 11px;
}
QFrame#card {
    background: #1a1e21;
    border: 1px solid #2c3237;
    border-radius: 10px;
}
QFrame#amberCard {
    background: #201d16;
    border: 1px solid #654a12;
    border-radius: 10px;
}
QPushButton {
    background: #272c30;
    border: 1px solid #3a4146;
    border-radius: 6px;
    min-height: 38px;
    padding: 0 15px;
    font-weight: 600;
}
QPushButton:hover {
    background: #30363b;
    border-color: #515a61;
}
QPushButton:pressed {
    background: #202428;
}
QPushButton:disabled {
    color: #676d72;
    background: #202326;
    border-color: #2b3034;
}
QPushButton#primaryButton {
    color: #17191b;
    background: #f5a800;
    border-color: #f5a800;
    font-weight: 750;
}
QPushButton#primaryButton:hover {
    background: #ffb516;
    border-color: #ffb516;
}
QPushButton#navButton {
    text-align: left;
    background: transparent;
    border: 0;
    border-radius: 6px;
    color: #aeb4b9;
    padding-left: 16px;
}
QPushButton#navButton:hover {
    color: #ffffff;
    background: #202428;
}
QPushButton#navButton:checked {
    color: #f5a800;
    background: #29271f;
    border-left: 3px solid #f5a800;
    padding-left: 13px;
}
QComboBox, QLineEdit, QSpinBox {
    background: #121517;
    border: 1px solid #363d42;
    border-radius: 6px;
    min-height: 38px;
    padding: 0 11px;
    selection-background-color: #7a5607;
}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover {
    border-color: #596168;
}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus {
    border-color: #f5a800;
}
QComboBox::drop-down {
    border: 0;
    width: 28px;
}
QComboBox QAbstractItemView {
    background: #1b1f22;
    border: 1px solid #3b4247;
    selection-background-color: #6a4a06;
    padding: 5px;
}
QScrollArea {
    border: 0;
    background: transparent;
}
QScrollBar:vertical {
    background: #15181a;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3c4348;
    border-radius: 5px;
    min-height: 30px;
}
QToolTip {
    color: #e8eaec;
    background: #24292d;
    border: 1px solid #555e65;
    padding: 5px;
}
QMessageBox {
    background: #181b1e;
}
"""
