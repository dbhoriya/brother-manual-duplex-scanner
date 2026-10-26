"""Small Qt helpers shared by the scanner window and crop editor."""

from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QLabel, QPushButton
from model import export_pdf

ASSETS = Path(__file__).resolve().parent / "assets"


def ImageQt(image):
    rgb = image.convert("RGB")
    return QImage(
        rgb.tobytes(), rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888
    ).copy()


def label(text, name=None, wrap=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName("primary")
    return widget


class ExportWorker(QThread):
    done = pyqtSignal(str, int)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)

    def __init__(self, pages, target, quality, dpi, gray):
        super().__init__()
        self.args = (pages, target, quality, dpi, gray)

    def run(self):
        try:
            size = export_pdf(
                *self.args, progress=lambda a, b: self.progress.emit(a, b)
            )
            self.done.emit(str(self.args[1]), size)
        except Exception as error:
            self.failed.emit(str(error))
