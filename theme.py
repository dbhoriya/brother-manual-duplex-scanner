"""Paperwork theme: resolution-independent drawing and restrained desktop chrome."""

from pathlib import Path
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import QLabel

ASSETS = Path(__file__).resolve().parent / "assets" / "paperwork"
ASSETS.mkdir(exist_ok=True)
ICONS = {
    "scan": '<rect x="4" y="11" width="24" height="14" rx="3"/><path d="m6 11 3-6h14l3 6M8 17h16M10 21h12"/><circle cx="25" cy="21" r=".6"/>',
    "new": '<path d="M8 4h11l6 6v18H8zM19 4v7h6M12 19h9M16.5 14.5v9"/>',
    "folder": '<path d="M4 9h9l3 3h12v14H4zM4 12V7h9l3 3h10v2"/>',
    "save": '<path d="M6 4h18l3 3v21H5V4zM10 4v8h12V4M10 28V18h12v10"/>',
    "pdf": '<path d="M8 3h11l6 6v20H8zM19 3v7h6M11 16h10M11 21h7"/>',
    "trash": '<path d="M6 9h20M11 9V5h10v4M9 9l1 19h12l1-19M13 13v11M19 13v11"/>',
    "undo": '<path d="m12 7-7 7 7 7M5 14h13a8 8 0 0 1 0 16"/>',
    "crop": '<path d="M9 3v20h20M3 9h20v20M9 9h14v14H9"/>',
    "rotate": '<path d="M9 9a11 11 0 1 1-3 11M3 9h7V2"/>',
    "zoom": '<circle cx="14" cy="14" r="9"/><path d="m21 21 8 8M9 14h10M14 9v10"/>',
    "help": '<circle cx="16" cy="16" r="12"/><path d="M12 12a4 4 0 1 1 6 3.5c-2 1-2 2-2 3M16 23v.1"/>',
    "left": '<path d="m19 7-9 9 9 9"/>',
    "right": '<path d="m13 7 9 9-9 9"/>',
    "one": '<rect x="8" y="3" width="17" height="26" rx="2"/><path d="M12 10h9M12 15h9M12 20h6"/>',
    "two": '<path d="M7 24H4V3h17v3"/><rect x="9" y="8" width="18" height="21" rx="2"/><path d="M13 14h10M13 19h10M13 24h6"/>',
}


def make_assets():
    for name, paths in ICONS.items():
        (ASSETS / (name + ".svg")).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none" stroke="#47515e" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'
            + paths
            + "</svg>"
        )
    (ASSETS / "tray.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 180"><g fill="none" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="120" cy="150" rx="85" ry="9" fill="#d4d5d4" stroke="none"/><path d="M53 80 73 43h94l20 37" fill="#e4e5e3" stroke="#9ca3a6" stroke-width="2"/><rect x="48" y="80" width="144" height="63" rx="8" fill="#f4f3ef" stroke="#8c959d" stroke-width="2"/><path d="M67 98h106" stroke="#808a91" stroke-width="4"/><path d="M82 31h61l17 17v62H82z" fill="#fffefa" stroke="#9ca3a6" stroke-width="2"/><path d="M143 31v18h17M94 61h53M94 72h53M94 83h36" stroke="#b8bec2" stroke-width="2"/><rect x="70" y="119" width="75" height="6" rx="3" fill="#dce1e4" stroke="none"/><circle cx="173" cy="122" r="4" fill="#426b9c" stroke="none"/></g></svg>"""
    )
    (ASSETS / "flip.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 156 66"><g fill="none" stroke="#73808d" stroke-width="1.4" stroke-linejoin="round"><path d="M13 11h34v46H13z" fill="#fefdf9"/><path d="M18 6h34v46H18z" fill="#fffefa"/><path d="M26 19h18M26 26h18M26 33h12"/><path d="M106 11h34v46h-34z" fill="#fefdf9"/><path d="M101 6h34v46h-34z" fill="#fffefa"/><path d="M108 36h18M108 29h18M108 22h12"/><path d="M60 29c5-15 24-16 31-2m-8-2 9 3 1-9" stroke="#426b9c" stroke-width="2"/></g></svg>"""
    )


DARK_ICONS = False


def set_dark_icons(value):
    global DARK_ICONS
    DARK_ICONS = value


def icon(name):
    suffix = "-dark" if DARK_ICONS and (ASSETS / (name + "-dark.svg")).exists() else ""
    return QIcon(str(ASSETS / (name + suffix + ".svg")))


def decorate(button, name, tip=None):
    button.setProperty("scan_icon", name)
    button.setIcon(icon(name))
    button.setIconSize(QSize(18, 18))
    button.setToolTip(tip or button.text())
    return button


