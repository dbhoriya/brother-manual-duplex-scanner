"""Regression checks for the audit (no hardware acquisition)."""

import copy
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from PyQt5.QtWidgets import QMessageBox
import test_simple
from test_simple import APP
from model import Project


class AuditTests(test_simple.SimpleTests):
    def test_export_keeps_prior_color_when_capture_changes_to_gray(self):
        self.w.choose_mode(False)
        self.run_scan([10])
        Image.new("RGB", (60, 80), (210, 30, 10)).save(
            self.project.ordered()[0]["path"]
        )
        self.w.color.setChecked(False)
        with patch("simple.QProcess.startDetached", return_value=True):
            self.w.export_pdf(preview=True)
            deadline = time.monotonic() + 8
            while self.w.busy and time.monotonic() < deadline:
                APP.processEvents()
                time.sleep(0.01)
            self.assertFalse(
                self.w.worker.args[4], "Capture mode must not recolor existing scans"
            )

    def test_new_document_keeps_visible_settings(self):
        self.w.quality.setCurrentIndex(2)
        self.w.color.setChecked(True)
        self.w.pdf_quality.setCurrentIndex(2)
        new = Project.create(self.root, count=0)
        with (
            patch("simple.Project.create", return_value=new),
            patch.object(self.w, "remember"),
        ):
            self.w.new_document()
        loaded = Project.load(new.path)
        self.assertEqual(loaded.data.get("speed_preset"), 2)
        self.assertTrue(loaded.data.get("simple_color"))
        self.assertEqual(loaded.data.get("pdf_quality"), 2)

    def test_one_sided_export_ignores_unpaired_backs(self):
        self.run_scan([10])
        self.run_scan([20, 30])
        self.w.choose_mode(False)
        self.assertTrue(self.w.export_btn.isEnabled())

    def test_crop_all_does_not_change_hidden_backs(self):
        self.run_scan([10])
        self.run_scan([20])
        self.w.choose_mode(False)
        self.w.apply_crop((0, "front"), [0.1, 0.1, 0.9, 0.9], True)
        self.assertNotIn("crop", self.project.data["sheets"][0]["back"])

    def test_all_deleted_disables_save_action(self):
        self.w.choose_mode(False)
        self.run_scan([10])
        with patch("simple.QMessageBox.question", return_value=QMessageBox.Yes):
            self.w.delete_selected()
        self.assertFalse(self.w.main_btn.isEnabled())

    def test_missing_image_does_not_crash_crop_or_zoom(self):
        self.w.choose_mode(False)
        self.run_scan([10])
        Path(self.project.ordered()[0]["path"]).unlink()
        self.w.crop_page()
        self.w.enlarge()
        self.assertEqual(len(self.errors), 2)

    def test_recovery_of_complete_backs_is_ready(self):
        self.run_scan([10, 30])
        folder = self.project.path / "crash"
        folder.mkdir()
        for i in [1, 2]:
            Image.new("L", (20, 20), 100).save(folder / f"page-{i:04d}.pnm")
        self.project.data["pending"] = {
            "whole_stack": True,
            "folder": "crash",
            "side": "back",
            "targets": [1, 0],
            "start": 2,
            "dpi": 100,
        }
        self.project.save()
        recovered = Project.load(self.project.path)
        self.assertEqual(recovered.data["phase"], "ready")

    def test_partial_pnm_not_treated_as_complete(self):
        from model import scan_file_complete

        path = self.root / "stream.pnm"
        path.write_bytes(b"P5\n20 30\n255\n" + b"x" * 500)
        self.assertFalse(scan_file_complete(path))
        with path.open("ab") as f:
            f.write(b"x" * 100)
        self.assertTrue(scan_file_complete(path))

    def test_failed_import_does_not_assign_half_a_batch(self):
        project = Project.create(self.root, count=2)
        good = self.root / "good.png"
        Image.new("L", (20, 30), 100).save(good)
        bad = self.root / "bad.png"
        bad.write_bytes(b"not an image")
        before = copy.deepcopy(project.data)
        with self.assertRaises(OSError):
            project.assign([(0, "front"), (1, "front")], [good, bad], 100)
        self.assertEqual(project.data, before)
        self.assertEqual(Project.load(project.path).data, before)

    def test_invalid_project_rejected_before_use(self):
        import json

        (self.project.path / "project.json").write_text(
            json.dumps({"version": 1, "sheets": [{"front": 123, "back": None}]})
        )
        with self.assertRaises(ValueError):
            Project.load(self.project.path)

    def test_gray_pdf_keeps_compact_gray_encoding(self):
        from model import export_pdf

        self.w.choose_mode(False)
        self.run_scan([10])
        path = self.root / "gray.pdf"
        export_pdf(self.project.ordered(), path, gray=False)
        self.assertIn(b"/ColorSpace /DeviceGray", path.read_bytes())

    def test_stored_setting_indices_are_clamped(self):
        self.project.data.update(
            speed_preset=999, pdf_quality=-8, simple_source="wrong"
        )
        self.w.normalize()
        self.assertEqual(self.project.data["speed_preset"], 0)
        self.assertEqual(self.project.data["pdf_quality"], 1)
        self.assertEqual(self.project.data["simple_source"], 0)

    def test_paper_preference_reaches_scan_command(self):
        self.w.choose_mode(False)
        self.project.data["paper"] = "A5"
        self.run_scan([10])
        args = self.w.last_scan_args
        self.assertEqual(args[args.index("-x") + 1], "148")
        self.assertEqual(args[args.index("-y") + 1], "210")

    def test_driver_profile_reaches_scan_command_and_metadata(self):
        from scanner_setup import PROFILES

        self.w.scanner_config = dict(
            PROFILES["Standard SANE / AirScan"], device="fake", dpi=[75, 150, 300]
        )
        self.w.choose_mode(False)
        self.w.color.setChecked(True)
        self.run_scan([10])
        args = self.w.last_scan_args
        self.assertEqual(args[args.index("--source") + 1], "ADF")
        self.assertEqual(args[args.index("--mode") + 1], "Color")
        self.assertEqual(args[args.index("--resolution") + 1], "75")
        self.assertEqual(self.project.ordered()[0]["dpi"], 75)

    def test_close_ends_workspace_but_keeps_originals(self):
        from PyQt5.QtGui import QCloseEvent

        self.w.choose_mode(False)
        self.run_scan([10])
        path = Path(self.project.ordered()[0]["path"])
        pointer = self.root / "last-project.txt"
        pointer.write_text(str(self.project.path))
        event = QCloseEvent()
        with patch("simple.HOME", self.root):
            self.w.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertFalse(pointer.exists())
        self.assertTrue(path.exists())
        self.assertEqual(len(Project.load(self.project.path).ordered()), 1)


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2)
