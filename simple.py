#!/usr/bin/env python3
"""Whole-stack scanning. No page counts, ranges, or selected-page acquisition."""

import copy
import re
import sys
import time
import uuid
from pathlib import Path
from PIL import Image
from PyQt5.QtCore import Qt, QProcess, QTimer, QSize, QLockFile, QItemSelectionModel
from PyQt5.QtGui import QPixmap, QIcon, QColor, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QSplitter,
    QTabBar,
    QScrollArea,
    QSlider,
    QFileDialog,
    QMessageBox,
    QDialog,
    QTextBrowser,
    QSizePolicy,
    QShortcut,
    QStackedWidget,
)
from model import Project, HOME, render, scan_file_complete
from crop import CropDialog
from scanner_setup import ScannerSetup, load_scanner_config, scanner_options
from theme import THEME, DARK_THEME, VectorLabel, decorate, icon, set_dark_icons
from preferences import PreferencesDialog, load_preferences, paper_dimensions
from ui import ASSETS, label, button, ImageQt, ExportWorker

SCAN_DPI = [100, 150, 300, 600]
PDF_QUALITY = [55, 78, 92]

SIMPLE_STYLE = (
    THEME
    + f'QComboBox::down-arrow {{ image:url({ASSETS / "down.svg"}); width:10px; height:7px; }}'
)
GUIDE = """<h1>Just scan the stack.</h1>
<h2>Delete, clear, undo</h2><p>Select a thumbnail and press <b>Delete</b>, or use <b>Delete selected</b>. Ctrl-click or Shift-click selects several pages. <b>Clear all</b> empties the entire document. Both ask for confirmation and preserve original files. <b>Undo</b> or <b>Ctrl+Z</b> in the gallery restores the last edit. Starting a new scan ends the previous undo history.</p>
<h2>Crop and PDF preview</h2><p>Select a page and click <b>Crop…</b>. Drag over the area to keep, then choose <b>Crop this page</b> or <b>Crop all pages</b>. All pages receive the same proportional crop, so inspect differently sized pages. <b>Full page</b> removes the crop when applied. Undo reverses cropping and rotation.</p><p><b>Preview PDF</b> opens the actual compressed combined PDF in your system PDF viewer. The gallery updates immediately after cropping or deletion. Save PDF writes the final copy wherever you choose.</p>
<h2>One-sided for all pages</h2><p>Load the whole stack in the feeder. Choose <b>One-sided</b> and press <b>Scan all pages</b>. It stops when the feeder is empty. Review the gallery and save your PDF.</p>
<h2>Two-sided for all pages</h2><p>Choose <b>Two-sided</b> and <b>Scan all fronts</b>. When it finishes, flip the stack and load the back of the <b>last sheet first</b>. Press <b>Scan all backs</b>. The Combined PDF gallery puts the pages in reading order automatically.</p>
<p>Keep blank backs in the stack. Preview the first and last pairs before saving. Clicking a thumbnail only previews it; scanning always processes the entire loaded stack.</p>
<h2>Stopped halfway?</h2><p>Completed pages are saved. Leave scanned sheets out of the feeder and load the remaining sheets, without changing their order. Press <b>Continue</b>. For a partial back pass, the main instruction tells you how many backs remain. If you are unsure of the order, <b>Scan backs again</b> restarts the whole back pass while retaining all original files.</p>
<h2>Only put half the fronts in?</h2><p>Before scanning any backs, use <b>Add more fronts</b> to scan the rest. The app counts them for you. If you use the glass, scan each side in order and press <b>Fronts finished</b> when ready to flip.</p>
<h2>Speed and quality</h2><p><b>Fastest</b>: 100 DPI (default). <b>Balanced</b>: 150 DPI. <b>High detail</b>: 300 DPI. <b>Maximum detail</b>: 600 DPI. Leave Color unchecked for grayscale and less data, or enable it at any speed. Higher DPI captures fine print but cannot remove scanner warmup and carriage delays.</p><p><b>PDF quality</b> independently controls compression: Small file, Balanced, or Best quality. It does not change scan speed or resolution. Original scans remain unchanged.</p>
<h2>Resume later</h2><p>Closing ends the workspace; the next launch starts empty. Projects remain saved on disk. Use Open saved to resume one. Clear separation of Fronts, Backs, and Combined PDF lets you inspect originals and their final order. Originals are never overwritten by redoing a pass or rotating a preview.</p>"""


