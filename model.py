"""Persistent sheet-slot model and bounded-memory PDF export."""

import copy
import io
import json
import os
import time
import uuid
from pathlib import Path
from PIL import Image, ImageOps

HOME = Path.home() / "Scans" / "Studio"


def atomic_json(path, data):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class Project:
    def __init__(self, path, data):
        self.path = Path(path)
        self.data = data

    @classmethod
    def create(cls, root=HOME, count=1):
        path = Path(root) / (
            "scan-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        )
        path.mkdir(parents=True)
        p = cls(
            path,
            {
                "version": 1,
                "name": "Untitled document",
                "duplex": True,
                "sheets": [{"front": None, "back": None} for _ in range(count)],
                "history": [],
                "pending": None,
            },
        )
        p.save()
        return p

    @classmethod
    def load(cls, path):
        path = Path(path)
        path = path.parent if path.is_file() else path
        data = json.loads((path / "project.json").read_text())
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or not isinstance(data.get("sheets"), list)
        ):
            raise ValueError("Not a Scan Studio project.")
        for sheet in data["sheets"]:
            if not isinstance(sheet, dict) or not {"front", "back"} <= sheet.keys():
                raise ValueError("Invalid sheet record in project.")
            for page in (sheet["front"], sheet["back"]):
                if page is not None and (
                    not isinstance(page, dict)
                    or not isinstance(page.get("path"), str)
                    or not isinstance(page.get("dpi"), (int, float))
                    or page["dpi"] <= 0
                ):
                    raise ValueError("Invalid page record in project.")
        data.setdefault("name", "Untitled document")
        data.setdefault("duplex", True)
        data.setdefault("history", [])
        p = cls(path, data)
        p.recover()
        return p

    def save(self):
        atomic_json(self.path / "project.json", self.data)

    def checkpoint(self):
        self.data["history"].append(copy.deepcopy(self.data["sheets"]))
        self.data["history"] = self.data["history"][-20:]

    def resize(self, count):
        if count < len(self.data["sheets"]) and any(
            s["front"] or s["back"] for s in self.data["sheets"][count:]
        ):
            raise ValueError(
                "Those sheets contain scans. Clear their slots before reducing the sheet count. Originals remain saved."
            )
        self.checkpoint()
        self.data["sheets"] = self.data["sheets"][:count] + [
            {"front": None, "back": None}
            for _ in range(max(0, count - len(self.data["sheets"])))
        ]
        self.save()

    def targets(self, side, start, reverse=False, limit=0):
        n = len(self.data["sheets"])
        if side not in ("front", "back") or not 0 <= start < n:
            raise ValueError("Choose an existing sheet and side.")
        ids = list(range(start, -1, -1)) if reverse else list(range(start, n))
        return [(i, side) for i in (ids[:limit] if limit else ids)]

    def missing(self, side):
        return [i for i, s in enumerate(self.data["sheets"]) if not s[side]]

    def assign(self, targets, files, dpi, copy_files=True):
        if len(files) > len(targets):
            raise ValueError(
                "Too many images for the selected range. Increase sheet count or change the starting sheet."
            )
        staged = []
        for (sheet, side), source in zip(targets, files):
            if not 0 <= sheet < len(self.data["sheets"]) or side not in (
                "front",
                "back",
            ):
                raise ValueError("Invalid destination sheet.")
            source = Path(source)
            with Image.open(source) as im:
                im.load()
                if copy_files:
                    dest = self.path / ("original-" + uuid.uuid4().hex + ".png")
                    im.save(dest)
                else:
                    dest = source
            staged.append((sheet, side, {"path": str(dest), "dpi": dpi, "rotation": 0}))
        before = copy.deepcopy(self.data)
        try:
            self.checkpoint()
            for sheet, side, page in staged:
                self.data["sheets"][sheet][side] = page
            self.save()
        except Exception:
            self.data = before
            raise

    def recover(self):
        pending = self.data.get("pending")
        if not pending:
            return 0
        count = 0
        if pending.get("whole_stack"):
            files = sorted((self.path / pending["folder"]).glob("page-*.pnm"))
            for path in files:
                try:
                    index = int(path.stem.split("-")[-1]) - 1
                    with Image.open(path) as im:
                        im.load()
                except (OSError, ValueError):
                    continue
                page = {"path": str(path), "dpi": pending["dpi"], "rotation": 0}
                if pending["side"] == "front":
                    sheet = pending["start"] + index
                    while len(self.data["sheets"]) <= sheet:
                        self.data["sheets"].append({"front": None, "back": None})
                    self.data["sheets"][sheet]["front"] = page
                elif index < len(pending["targets"]):
                    sheet = pending["targets"][index]
                    self.data["sheets"][sheet]["back"] = page
                else:
                    extra = self.data.setdefault("extra_backs", [])
                    if not any(p["path"] == page["path"] for p in extra):
                        extra.append(page)
                count += 1
            self.data["phase"] = pending["side"] + "s"
            if (
                pending["side"] == "back"
                and not self.missing("back")
                and not self.data.get("extra_backs")
            ):
                self.data["phase"] = "ready"
            self.data["pending"] = None
            self.save()
            return count
        for index, (sheet, side) in enumerate(pending["targets"]):
            path = self.path / pending["folder"] / f"page-{index+1:04d}.pnm"
            try:
                with Image.open(path) as im:
                    im.load()
            except (OSError, ValueError):
                continue
            self.data["sheets"][sheet][side] = {
                "path": str(path),
                "dpi": pending["dpi"],
                "rotation": 0,
            }
            count += 1
        self.data["pending"] = None
        self.save()
        return count

    def undo(self):
        if self.data["history"]:
            self.data["sheets"] = self.data["history"].pop()
            self.save()

    def ordered(self, require_complete=True):
        result = []
        sides = ("front", "back") if self.data["duplex"] else ("front",)
        for i, s in enumerate(self.data["sheets"]):
            for side in sides:
                if s[side]:
                    if not s[side].get("excluded", False):
                        result.append(s[side])
                elif require_complete:
                    raise ValueError(
                        f"Sheet {i+1} is missing its {side}. Scan/import that side, or insert an intentional blank."
                    )
        return result


