"""ETS2-inspired Qt stylesheet for FleetFill."""

APP_STYLESHEET = r"""
* {
    font-family: "Segoe UI Variable Text", "Segoe UI";
    font-size: 14px;
    color: #e8eaec;
}
QMainWindow, QWidget#appRoot {
    background: #0e1113;
}
QFrame#topBar {
    background: #15191c;
    border-bottom: 1px solid #293036;
}
QPushButton#windowButton, QPushButton#closeButton {
    background: transparent;
    border: 0;
    border-radius: 6px;
    color: #bcc3c8;
    font-family: "Segoe UI Symbol", "Segoe UI";
    font-size: 16px;
    font-weight: 500;
    min-height: 0;
    padding: 0;
}
QPushButton#windowButton:hover {
    background: #293035;
    color: #ffffff;
}
QPushButton#windowButton:pressed {
    background: #343c42;
}
QPushButton#closeButton:hover {
    background: #c42b1c;
    color: #ffffff;
}
QPushButton#closeButton:pressed {
    background: #9f2117;
}
QFrame#sidebar {
    background: #121619;
    border-right: 1px solid #272e33;
}
QLabel#brandMark {
    background: transparent;
}
QLabel#brandName {
    font-size: 22px;
    font-weight: 750;
}
QLabel#pageTitle {
    font-size: 28px;
    font-weight: 750;
}
QLabel#sectionTitle {
    font-size: 16px;
    font-weight: 700;
}
QLabel#muted, QLabel.muted {
    color: #98a2a9;
}
QLabel#successText {
    color: #68c78c;
}
QLabel#warningText {
    color: #f5a800;
}
QLabel#statusPill {
    background: #1b2125;
    border: 1px solid #333c42;
    border-radius: 15px;
    color: #d3d8dc;
    padding: 7px 13px;
}
QFrame#card {
    background: #181d20;
    border: 1px solid #2b3338;
    border-radius: 12px;
}
QFrame#amberCard {
    background: #201d16;
    border: 1px solid #654a12;
    border-radius: 10px;
}
QPushButton {
    background: #252b2f;
    border: 1px solid #394248;
    border-radius: 7px;
    min-height: 40px;
    padding: 0 16px;
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
    border-radius: 7px;
    color: #aeb4b9;
    min-height: 42px;
    padding-left: 17px;
}
QPushButton#navButton:hover {
    color: #ffffff;
    background: #202428;
}
QPushButton#navButton:checked {
    color: #f5a800;
    background: #29271f;
    border-left: 3px solid #f5a800;
    padding-left: 14px;
}
QLabel#historyMeta {
    color: #929ca3;
    font-size: 13px;
}
QLabel#verifiedMark {
    background: #193524;
    border: 1px solid #3e9f62;
    border-radius: 15px;
    color: #65d38d;
    font-size: 18px;
    font-weight: 800;
}
QLabel#waitingMark {
    background: #322914;
    border: 1px solid #7b611d;
    border-radius: 15px;
    color: #f5a800;
    font-size: 18px;
    font-weight: 800;
}
QLabel#failedMark {
    background: #3a2020;
    border: 1px solid #8e4646;
    border-radius: 15px;
    color: #ef7c7c;
    font-size: 18px;
    font-weight: 800;
}
QLabel#metricLabel {
    color: #8f999f;
    font-size: 12px;
    font-weight: 600;
}
QLabel#metricValue {
    color: #f2f4f5;
    font-size: 15px;
    font-weight: 700;
}
QLabel#evidenceTitle {
    color: #b5bdc2;
    font-size: 13px;
    font-weight: 700;
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
