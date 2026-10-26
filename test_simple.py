import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from model import Project, render, export_pdf
from simple import SimpleWindow, SIMPLE_STYLE

APP = QApplication.instance() or QApplication([])
APP.setStyleSheet(SIMPLE_STYLE)


class SimpleTests(unittest.TestCase):
    def setUp(self):
        from preferences import DEFAULTS

        prefs = patch("simple.load_preferences", return_value=dict(DEFAULTS))
        prefs.start()
        self.addCleanup(prefs.stop)
        scanner = patch("simple.load_scanner_config", return_value={})
        scanner.start()
        self.addCleanup(scanner.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = Project.create(self.root, count=0)
        self.w = SimpleWindow(self.project)
        self.w.device = "fake"
        self.errors = []
        self.w.error = self.errors.append

    def tearDown(self):
        self.w.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def run_scan(self, values, code=7):
        binary = self.root / "scanimage"
        binary.write_text("""#!/usr/bin/python3
import sys,time
from PIL import Image
if '-L' in sys.argv:
 print("device `fake' is a Brother test scanner")
 sys.exit(0)
pattern=next(a.split('=',1)[1] for a in sys.argv if a.startswith('--batch='))
for i,value in enumerate(%r,1):
 Image.new('L',(60,80),value).save(pattern %% i)
 time.sleep(.04)
sys.exit(%d)
""" % (values, code))
        binary.chmod(0o755)
        with patch.dict(
            os.environ, {"PATH": str(self.root) + ":" + os.environ["PATH"]}
        ):
            self.w.main_action()
            deadline = time.monotonic() + 8
            while self.w.busy and time.monotonic() < deadline:
                APP.processEvents()
                time.sleep(0.01)
        self.assertFalse(self.w.busy)
        self.assertFalse(
            any(a.startswith("--batch-count") for a in self.w.last_scan_args)
        )

    def test_one_sided_entire_stack(self):
        self.w.choose_mode(False)
        self.run_scan([10, 20, 30, 40])
        self.assertEqual(len(self.project.ordered()), 4)
        self.assertEqual(self.project.data["phase"], "ready")
        self.assertTrue(self.w.export_btn.isEnabled())
        self.assertEqual(self.w.gallery.count(), 4)
        self.assertEqual(self.errors, [])

    def test_two_sided_reverse_pairing_and_gallery(self):
        self.run_scan([10, 30, 50])
        self.assertEqual(self.project.data["phase"], "backs")
        self.run_scan([60, 40, 20])
        self.assertEqual(self.project.data["phase"], "ready")
        values = []
        for page in self.project.ordered():
            with Image.open(page["path"]) as im:
                values.append(im.getpixel((0, 0)))
        self.assertEqual(values, [10, 20, 30, 40, 50, 60])
        self.assertEqual(self.w.gallery.count(), 6)
        self.w.tabs.setCurrentIndex(1)
        self.assertEqual(self.w.gallery.count(), 3)
        self.w.tabs.setCurrentIndex(2)
        self.assertEqual(self.w.gallery.count(), 3)

    def test_partial_backs_resume_without_counts(self):
        self.run_scan([10, 30, 50])
        self.run_scan([60])
        self.assertEqual(self.project.data["phase"], "backs")
        self.assertFalse(self.w.export_btn.isEnabled())
        self.run_scan([40, 20])
        self.assertEqual(self.project.data["phase"], "ready")
        self.assertEqual(self.project.missing("back"), [])

    def test_extra_back_is_preserved_and_blocks_export(self):
        self.run_scan([10])
        self.run_scan([20, 30])
        self.assertEqual(len(self.project.data["extra_backs"]), 1)
        self.assertFalse(self.w.export_btn.isEnabled())
        self.w.tabs.setCurrentIndex(2)
        self.assertEqual(self.w.gallery.count(), 2)

    def test_front_error_resumes_remaining_stack(self):
        self.run_scan([10], 3)
        self.assertEqual(self.project.data["phase"], "fronts")
        self.run_scan([30, 50])
        self.assertEqual(len(self.project.data["sheets"]), 3)
        self.assertEqual(self.project.data["phase"], "backs")

    def test_unknown_count_crash_recovery(self):
        folder = self.project.path / "pass-crash"
        folder.mkdir()
        Image.new("L", (20, 20), 100).save(folder / "page-0001.pnm")
        self.project.data["pending"] = {
            "whole_stack": True,
            "folder": folder.name,
            "side": "front",
            "start": 0,
            "targets": [],
            "dpi": 150,
        }
        self.project.save()
        loaded = Project.load(self.project.path)
        self.assertEqual(len(loaded.data["sheets"]), 1)
        self.assertEqual(loaded.data["phase"], "fronts")
        self.assertIsNone(loaded.data["pending"])

    def test_delete_keeps_duplex_pairing_and_undo(self):
        self.run_scan([10, 30])
        self.run_scan([40, 20])
        paths = [p["path"] for p in self.project.ordered()]
        self.w.gallery.clearSelection()
        self.w.gallery.setCurrentRow(0)
        with patch("simple.QMessageBox.question", return_value=QMessageBox.Yes):
            self.w.delete_selected()
        values = []
        for p in self.project.ordered():
            with Image.open(p["path"]) as im:
                values.append(im.getpixel((0, 0)))
        self.assertEqual(values, [20, 30, 40])
        self.assertEqual(len(self.project.data["sheets"]), 2)
        self.assertTrue(all(Path(p).exists() for p in paths))
        self.w.undo_delete()
        self.assertEqual(len(self.project.ordered()), 4)

    def test_clear_all_and_restore(self):
        self.w.choose_mode(False)
        self.run_scan([10, 20])
        with patch("simple.QMessageBox.question", return_value=QMessageBox.Yes):
            self.w.clear_all()
        self.assertEqual(self.project.data["sheets"], [])
        self.assertEqual(self.project.data["phase"], "fronts")
        self.w.undo_delete()
        self.assertEqual(len(self.project.ordered()), 2)

    def test_delete_key_only_in_gallery(self):
        self.w.choose_mode(False)
        self.run_scan([10, 20])
        self.w.show()
        self.w.activateWindow()
        self.w.gallery.setFocus()
        APP.processEvents()
        with patch("simple.QMessageBox.question", return_value=QMessageBox.Yes):
            QTest.keyClick(self.w.gallery, Qt.Key_Delete)
        self.assertEqual(len(self.project.ordered()), 1)
        self.w.name.setFocus()
        self.w.name.setText("AB")
        self.w.name.setCursorPosition(0)
        QTest.keyClick(self.w.name, Qt.Key_Delete)
        self.assertEqual(self.w.name.text(), "B")
        self.assertEqual(len(self.project.ordered()), 1)

    def test_crop_one_all_and_undo(self):
        self.w.choose_mode(False)
        self.run_scan([10, 20])
        self.w.apply_crop((0, "front"), [0.1, 0.1, 0.9, 0.9])
        self.assertEqual(render(self.project.ordered()[0]).size, (48, 64))
        self.assertEqual(render(self.project.ordered()[1]).size, (60, 80))
        self.w.apply_crop((0, "front"), [0, 0, 0.5, 0.5], True)
        self.assertEqual(
            [render(p).size for p in self.project.ordered()], [(30, 40), (30, 40)]
        )
        self.w.undo_delete()
        self.assertEqual(render(self.project.ordered()[0]).size, (48, 64))
        path = self.project.ordered()[0]["path"]
        with Image.open(path) as im:
            self.assertEqual(im.size, (60, 80))

    def test_crop_pdf_has_cropped_page_size(self):
        import subprocess

        self.w.choose_mode(False)
        self.run_scan([10])
        self.w.apply_crop((0, "front"), [0, 0, 0.5, 0.5])
        pdf = self.root / "cropped.pdf"
        export_pdf(self.project.ordered(), pdf)
        info = subprocess.check_output(["pdfinfo", str(pdf)], text=True)
        self.assertIn("21.6 x 28.8 pts", info)

    def test_actual_pdf_preview(self):
        self.w.choose_mode(False)
        self.run_scan([10, 20])
        with patch("simple.QProcess.startDetached", return_value=True) as opened:
            self.w.export_pdf(preview=True)
            deadline = time.monotonic() + 8
            while self.w.busy and time.monotonic() < deadline:
                APP.processEvents()
                time.sleep(0.01)
            self.assertFalse(self.w.busy)
            opened.assert_called_once()
            path = Path(opened.call_args[0][1][0])
            self.assertTrue(path.read_bytes().startswith(b"%PDF"))

    def test_multiselect_delete(self):
        self.w.choose_mode(False)
        self.run_scan([10, 20, 30])
        self.w.gallery.clearSelection()
        self.w.gallery.item(0).setSelected(True)
        self.w.gallery.item(2).setSelected(True)
        with patch("simple.QMessageBox.question", return_value=QMessageBox.Yes):
            self.w.delete_selected()
        self.assertEqual(len(self.project.ordered()), 1)
        with Image.open(self.project.ordered()[0]["path"]) as im:
            self.assertEqual(im.getpixel((0, 0)), 20)
        self.w.undo_delete()
        self.assertEqual(len(self.project.ordered()), 3)

    def test_fastest_default_and_independent_color(self):
        self.w.choose_mode(False)
        self.run_scan([10])
        args = self.w.last_scan_args
        self.assertEqual(args[args.index("--resolution") + 1], "100")
        self.assertEqual(args[args.index("--mode") + 1], "True Gray")
        self.w.secondary_action()
        self.w.color.setChecked(True)
        self.w.pdf_quality.setCurrentIndex(2)
        self.run_scan([20])
        args = self.w.last_scan_args
        self.assertEqual(args[args.index("--resolution") + 1], "100")
        self.assertEqual(args[args.index("--mode") + 1], "24bit Color[Fast]")
        self.assertEqual(self.project.data["speed_preset"], 0)
        self.assertEqual(self.project.data["pdf_quality"], 2)

    def test_detail_resolution_choices(self):
        self.w.choose_mode(False)
        for index, dpi in [(1, 150), (2, 300), (3, 600)]:
            if self.project.data["phase"] == "ready":
                self.w.secondary_action()
            self.w.quality.setCurrentIndex(index)
            self.run_scan([10])
            args = self.w.last_scan_args
            self.assertEqual(args[args.index("--resolution") + 1], str(dpi))


if __name__ == "__main__":
    unittest.main(verbosity=2)