class SimpleWindow(QMainWindow):
    def __init__(self, project=None):
        super().__init__()
        self.setWindowTitle("Brother Scan")
        self.setWindowIcon(QIcon(str(ASSETS / "icon.svg")))
        self.resize(1300, 880)
        self.setMinimumSize(1000, 700)
        self.prefs = load_preferences()
        self.project = project or Project.create(count=0)
        self.proc = None
        self.busy = False
        self.scanning = False
        self.stopped = False
        self.discovery_then_scan = False
        self.scanner_config = load_scanner_config()
        self.device = self.scanner_config.get("device", "")
        self.cache = {}
        self.entries = []
        self.selected_key = None
        self.logs = bytearray()
        self.seen = set()
        self.exporting = False
        self.normalize()
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(10)
        header = QHBoxLayout()
        mark = VectorLabel("scan", 36, 36)
        header.addWidget(mark)
        words = QVBoxLayout()
        words.setSpacing(0)
        words.addWidget(label("Brother Scan", "title"))
        words.addWidget(label("Brother printers · Manual duplex scanning", "muted"))
        header.addLayout(words, 1)
        self.scanner_btn = decorate(
            button("Scanner", self.open_scanner_setup),
            "scan",
            "Choose a scanner or configure its driver",
        )
        header.addWidget(self.scanner_btn)
        header.addWidget(
            decorate(
                button("New", self.new_document),
                "new",
                "Start a new document; existing scans stay saved",
            )
        )
        header.addWidget(
            decorate(
                button("Open", self.open_saved), "folder", "Resume a saved project"
            )
        )
        header.addWidget(decorate(button("Help", self.help), "help"))
        self.prefs_btn = button("Preferences", self.open_preferences)
        header.addWidget(self.prefs_btn)
        layout.addLayout(header)
        modes = QHBoxLayout()
        self.one = button("One-sided", lambda: self.choose_mode(False))
        self.two = button("Two-sided", lambda: self.choose_mode(True))
        for b in [self.one, self.two]:
            b.setObjectName("mode")
            b.setCheckable(True)
            modes.addWidget(b)
        decorate(self.one, "one", "Scan every sheet once")
        decorate(self.two, "two", "Scan all fronts, then flip and scan all backs")
        modes.addStretch()
        self.paper_badge = label("A4 · Whole stack", "muted")
        modes.addWidget(self.paper_badge)
        layout.addLayout(modes)
        options = QHBoxLayout()
        self.name = QLineEdit(self.project.data["name"])
        self.name.setPlaceholderText("Document name")
        self.name.editingFinished.connect(self.save_name)
        options.addWidget(self.name, 1)
        options.addWidget(label("Scan from", "muted"))
        self.source = QComboBox()
        self.source.addItems(["Whole feeder stack", "Glass · one side at a time"])
        options.addWidget(self.source)
        options.addWidget(label("Scan speed", "muted"))
        self.quality = QComboBox()
        self.quality.addItems(
            [
                "Fastest · 100 DPI",
                "Balanced · 150 DPI",
                "High detail · 300 DPI",
                "Maximum detail · 600 DPI",
            ]
        )
        self.quality.setToolTip(
            "Fastest uses the lowest resolution supported by this scanner. Higher DPI captures more detail and more data. Mechanical startup still takes time."
        )
        options.addWidget(self.quality)
        self.color = QCheckBox("Color")
        self.color.setToolTip(
            "Leave unchecked for grayscale and less data. Enable for color at any scan speed."
        )
        options.addWidget(self.color)
        self.source.setCurrentIndex(
            self.project.data.get("simple_source", self.prefs["source"])
        )
        self.quality.setCurrentIndex(
            self.project.data.get("speed_preset", self.prefs["speed"])
        )
        self.color.setChecked(
            self.project.data.get("simple_color", self.prefs["color"])
        )
        for w in [self.source, self.quality]:
            w.currentIndexChanged.connect(self.save_options)
        self.color.toggled.connect(self.save_options)
        layout.addLayout(options)
        self.speed_hint = label("Fastest: 100 DPI grayscale.", "muted", True)
        self.speed_hint.hide()
        hero = QFrame()
        hero.setObjectName("hero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(12, 10, 12, 10)
        self.flip_graphic = VectorLabel("flip", 126, 54)
        hero_layout.addWidget(self.flip_graphic)
        instruction = QVBoxLayout()
        self.step = label("", "heroTitle")
        self.instruction = label("", wrap=True)
        instruction.addWidget(self.step)
        instruction.addWidget(self.instruction)
        hero_layout.addLayout(instruction, 1)
        actions = QVBoxLayout()
        self.main_btn = button("Scan all pages", self.main_action, True)
        self.main_btn.setMinimumWidth(205)
        actions.addWidget(self.main_btn)
        self.secondary = button("Add more fronts", self.secondary_action)
        actions.addWidget(self.secondary)
        self.stop_btn = button("Stop scanning", self.stop)
        self.stop_btn.setObjectName("danger")
        actions.addWidget(self.stop_btn)
        hero_layout.addLayout(actions)
        layout.addWidget(hero)
        split = QSplitter(Qt.Horizontal)
        layout.addWidget(split, 1)
        gallery = QWidget()
        g = QVBoxLayout(gallery)
        g.setContentsMargins(0, 0, 8, 0)
        self.tabs = QTabBar()
        self.tabs.addTab("Combined PDF")
        self.tabs.addTab("Fronts")
        self.tabs.addTab("Backs")
        self.tabs.currentChanged.connect(self.refresh_gallery)
        g.addWidget(self.tabs)
        self.gallery = QListWidget()
        self.gallery.setViewMode(QListWidget.IconMode)
        self.gallery.setResizeMode(QListWidget.Adjust)
        self.gallery.setMovement(QListWidget.Static)
        self.gallery.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.gallery.setIconSize(QSize(128, 163))
        self.gallery.setGridSize(QSize(174, 220))
        self.gallery.setWordWrap(True)
        self.gallery.currentItemChanged.connect(self.preview)
        self.gallery.itemDoubleClicked.connect(self.enlarge)
        self.gallery_stack = QStackedWidget()
        self.gallery_stack.addWidget(self.gallery)
        empty = QWidget()
        empty_box = QVBoxLayout(empty)
        empty_box.addStretch()
        empty_box.addWidget(VectorLabel("tray", 240, 180), 0, Qt.AlignHCenter)
        empty_box.addWidget(
            label("No pages scanned yet", "cardTitle"), 0, Qt.AlignHCenter
        )
        empty_box.addWidget(
            label("Load the feeder, then press Scan.", "muted"), 0, Qt.AlignHCenter
        )
        empty_box.addStretch()
        self.gallery_stack.addWidget(empty)
        g.addWidget(self.gallery_stack, 1)
        editbar = QHBoxLayout()
        self.delete_btn = button("Delete selected", self.delete_selected)
        self.clear_btn = button("Clear all", self.clear_all)
        self.undo_btn = button("Undo", self.undo_delete)
        decorate(self.delete_btn, "trash")
        decorate(self.clear_btn, "trash")
        decorate(self.undo_btn, "undo")
        for b in [self.delete_btn, self.clear_btn, self.undo_btn]:
            editbar.addWidget(b)
        editbar.addStretch()
        g.addLayout(editbar)
        self.delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self.gallery)
        self.delete_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.delete_shortcut.activated.connect(self.delete_selected)
        self.undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self.gallery)
        self.undo_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.undo_shortcut.activated.connect(self.undo_delete)
        self.gallery.itemSelectionChanged.connect(self.update_edit_buttons)
        self.counts = label("No pages scanned yet.", "muted")
        g.addWidget(self.counts)
        split.addWidget(gallery)
        preview = QFrame()
        preview.setObjectName("card")
        p = QVBoxLayout(preview)
        p.setContentsMargins(18, 14, 18, 14)
        preview_head = QHBoxLayout()
        self.preview_title = label("Page preview", "cardTitle")
        preview_head.addWidget(self.preview_title, 1)
        preview_head.addWidget(decorate(button("Zoom", self.enlarge), "zoom"))
        p.addLayout(preview_head)
        self.picture = label("Scanned pages appear here.")
        self.picture.setAlignment(Qt.AlignCenter)
        self.picture.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.picture.setMinimumSize(160, 120)
        self.picture.setStyleSheet(
            "background:#555c65;border:1px solid #474f59;border-radius:3px;color:#e4e7ea;font-size:14px;"
        )
        p.addWidget(self.picture, 1)
        controls = QHBoxLayout()
        controls.addWidget(
            decorate(button("", lambda: self.navigate(-1)), "left", "Previous page")
        )
        controls.addWidget(decorate(button("Rotate", self.rotate), "rotate"))
        controls.addWidget(decorate(button("Crop", self.crop_page), "crop"))
        controls.addWidget(
            decorate(button("", lambda: self.navigate(1)), "right", "Next page")
        )
        p.addLayout(controls)
        self.page_detail = label("Click any page to preview it.", "muted", True)
        p.addWidget(self.page_detail)
        split.addWidget(preview)
        split.setSizes([760, 470])
        footer = QHBoxLayout()
        self.status = label("Ready. The app counts pages automatically.", "muted", True)
        footer.addStretch()
        self.pdf_preview_btn = decorate(
            button("Preview PDF", lambda: self.export_pdf(preview=True)), "pdf"
        )
        footer.addWidget(self.pdf_preview_btn)
        self.folder_btn = decorate(
            button("Originals", self.open_folder), "folder", "Open original scans"
        )
        footer.addWidget(self.folder_btn)
        footer.addWidget(label("PDF quality", "muted"))
        self.pdf_quality = QComboBox()
        self.pdf_quality.addItems(["Small file", "Balanced", "Best quality"])
        self.pdf_quality.setCurrentIndex(
            self.project.data.get("pdf_quality", self.prefs["pdf_quality"])
        )
        self.pdf_quality.setToolTip(
            "Controls saved PDF compression, independently of scanner speed. Original scans are preserved."
        )
        self.pdf_quality.currentIndexChanged.connect(self.save_options)
        footer.addWidget(self.pdf_quality)
        self.export_btn = button("Save combined PDF ↗", self.export_pdf, True)
        footer.addWidget(self.export_btn)
        layout.addLayout(footer)
        bottom = QHBoxLayout()
        bottom.addWidget(self.status, 1)
        bottom.addWidget(label("Written by Deepak Bhoriya", "muted"))
        layout.addLayout(bottom)
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.collect)
        self.apply_appearance()
        self.refresh()

    def open_preferences(self):
        if self.busy:
            return
        values = copy.deepcopy(self.prefs)
        values.update(
            paper=self.project.data.get("paper", self.prefs["paper"]),
            source=self.source.currentIndex(),
            speed=self.quality.currentIndex(),
            color=self.color.isChecked(),
            pdf_quality=self.pdf_quality.currentIndex(),
        )
        dialog = PreferencesDialog(self, values)
        if dialog.exec_() != QDialog.Accepted:
            return
        self.prefs = dialog.values
        self.project.data["paper"] = self.prefs["paper"]
        for w in [self.source, self.quality, self.color, self.pdf_quality]:
            w.blockSignals(True)
        self.source.setCurrentIndex(self.prefs["source"])
        self.quality.setCurrentIndex(self.prefs["speed"])
        self.color.setChecked(self.prefs["color"])
        self.pdf_quality.setCurrentIndex(self.prefs["pdf_quality"])
        for w in [self.source, self.quality, self.color, self.pdf_quality]:
            w.blockSignals(False)
        self.save_options()
        self.apply_appearance()
        self.refresh()

    def apply_appearance(self):
        set_dark_icons(self.prefs["theme"] == "Dark")
        for b in self.findChildren(QPushButton):
            if b.property("scan_icon"):
                b.setIcon(icon(b.property("scan_icon")))
        for vector in self.findChildren(VectorLabel):
            vector.update()
        QApplication.instance().setStyleSheet(
            SIMPLE_STYLE + (DARK_THEME if self.prefs["theme"] == "Dark" else "")
        )
        size = {"Small": 96, "Medium": 128, "Large": 160}[self.prefs["thumbnail"]]
        self.thumb_width = size
        self.gallery.setIconSize(QSize(size, round(size * 1.27)))
        self.gallery.setGridSize(QSize(size + 46, round(size * 1.27) + 57))
        self.cache.clear()

    def normalize(self):
        for key, maximum, default in [
            ("simple_source", 1, self.prefs["source"]),
            ("speed_preset", 3, self.prefs["speed"]),
            ("pdf_quality", 2, self.prefs["pdf_quality"]),
        ]:
            value = self.project.data.get(key, default)
            self.project.data[key] = (
                value if isinstance(value, int) and 0 <= value <= maximum else default
            )
        self.project.data.setdefault("paper", self.prefs["paper"])
        # Migrate saved advanced projects without dropping any captured side.
        if "phase" not in self.project.data:
            if not any(s["front"] or s["back"] for s in self.project.data["sheets"]):
                self.project.data["sheets"] = []
            if self.project.data["sheets"] and not self.project.missing("front"):
                self.project.data["phase"] = (
                    "backs"
                    if self.project.data["duplex"] and self.project.missing("back")
                    else "ready"
                )
            else:
                self.project.data["phase"] = "fronts"
        self.project.data.setdefault("delete_history", [])
        self.project.data.setdefault("extra_backs", [])
        self.project.save()

    def save_name(self):
        self.project.data["name"] = self.name.text().strip() or "Untitled document"
        self.project.save()

    def save_options(self, *args):
        self.project.data.update(
            simple_source=self.source.currentIndex(),
            simple_quality=self.quality.currentIndex(),
            speed_preset=self.quality.currentIndex(),
            simple_color=self.color.isChecked(),
            pdf_quality=self.pdf_quality.currentIndex(),
        )
        self.project.save()
        self.refresh_controls()

    def remember(self):
        HOME.mkdir(parents=True, exist_ok=True)
        (HOME / "last-project.txt").write_text(str(self.project.path))

    def message(self, text):
        QMessageBox.information(self, "Brother Scan", text)

    def error(self, text):
        QMessageBox.warning(self, "Scan needs attention", str(text))

    def choose_mode(self, duplex):
        if self.busy:
            return
        self.project.data["duplex"] = duplex
        if (
            self.project.data["phase"] == "ready"
            and duplex
            and self.project.missing("back")
        ):
            self.project.data["phase"] = "backs"
        if self.project.data["phase"] == "backs" and not duplex:
            self.project.data["phase"] = "ready"
        self.project.save()
        self.refresh()

    def refresh(self):
        self.refresh_controls()
        self.refresh_gallery()

    def refresh_controls(self):
        duplex = self.project.data["duplex"]
        phase = self.project.data["phase"]
        fronts = sum(bool(s["front"]) for s in self.project.data["sheets"])
        backs = sum(bool(s["back"]) for s in self.project.data["sheets"])
        extras = self.project.data["extra_backs"] if duplex else []
        self.paper_badge.setText(
            self.project.data.get("paper", "A4") + " · Whole stack"
        )
        self.flip_graphic.setVisible(duplex)
        self.one.setChecked(not duplex)
        self.two.setChecked(duplex)
        dpi = SCAN_DPI[self.quality.currentIndex()]
        mode = "color" if self.color.isChecked() else "grayscale"
        self.speed_hint.setText(
            f"{dpi} DPI · {mode}. "
            + (
                "Lowest supported DPI; whole-stack feeding reduces repeated startup delays."
                if dpi == 100
                else "More detail means more data. Choose Fastest for speed."
            )
        )
        for w in [
            self.one,
            self.two,
            self.source,
            self.quality,
            self.color,
            self.pdf_quality,
            self.scanner_btn,
            self.prefs_btn,
            self.name,
            self.main_btn,
            self.secondary,
        ]:
            w.setEnabled(not self.busy)
        self.stop_btn.setVisible(self.scanning)
        self.secondary.setVisible(True)
        if phase == "fronts":
            self.step.setText("1  Scan the fronts" if duplex else "Scan all pages")
            self.instruction.setText(
                (
                    "Load all remaining fronts in their original order. "
                    if fronts
                    else "Put your whole stack in the feeder. "
                )
                + (
                    "No counting needed—we stop when the feeder is empty."
                    if self.source.currentIndex() == 0
                    else "Place one side on the glass. Keep adding sides, then press Finished."
                )
            )
            self.main_btn.setText(
                ("Continue scanning fronts" if duplex else "Continue scanning")
                if fronts
                else ("Scan all fronts" if duplex else "Scan all pages")
            )
            self.secondary.setText(
                "Fronts finished →" if duplex else "Finished → Review"
            )
            self.secondary.setVisible(fronts > 0)
        elif phase == "backs":
            self.step.setText(
                "2  Flip the stack" if backs == 0 else "2  Finish the backs"
            )
            missing = len(self.project.missing("back"))
            self.instruction.setText(
                f"{fronts} fronts saved. Flip the whole stack. Feed the BACK of the LAST sheet first. Keep blank backs too."
                if backs == 0
                else f"{backs} backs saved, {missing} remaining. Leave scanned sheets aside; load the remaining backs in the same reverse order."
            )
            self.main_btn.setText(
                "Scan all backs" if backs == 0 else "Continue scanning backs"
            )
            self.secondary.setText(
                "Add more fronts" if backs == 0 else "Scan backs again"
            )
        else:
            self.step.setText("Ready to save")
            self.instruction.setText(
                "Browse the combined PDF below. Front 1 → back 1 → front 2 → back 2. Check the pairs, then save."
                if duplex
                else "Every scanned page is below, in order. Preview any page, then save one PDF."
            )
            self.main_btn.setText("Save PDF")
            self.secondary.setText(
                "Scan backs again" if duplex else "Add another stack"
            )
        if extras:
            self.step.setText("The two passes have different counts")
            self.instruction.setText(
                f"{fronts} fronts and {backs+len(extras)} backs were captured. Originals are safe. Reload ALL backs and scan the back pass again."
            )
            self.main_btn.setText("Scan backs again")
            self.secondary.hide()
        if self.scanning:
            self.step.setText("Scanning…")
            self.instruction.setText(
                "Each completed page appears below. You can browse and enlarge previews while scanning continues."
            )
        visible = any(
            p and not p.get("excluded")
            for sheet in self.project.data["sheets"]
            for side, p in sheet.items()
            if duplex or side == "front"
        )
        complete = (
            visible
            and bool(fronts)
            and not self.project.missing("front")
            and (not duplex or not self.project.missing("back"))
            and not extras
        )
        if phase == "ready" and not complete:
            self.main_btn.setEnabled(False)
            if not visible:
                self.step.setText("No pages to save")
                self.instruction.setText(
                    "Undo to restore deleted pages, or start a new document."
                )
        self.export_btn.setEnabled(complete and not self.busy)
        self.export_btn.setText("Save PDF")
        self.pdf_preview_btn.setEnabled(complete and not self.busy)
        self.tabs.setTabVisible(2, duplex)
        self.tabs.setTabText(0, "Combined PDF" if duplex else "All pages")
        self.update_edit_buttons()
        self.tabs.setTabText(
            1,
            f'Fronts ({sum(bool(s["front"]) and not s["front"].get("excluded") for s in self.project.data["sheets"])})',
        )
        self.tabs.setTabText(
            2,
            f'Backs ({sum(bool(s["back"]) and not s["back"].get("excluded") for s in self.project.data["sheets"])+len(extras)})',
        )

    def refresh_gallery(self, *args):
        if not hasattr(self, "gallery"):
            return
        selected = self.gallery.currentItem()
        old_key = selected.data(Qt.UserRole)[0] if selected else None
        selected_keys = {
            tuple(item.data(Qt.UserRole)[0]) for item in self.gallery.selectedItems()
        }
        self.gallery.blockSignals(True)
        self.gallery.clear()
        self.entries = []
        tab = self.tabs.currentIndex()
        duplex = self.project.data["duplex"]
        pdf_number = 0
        for i, sheet in enumerate(self.project.data["sheets"]):
            for side in ["front", "back"] if duplex else ["front"]:
                page = sheet[side]
                if page and page.get("excluded"):
                    continue
                pdf_number += 1
                if tab == 1 and side != "front" or tab == 2 and side != "back":
                    continue
                if tab and not page:
                    continue
                number = pdf_number
                caption = f"Page {number}  ·  {side}" if duplex else f"Page {number}"
                self.entries.append(((i, side), page, caption))
        if tab == 2:
            for j, page in enumerate(self.project.data["extra_backs"]):
                self.entries.append((("extra", j), page, "Unpaired back"))
        for key, page, caption in self.entries:
            item = QListWidgetItem(caption + ("" if page else "\nWaiting for back"))
            item.setData(Qt.UserRole, (key, page, caption))
            item.setSizeHint(
                QSize(
                    getattr(self, "thumb_width", 128) + 32,
                    round(getattr(self, "thumb_width", 128) * 1.27) + 42,
                )
            )
            item.setTextAlignment(Qt.AlignHCenter)
            if page:
                try:
                    cache_key = (
                        page["path"],
                        page.get("rotation", 0),
                        tuple(page.get("crop", [])),
                    )
                    if cache_key not in self.cache:
                        im = render(page)
                        ratio = self.devicePixelRatioF()
                        im.thumbnail(
                            (
                                round(getattr(self, "thumb_width", 128) * ratio),
                                round(getattr(self, "thumb_width", 128) * 1.27 * ratio),
                            )
                        )
                        pix = QPixmap.fromImage(ImageQt(im))
                        pix.setDevicePixelRatio(ratio)
                        ico = QIcon()
                        ico.addPixmap(pix, QIcon.Normal)
                        ico.addPixmap(pix, QIcon.Selected)
                        self.cache[cache_key] = ico
                    item.setIcon(self.cache[cache_key])
                except Exception:
                    item.setText(caption + "\nImage unavailable")
            else:
                canvas = QPixmap(128, 163)
                canvas.fill(QColor("#e3ece9"))
                item.setIcon(QIcon(canvas))
                item.setForeground(QColor("#7f9690"))
            self.gallery.addItem(item)
            if key == old_key:
                self.gallery.setCurrentItem(item, QItemSelectionModel.NoUpdate)
            if tuple(key) in selected_keys:
                item.setSelected(True)
        if self.gallery.currentRow() < 0 and self.gallery.count():
            self.gallery.setCurrentRow(0, QItemSelectionModel.ClearAndSelect)
        self.gallery.blockSignals(False)
        self.gallery_stack.setCurrentIndex(0 if self.gallery.count() else 1)
        self.preview()
        count = sum(bool(page) for _, page, _ in self.entries)
        self.counts.setText(
            f"{count} pages · Ctrl/Shift-click to select several · Delete to remove"
        )
        self.update_edit_buttons()

    def preview(self, *args):
        item = self.gallery.currentItem()
        if not item:
            self.preview_cache_key = None
            self.picture.setPixmap(QPixmap())
            self.picture.setText("Your pages will appear here.")
            self.preview_title.setText("Page preview")
            self.page_detail.setText("Click a page to preview it.")
            return
        key, page, caption = item.data(Qt.UserRole)
        self.preview_title.setText(caption)
        if not page:
            self.preview_cache_key = None
            self.picture.setPixmap(QPixmap())
            self.picture.setText("This back is not scanned yet.")
            self.page_detail.setText(
                "It will be paired automatically when you scan the backs."
            )
            return
        try:
            key = (
                page["path"],
                page.get("rotation", 0),
                tuple(page.get("crop", [])),
                self.picture.width(),
                self.picture.height(),
            )
            if getattr(self, "preview_cache_key", None) == key:
                return
            im = render(page)
            w, h = im.size
            ratio = self.devicePixelRatioF()
            im.thumbnail(
                (
                    round(max(1, self.picture.width() - 24) * ratio),
                    round(max(1, self.picture.height() - 24) * ratio),
                ),
                Image.Resampling.LANCZOS,
            )
            pix = QPixmap.fromImage(ImageQt(im))
            pix.setDevicePixelRatio(ratio)
            self.picture.setPixmap(pix)
            self.preview_cache_key = key
            self.page_detail.setText(
                f'{w} × {h} pixels · {page["dpi"]} DPI\nOriginal scan retained. Your PDF is compressed separately.'
            )
        except Exception as e:
            self.picture.setText("Preview unavailable")
            self.page_detail.setText(str(e))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "gallery"):
            QTimer.singleShot(80, self.preview)

    def navigate(self, delta):
        self.gallery.setCurrentRow(
            max(0, min(self.gallery.count() - 1, self.gallery.currentRow() + delta)),
            QItemSelectionModel.ClearAndSelect,
        )

    def update_edit_buttons(self):
        if not hasattr(self, "delete_btn"):
            return
        self.delete_btn.setEnabled(
            not self.busy
            and any(item.data(Qt.UserRole)[1] for item in self.gallery.selectedItems())
        )
        self.clear_btn.setEnabled(
            not self.busy
            and bool(self.project.data["sheets"] or self.project.data["extra_backs"])
        )
        self.undo_btn.setEnabled(
            not self.busy and bool(self.project.data.get("delete_history"))
        )

    def checkpoint_delete(self):
        snapshot = {
            key: copy.deepcopy(self.project.data[key])
            for key in ["sheets", "extra_backs", "phase"]
        }
        self.project.data.setdefault("delete_history", []).append(snapshot)
        self.project.data["delete_history"] = self.project.data["delete_history"][-20:]

    def delete_selected(self):
        if self.busy:
            return
        entries = [
            item.data(Qt.UserRole)
            for item in self.gallery.selectedItems()
            if item.data(Qt.UserRole)[1]
        ]
        if not entries:
            return
        if (
            QMessageBox.question(
                self,
                "Delete selected pages?",
                f"Remove {len(entries)} selected page(s) from this document? You can Undo. Original scan files stay saved.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        self.checkpoint_delete()
        extras = []
        for key, _, _ in entries:
            if key[0] == "extra":
                extras.append(key[1])
            else:
                self.project.data["sheets"][key[0]][key[1]]["excluded"] = True
        for index in sorted(extras, reverse=True):
            self.project.data["extra_backs"].pop(index)
        if (
            self.project.data["phase"] == "backs"
            and not self.project.missing("back")
            and not self.project.data["extra_backs"]
        ):
            self.project.data["phase"] = "ready"
        self.project.save()
        self.refresh()
        self.status.setText(
            f"Removed {len(entries)} page(s). Undo restores them. Original scan files and sheet pairing are preserved."
        )

    def clear_all(self):
        if self.busy or not (
            self.project.data["sheets"] or self.project.data["extra_backs"]
        ):
            return
        if (
            QMessageBox.question(
                self,
                "Clear the whole document?",
                "Remove ALL fronts, backs and combined pages from this document? You can Undo. Original scan files stay saved.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        self.checkpoint_delete()
        self.project.data.update(
            sheets=[], extra_backs=[], phase="fronts", pending=None
        )
        self.project.save()
        self.refresh()
        self.status.setText(
            "Document cleared. Ready for another stack. Undo restores the previous pages."
        )

    def undo_delete(self):
        if self.busy or not self.project.data.get("delete_history"):
            return
        snapshot = self.project.data["delete_history"].pop()
        self.project.data.update(snapshot)
        if not self.project.data["duplex"] and self.project.data["phase"] == "backs":
            self.project.data["phase"] = (
                "ready" if not self.project.missing("front") else "fronts"
            )
        self.project.save()
        self.refresh()
        self.status.setText("Undid the last edit.")

    def rotate(self):
        if self.busy:
            return
        item = self.gallery.currentItem()
        if not item:
            return
        key, page, _ = item.data(Qt.UserRole)
        if page:
            if key[0] == "extra":
                target = self.project.data["extra_backs"][key[1]]
            else:
                target = self.project.data["sheets"][key[0]][key[1]]
            self.checkpoint_delete()
            if target.get("crop"):
                x1, y1, x2, y2 = target["crop"]
                target["crop"] = [1 - y2, x1, 1 - y1, x2]
            target["rotation"] = (target.get("rotation", 0) + 90) % 360
            self.project.save()
            self.refresh_gallery()

    def crop_page(self):
        if self.busy:
            return
        item = self.gallery.currentItem()
        if not item or not item.data(Qt.UserRole)[1]:
            return
        key, page, _ = item.data(Qt.UserRole)
        full = copy.deepcopy(page)
        full.pop("crop", None)
        try:
            full_image = render(full)
        except Exception as e:
            self.error(f"Cannot crop this image: {e}")
            return
        dialog = CropDialog(self, full_image, page.get("crop"))
        if dialog.exec_() != QDialog.Accepted:
            return
        self.apply_crop(key, list(dialog.canvas.box), dialog.scope == "all")

    def apply_crop(self, key, box, all_pages=False):
        if self.busy:
            return
        self.checkpoint_delete()
        if all_pages:
            pages = [
                p
                for sheet in self.project.data["sheets"]
                for side, p in sheet.items()
                if p
                and not p.get("excluded")
                and (self.project.data["duplex"] or side == "front")
            ]
        else:
            pages = [
                (
                    self.project.data["extra_backs"][key[1]]
                    if key[0] == "extra"
                    else self.project.data["sheets"][key[0]][key[1]]
                )
            ]
        for p in pages:
            p["crop"] = list(box)
        self.cache.clear()
        self.project.save()
        self.refresh()
        self.status.setText(
            f"Cropped {len(pages)} page(s). Undo restores the previous crop. Originals remain saved."
        )

    def enlarge(self, *args):
        item = self.gallery.currentItem()
        if not item or not item.data(Qt.UserRole)[1]:
            return
        _, page, title = item.data(Qt.UserRole)
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(880, 900)
        box = QVBoxLayout(dialog)
        area = QScrollArea()
        image = QLabel()
        image.setAlignment(Qt.AlignCenter)
        area.setWidget(image)
        area.setAlignment(Qt.AlignCenter)
        box.addWidget(area)
        zoom = QSlider(Qt.Horizontal)
        zoom.setRange(25, 200)
        zoom.setValue(75)
        box.addWidget(label("Zoom · scroll to inspect fine text", "muted"))
        box.addWidget(zoom)
        try:
            original = render(page)
        except Exception as e:
            self.error(f"Cannot open this image: {e}")
            return

        def update(value):
            width = round(original.width * value / 100)
            height = round(original.height * value / 100)
            max_pixels = 24_000_000
            scale = min(1, (max_pixels / max(1, width * height)) ** 0.5)
            width, height = max(1, round(width * scale)), max(1, round(height * scale))
            scaled = original.resize((width, height), Image.Resampling.LANCZOS)
            image.setPixmap(QPixmap.fromImage(ImageQt(scaled)))
            image.resize(width, height)

        zoom.valueChanged.connect(update)
        update(75)
        dialog.exec_()

    def main_action(self):
        if self.busy:
            return
        if self.project.data["duplex"] and self.project.data["extra_backs"]:
            self.restart_backs()
            return
        if self.project.data["phase"] == "ready":
            self.export_pdf()
            return
        if not self.device:
            self.find_scanner()
            return
        self.scan_stack()

    def find_scanner(self):
        self.busy = True
        self.refresh_controls()
        self.status.setText("Finding your scanner…")
        self.discovery = QProcess(self)
        self.discovery.finished.connect(self.found_scanner)
        self.discovery.errorOccurred.connect(self.find_error)
        self.discovery.start("scanimage", ["-L"])
        proc = self.discovery
        QTimer.singleShot(
            45000, lambda: proc.kill() if proc.state() != QProcess.NotRunning else None
        )

    def find_error(self, error):
        if error == QProcess.FailedToStart:
            self.busy = False
            self.refresh_controls()
            self.open_scanner_setup()

    def open_scanner_setup(self, checked=False, devices=None, auto_scan=False):
        if self.busy:
            return
        dialog = ScannerSetup(self, self.scanner_config, devices)
        if dialog.exec_() == QDialog.Accepted:
            self.scanner_config = dialog.result_config
            self.device = self.scanner_config["device"]
            self.status.setText("Scanner selected. Ready to scan the whole stack.")
            if auto_scan:
                self.scan_stack()

    def found_scanner(self, *args):
        output = bytes(self.discovery.readAllStandardOutput()).decode(errors="replace")
        devices = re.findall(r"device `([^']+)'", output)
        self.busy = False
        self.refresh_controls()
        if len(devices) != 1 or "brother" not in output.lower():
            self.open_scanner_setup(devices=devices, auto_scan=True)
            return
        self.device = devices[0]
        self.scan_stack()

    def scan_stack(self):
        try:
            source, mode, dpi = scanner_options(
                self.scanner_config,
                self.device,
                self.source.currentIndex() == 1,
                self.color.isChecked(),
                SCAN_DPI[self.quality.currentIndex()],
            )
        except ValueError as e:
            self.error(e)
            return
        try:
            width, height = paper_dimensions(
                self.project.data.get("paper", "A4"),
                self.source.currentIndex() == 1,
                self.scanner_config.get("profile", "Brother brscan")
                == "Brother brscan",
            )
        except ValueError as e:
            self.error(e)
            return
        side = "back" if self.project.data["phase"] == "backs" else "front"
        sheets = self.project.data["sheets"]
        targets = list(reversed(self.project.missing("back"))) if side == "back" else []
        if side == "back" and not targets:
            self.project.data["phase"] = "ready"
            self.project.save()
            self.refresh()
            return
        self.project.data["delete_history"] = []
        self.project.checkpoint()
        self.job = self.project.path / ("pass-" + uuid.uuid4().hex[:8])
        self.job.mkdir()
        self.run = {
            "whole_stack": True,
            "folder": self.job.name,
            "side": side,
            "start": len(sheets),
            "targets": targets,
            "dpi": dpi,
        }
        self.project.data["pending"] = copy.deepcopy(self.run)
        self.project.save()
        self.seen = set()
        self.logs = bytearray()
        self.started = time.monotonic()
        self.stopped = False
        self.busy = True
        self.scanning = True
        self.refresh_controls()
        args = [
            "-d",
            self.device,
            "--source",
            source,
            "--mode",
            mode,
            "--resolution",
            str(self.run["dpi"]),
            "-x",
            str(width),
            "-y",
            str(height),
            "--format=pnm",
            "--batch=" + str(self.job / "page-%04d.pnm"),
        ]
        # A feeder runs until empty, with no page-count or range argument.
        if self.source.currentIndex() == 1:
            args += ["--batch-count=1"]
        self.last_scan_args = args
        self.proc = QProcess(self)
        self.proc.readyReadStandardError.connect(self.read_log)
        self.proc.finished.connect(self.scan_finished)
        self.proc.errorOccurred.connect(self.scan_error)
        self.proc.start("scanimage", args)
        self.timer.start()
        self.tabs.setCurrentIndex(1 if side == "front" else 2)

    def read_log(self):
        self.logs.extend(bytes(self.proc.readAllStandardError()))

    def collect(self):
        if not self.scanning:
            return
        changed = False
        for path in sorted(self.job.glob("page-*.pnm")):
            if path.name in self.seen:
                continue
            try:
                index = int(path.stem.split("-")[-1]) - 1
                if not scan_file_complete(path):
                    continue
            except (OSError, ValueError):
                continue
            page = {"path": str(path), "dpi": self.run["dpi"], "rotation": 0}
            if self.run["side"] == "front":
                i = self.run["start"] + index
                while len(self.project.data["sheets"]) <= i:
                    self.project.data["sheets"].append({"front": None, "back": None})
                self.project.data["sheets"][i]["front"] = page
            elif index < len(self.run["targets"]):
                self.project.data["sheets"][self.run["targets"][index]]["back"] = page
            else:
                self.project.data["extra_backs"].append(page)
            self.seen.add(path.name)
            self.project.save()
            changed = True
        if changed:
            self.refresh()
        self.status.setText(
            f"{len(self.seen)} pages captured this pass · {time.monotonic()-self.started:.0f}s · Saved automatically"
        )

    def scan_error(self, error):
        if error == QProcess.FailedToStart:
            self.scan_finished(-1, 0)

    def scan_finished(self, code, *args):
        if not self.scanning:
            return
        self.collect()
        self.read_log()
        self.timer.stop()
        self.scanning = False
        self.busy = False
        (self.job / "scanner.log").write_bytes(self.logs)
        self.project.data["pending"] = None
        clean = not self.stopped and code in (0, 7)
        if (
            self.run["side"] == "front"
            and clean
            and self.source.currentIndex() == 0
            and self.project.data["sheets"]
        ):
            self.project.data["phase"] = (
                "backs" if self.project.data["duplex"] else "ready"
            )
        if (
            self.run["side"] == "back"
            and not self.project.missing("back")
            and not self.project.data["extra_backs"]
        ):
            self.project.data["phase"] = "ready"
        self.project.save()
        self.refresh()
        if self.project.data["phase"] == "ready":
            self.tabs.setCurrentIndex(0)
        self.status.setText(
            f"{len(self.seen)} pages saved in {time.monotonic()-self.started:.1f}s. "
            + (
                "Stopped safely. Load only the remaining pages and continue."
                if self.stopped
                else "Review the previews above. Originals are preserved."
            )
        )
        if not clean and not self.stopped:
            self.device = ""
            self.error(
                "Scanning stopped. Completed pages are safe.\n"
                + self.logs.decode(errors="replace")[-900:]
            )

    def stop(self):
        if self.scanning:
            self.stopped = True
            proc = self.proc
            proc.terminate()
            QTimer.singleShot(
                3000,
                lambda: proc.kill() if proc.state() != QProcess.NotRunning else None,
            )

    def secondary_action(self):
        if self.busy:
            return
        phase = self.project.data["phase"]
        if phase == "fronts":
            if not self.project.data["sheets"]:
                return
            self.project.data["phase"] = (
                "backs" if self.project.data["duplex"] else "ready"
            )
        elif phase == "backs" and not any(
            s["back"] for s in self.project.data["sheets"]
        ):
            self.project.data["phase"] = "fronts"
        elif self.project.data["duplex"]:
            self.restart_backs()
            return
        else:
            self.project.data["phase"] = "fronts"
        self.project.save()
        self.refresh()
        self.tabs.setCurrentIndex(0 if self.project.data["phase"] == "ready" else 1)

    def restart_backs(self):
        if (
            QMessageBox.question(
                self,
                "Scan the whole back pass again?",
                "Reload ALL backs, with the last sheet first. Existing originals stay saved; the new pass will replace the pairing.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        self.project.data["delete_history"] = []
        for s in self.project.data["sheets"]:
            s["back"] = None
        self.project.data["extra_backs"] = []
        self.project.data["phase"] = "backs"
        self.project.save()
        self.refresh()

    def export_pdf(self, preview=False):
        if self.busy:
            return
        try:
            if self.project.data["duplex"] and self.project.data["extra_backs"]:
                raise ValueError(
                    "The two passes have different counts. Scan the whole back pass again."
                )
            pages = copy.deepcopy(self.project.ordered())
            if not pages:
                raise ValueError("Scan your document first.")
        except Exception as e:
            self.error(e)
            return
        filename = (
            re.sub(r"[^\w .-]", "_", self.project.data["name"])[:120].strip()
            or "Document"
        ) + ".pdf"
        self.preview_export = preview
        if preview:
            directory = self.project.path / "pdf-previews"
            directory.mkdir(exist_ok=True)
            path = str(directory / ("preview-" + uuid.uuid4().hex[:8] + ".pdf"))
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save your PDF", str(self.project.path / filename), "PDF (*.pdf)"
            )
            if not path:
                return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        dpi, q = 0, PDF_QUALITY[self.pdf_quality.currentIndex()]
        self.busy = True
        self.exporting = True
        self.refresh_controls()
        self.worker = ExportWorker(pages, path, q, dpi, False)
        self.worker.progress.connect(
            lambda a, b: self.status.setText(f"Saving PDF · {a} of {b} pages")
        )
        self.worker.done.connect(self.export_done)
        self.worker.failed.connect(self.export_error)
        self.worker.start()

    def export_done(self, path, size):
        self.worker.wait()
        self.busy = False
        self.exporting = False
        self.refresh_controls()
        self.status.setText(f"PDF saved · {size/1e6:.2f} MB · {path}")
        if self.preview_export or self.prefs["open_pdf"]:
            QProcess.startDetached("xdg-open", [path])

    def export_error(self, error):
        self.worker.wait()
        self.busy = False
        self.exporting = False
        self.refresh_controls()
        self.error(error)

    def new_document(self):
        if self.busy:
            return
        self.project = Project.create(count=0)
        self.project.data["duplex"] = self.two.isChecked()
        self.project.data["paper"] = self.prefs["paper"]
        self.normalize()
        self.save_options()
        self.name.setText("Untitled document")
        self.cache = {}
        self.remember()
        self.refresh()
        self.tabs.setCurrentIndex(0)

    def open_saved(self):
        if self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open a saved scan", str(HOME), "Scan project (project.json)"
        )
        if path:
            try:
                self.project = Project.load(path)
                self.normalize()
                self.name.setText(self.project.data["name"])
                for w in [self.source, self.quality, self.color, self.pdf_quality]:
                    w.blockSignals(True)
                self.source.setCurrentIndex(
                    self.project.data.get("simple_source", self.prefs["source"])
                )
                self.quality.setCurrentIndex(
                    self.project.data.get("speed_preset", self.prefs["speed"])
                )
                self.color.setChecked(
                    self.project.data.get("simple_color", self.prefs["color"])
                )
                self.pdf_quality.setCurrentIndex(
                    self.project.data.get("pdf_quality", self.prefs["pdf_quality"])
                )
                for w in [self.source, self.quality, self.color, self.pdf_quality]:
                    w.blockSignals(False)
                self.cache = {}
                self.remember()
                self.refresh()
            except Exception as e:
                self.error(e)

    def open_folder(self):
        QProcess.startDetached("xdg-open", [str(self.project.path)])

    def help(self):
        d = QDialog(self)
        d.setWindowTitle("Simple scanning")
        d.resize(700, 720)
        l = QVBoxLayout(d)
        t = QTextBrowser()
        t.setHtml(GUIDE)
        l.addWidget(t)
        l.addWidget(button("Got it", d.accept, True))
        d.exec_()

    def closeEvent(self, event):
        if self.busy:
            self.message(
                "Stop scanning or wait for saving to finish before closing. Your completed pages are safe."
            )
            event.ignore()
        else:
            self.save_name()
            (HOME / "last-project.txt").unlink(missing_ok=True)
            event.accept()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(SIMPLE_STYLE)
    HOME.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(HOME / "studio.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(
            None,
            "Brother Scan",
            "Scan Studio is already open. Close that window, then reopen for the simplified app.",
        )
        return
    # Every launch starts with an empty workspace. Use Open saved to resume.
    window = SimpleWindow()
    window.remember()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
