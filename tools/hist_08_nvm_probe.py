"""HIST-08 NVM recovery probe (research only, GitHub Actions only).

Asks the imgix host for its own metadata (?fm=json) and inspects what each page URL really serves
(content type, PNG dimensions, share of non-white pixels, OCR character count at several scales).
Raw bytes stay in memory; only aggregates and short OCR line samples are printed. Nothing is committed.
"""
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import hist_02_acquire as acq  # noqa: E402

VM = "https://vmn-vastgoedmarkt.imgix.net/uploads/2024/07/kerncijfers-vastgoedmarkt-1974-2024.pdf"
SUFFIXES = ["?fm=png&w=3000", "?fm=png&w=3000&page=3"]


def png_dims(raw):
    return struct.unpack(">II", raw[16:24]) if raw[:8] == b"\x89PNG\r\n\x1a\n" else None


def ocr(raw, psm, scale, invert=False):
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "p.png"
        f.write_bytes(raw)
        cmd = ["tesseract", str(f), "-", "--psm", str(psm), "-l", "nld+eng"]
        if scale != 1:
            try:
                from PIL import Image
                im = Image.open(f).convert("L")
                if invert:
                    from PIL import ImageOps
                    im = ImageOps.autocontrast(ImageOps.invert(im))
                im = im.resize((im.width * scale, im.height * scale))
                g = Path(td) / "q.png"
                im.save(g)
                cmd[1] = str(g)
            except Exception as exc:  # noqa: BLE001
                return f"PIL_UNAVAILABLE {exc}"
        p = subprocess.run(cmd, capture_output=True, timeout=240)
        return p.stdout.decode("utf-8", "replace")


def main():
    acq.SOURCES.update({"nvm" + re.sub(r"\W+", "-", s): (VM + s, "bin") for s in SUFFIXES})
    for s in SUFFIXES:
        sid = "nvm" + re.sub(r"\W+", "-", s)
        try:
            raw, rec = acq.fetch(sid)
        except Exception as exc:  # noqa: BLE001
            print(f"RESULT {s}: NOT_RETRIEVED {exc}")
            continue
        head = raw[:8]
        print(f"RESULT {s}: {rec['bytes']} bytes sha256 {rec['sha256'][:16]} magic {head!r} png_dims {png_dims(raw)}")
        if raw[:1] == b"{":
            print("JSON", raw[:1500].decode("utf-8", "replace"))
        if png_dims(raw):
            try:
                from PIL import Image
                im = Image.open(__import__("io").BytesIO(raw)).convert("L")
                px = list(im.getdata())
                dark = sum(1 for v in px if v < 200) / len(px)
                print(f"  mode L size {im.size} dark_share {dark:.4f} distinct {len(set(px))}")
            except Exception as exc:  # noqa: BLE001
                print(f"  pixel stats unavailable: {exc}")
            for psm in (6, 11, 12):
                for scale in (1, 2):
                    t = ocr(raw, psm, scale, invert=True)
                    print(f"  OCR inverted psm{psm} x{scale}: {len(t)} chars; sample: {re.sub(chr(10), ' | ', t[:900])!r}")


if __name__ == "__main__":
    main()