def scan_file_complete(path):
    try:
        with Image.open(path) as im:
            if (
                im.format == "PPM"
                and im.tile
                and im.tile[0][0] == "raw"
                and im.mode in ("L", "RGB", "1")
            ):
                offset = im.tile[0][2]
                raw = im.tile[0][3]
                rawmode = raw[0] if isinstance(raw, tuple) else raw
                if rawmode in ("L", "RGB", "1"):
                    stride = (
                        (im.width + 7) // 8
                        if im.mode == "1"
                        else im.width * (3 if im.mode == "RGB" else 1)
                    )
                    return Path(path).stat().st_size >= offset + stride * im.height
            im.load()
        return True
    except (OSError, ValueError):
        return False


def render(page):
    with Image.open(page["path"]) as src:
        im = ImageOps.exif_transpose(src).convert("RGB")
    if page.get("rotation"):
        im = im.rotate(-page["rotation"], expand=True)
    if page.get("crop"):
        x1, y1, x2, y2 = page["crop"]
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("Invalid crop area.")
        w, h = im.size
        left, top = min(w - 1, round(x1 * w)), min(h - 1, round(y1 * h))
        right, bottom = min(w, max(left + 1, round(x2 * w))), min(
            h, max(top + 1, round(y2 * h))
        )
        im = im.crop((left, top, right, bottom))
    return im


def export_pdf(pages, target, quality=78, max_dpi=150, gray=False, progress=None):
    """One image at a time, JPEG compression, true physical page size, atomic output."""
    if not pages:
        raise ValueError("No pages to export.")
    target = Path(target)
    tmp = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    offsets = {}
    n = len(pages)
    try:
        with tmp.open("wb") as f:
            f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

            def obj(num, body):
                offsets[num] = f.tell()
                f.write(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")

            obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
            kids = " ".join(f"{3+i*3} 0 R" for i in range(n))
            obj(2, f"<< /Type /Pages /Count {n} /Kids [{kids}] >>".encode())
            for i, page in enumerate(pages):
                im = render(page)
                width, height = im.size
                dpi = page["dpi"]
                if dpi <= 0:
                    raise ValueError("Invalid page DPI.")
                pw, ph = width * 72 / dpi, height * 72 / dpi
                if max_dpi and dpi > max_dpi:
                    im.thumbnail(
                        (
                            max(1, round(width * max_dpi / dpi)),
                            max(1, round(height * max_dpi / dpi)),
                        ),
                        Image.Resampling.LANCZOS,
                    )
                with Image.open(page["path"]) as source:
                    original_gray = source.mode in ("1", "L", "I", "I;16")
                if gray or original_gray:
                    im = im.convert("L")
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=quality, optimize=True)
                data = buf.getvalue()
                w, h = im.size
                color = "/DeviceGray" if im.mode == "L" else "/DeviceRGB"
                a = 3 + i * 3
                obj(
                    a,
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw:.4f} {ph:.4f}] /Resources << /XObject << /Im0 {a+1} 0 R >> >> /Contents {a+2} 0 R >>".encode(),
                )
                obj(
                    a + 1,
                    f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace {color} /BitsPerComponent 8 /Filter /DCTDecode /Length {len(data)} >>\nstream\n".encode()
                    + data
                    + b"\nendstream",
                )
                content = f"q {pw:.4f} 0 0 {ph:.4f} 0 0 cm /Im0 Do Q".encode()
                obj(
                    a + 2,
                    f"<< /Length {len(content)} >>\nstream\n".encode()
                    + content
                    + b"\nendstream",
                )
                im.close()
                if progress:
                    progress(i + 1, n)
            start = f.tell()
            total = 3 + n * 3
            f.write(f"xref\n0 {total}\n0000000000 65535 f \n".encode())
            for i in range(1, total):
                f.write(f"{offsets[i]:010d} 00000 n \n".encode())
            f.write(
                f"trailer\n<< /Size {total} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return target.stat().st_size
