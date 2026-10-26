"""Drag-to-crop editor; coordinates are proportional to the full rotated page."""

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap
from PyQt5.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from ui import ImageQt


class CropCanvas(QWidget):
    def __init__(self, image, box=None):
        super().__init__()
        image.thumbnail((1400, 1600))
        self.pixmap = QPixmap.fromImage(ImageQt(image))
        self.box = list(box or [0, 0, 1, 1])
        self.anchor = None
        self.setMinimumSize(400, 400)
        self.setCursor(Qt.CrossCursor)

    def image_rect(self):
        scale = min(
            (self.width() - 32) / self.pixmap.width(),
            (self.height() - 32) / self.pixmap.height(),
        )
        w, h = self.pixmap.width() * scale, self.pixmap.height() * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#e6e5e1"))
        rect = self.image_rect()
        p.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))
        x1, y1, x2, y2 = self.box
        r = QRectF(
            rect.left() + rect.width() * x1,
            rect.top() + rect.height() * y1,
            rect.width() * (x2 - x1),
            rect.height() * (y2 - y1),
        )
        shade = QColor(34, 43, 54, 140)
        for outside in [
            QRectF(rect.left(), rect.top(), rect.width(), r.top() - rect.top()),
            QRectF(rect.left(), r.bottom(), rect.width(), rect.bottom() - r.bottom()),
            QRectF(rect.left(), r.top(), r.left() - rect.left(), r.height()),
            QRectF(r.right(), r.top(), rect.right() - r.right(), r.height()),
        ]:
            p.fillRect(outside, shade)
        p.setPen(QPen(QColor("#659de0"), 2))
        p.drawRect(r)

    def point(self, event):
        rect = self.image_rect()
        return [
            max(0, min(1, (event.pos().x() - rect.left()) / rect.width())),
            max(0, min(1, (event.pos().y() - rect.top()) / rect.height())),
        ]

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.image_rect().contains(event.pos()):
            self.anchor = self.point(event)
            self.previous = list(self.box)

    def mouseMoveEvent(self, event):
        if self.anchor is not None:
            x, y = self.point(event)
            a, b = self.anchor
            self.box = [min(x, a), min(y, b), max(x, a), max(y, b)]
            self.update()

    def mouseReleaseEvent(self, event):
        if self.anchor is not None:
            if self.box[2] - self.box[0] < 0.01 or self.box[3] - self.box[1] < 0.01:
                self.box = self.previous
            self.anchor = None
            self.update()


class CropDialog(QDialog):
    def __init__(self, parent, image, box=None):
        super().__init__(parent)
        self.setWindowTitle("Crop pages")
        self.resize(800, 850)
        self.scope = None
        layout = QVBoxLayout(self)
        title = QLabel("Drag around the area you want to keep.")
        title.setStyleSheet("font-size:19px;font-weight:700;")
        layout.addWidget(title)
        note = QLabel(
            "Crop all uses the same proportional area on every page. Originals stay unchanged."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.canvas = CropCanvas(image, box)
        layout.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        reset = QPushButton("Full page")
        reset.clicked.connect(self.reset)
        row.addWidget(reset)
        row.addStretch()
        for text, scope in [("Crop this page", "page"), ("Crop all pages", "all")]:
            b = QPushButton(text)
            b.setObjectName("primary")
            b.clicked.connect(lambda checked=False, s=scope: self.finish(s))
            row.addWidget(b)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        layout.addLayout(row)

    def reset(self):
        self.canvas.box = [0, 0, 1, 1]
        self.canvas.update()

    def finish(self, scope):
        self.scope = scope
        self.accept()