class VectorLabel(QLabel):
    def __init__(self, name, width, height):
        super().__init__()
        self.name = name
        self.setFixedSize(width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(
            self.rect(),
            icon(self.name).pixmap(
                QSize(
                    round(self.width() * self.devicePixelRatioF()),
                    round(self.height() * self.devicePixelRatioF()),
                )
            ),
        )


THEME = """
* { font-family:"Noto Sans", "DejaVu Sans"; font-size:12px; color:#303841; }
QMainWindow,QDialog { background:#f2f1ee; }
QLabel#title { font-size:22px; font-weight:600; color:#202730; }
QLabel#eyebrow,QLabel#muted { color:#6f777f; font-size:11px; }
QLabel#cardTitle { font-size:13px; font-weight:600; }
QLabel#heroTitle { color:#303b49; font-size:14px; font-weight:600; }
QFrame#hero { background:#e7ebee; border:1px solid #d4dae0; border-radius:5px; }
QFrame#card { background:#f9f9f7; border:1px solid #d4d7da; border-radius:5px; }
QPushButton { padding:7px 10px; background:#fafaf8; border:1px solid #cdd1d5; border-radius:4px; font-weight:500; }
QPushButton:hover { background:#fff; border-color:#8d9cab; }
QPushButton:pressed { background:#e2e7ed; }
QPushButton:disabled { color:#a2a7ac; border-color:#dce0e2; background:#eeefed; }
QPushButton#primary { background:#386396; border-color:#315987; color:white; font-weight:600; }
QPushButton#primary:hover { background:#2c5789; }
QPushButton#primary:disabled { background:#a2b3c8; color:#eef2f6; border-color:#a2b3c8; }
QPushButton#danger { color:#984c47; }
QPushButton#mode { padding:7px 16px; background:#fafaf8; }
QPushButton#mode:checked { background:#e1e9f2; border-color:#7290b0; color:#244d7a; }
QComboBox,QLineEdit { padding:6px 8px; min-height:18px; background:#fffefa; border:1px solid #cdd2d7; border-radius:4px; }
QComboBox:disabled,QLineEdit:disabled { color:#999; background:#eeefed; }
QComboBox::drop-down { border:0; width:20px; }
QListWidget { background:#e7e6e2; border:1px solid #d6d7d4; border-radius:4px; outline:none; }
QListWidget::item { background:#f9f9f6; border:1px solid #d0d4d8; border-radius:3px; padding:8px; margin:5px; }
QListWidget::item:selected { background:#e5edf6; border:2px solid #547eac; color:#203c5c; }
QListWidget::item:hover { border-color:#8296a9; }
QTabBar::tab { background:transparent; color:#6e757d; padding:9px 15px; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#284f7b; border-bottom:2px solid #436b97; font-weight:600; }
QTabBar::tab:hover { color:#253f5d; }
QScrollArea { border:0; background:#e3e5e6; }
QTextBrowser { background:#fffefa; border:1px solid #d4d7da; padding:16px; }
QToolTip { color:#f5f5f3; background:#343d48; border:0; padding:6px; }
QSplitter::handle { background:transparent; width:10px; }
QSlider::groove:horizontal { height:4px; background:#d2d7db; }
QSlider::handle:horizontal { width:14px; margin:-5px 0; border-radius:7px; background:#426b9c; }
"""

DARK_THEME = """
* { color:#dde3e9; }
QMainWindow,QDialog { background:#22282f; }
QLabel#title,QLabel#cardTitle,QLabel#heroTitle { color:#edf1f5; }
QLabel#muted,QLabel#eyebrow { color:#a4aeb8; }
QFrame#hero { background:#303b48; border-color:#465465; }
QFrame#card { background:#2b323a; border-color:#424b56; }
QPushButton { background:#39434e; border-color:#56616e; color:#e7ecf1; }
QPushButton:hover { background:#465361; border-color:#8ba1b9; }
QPushButton:disabled { background:#2e353e; color:#727e8a; border-color:#414954; }
QPushButton#mode { background:#303a45; }
QPushButton#mode:checked { background:#354f6b; color:#eaf2fb; border-color:#7b9bbb; }
QComboBox,QLineEdit { background:#303841; color:#e5ebf0; border-color:#536170; }
QComboBox QAbstractItemView { background:#303841; color:#e5ebf0; selection-background-color:#466b92; }
QListWidget { background:#262d34; border-color:#424d58; }
QListWidget::item { background:#343e49; border-color:#505d6b; }
QListWidget::item:selected { background:#3a526e; border-color:#8ab2df; color:#fff; }
QTabBar::tab { color:#aab5c0; }
QTabBar::tab:selected { color:#b8d8ff; border-color:#8ab2df; }
QTextBrowser,QPlainTextEdit { background:#29313a; color:#dde3e9; border-color:#536170; }
"""
