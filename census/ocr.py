"""Read card crops and screen labels with RapidOCR.

The engine settings (PP-OCRv6 detector, PP-OCRv6 medium recognizer, no angle classifier) and the card reader are
the ones that read every field of more than 19,000 real recruit cards. The first run downloads the OCR models
(internet needed once).
"""
from __future__ import annotations

import json
import re
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image

from .geometry import CARD_SIZE

_ENGINE = None


def engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr import ModelType, OCRVersion, RapidOCR
        _ENGINE = RapidOCR(params={
            "Global.use_cls": False, "Global.text_score": 0.0, "Global.log_level": "error",
            "Det.ocr_version": OCRVersion.PPOCRV6, "Rec.ocr_version": OCRVersion.PPOCRV6,
            "Rec.model_type": ModelType.MEDIUM,
            "Det.limit_type": "max", "Det.limit_side_len": 2000,
        })
    return _ENGINE


def ocr_image(img: Image.Image) -> list[tuple]:
    """[(text, score, x0, y0, x1, y1)] sorted top to bottom, left to right."""
    out = engine()(np.asarray(img.convert("RGB")))
    boxes = []
    for b, t, s in zip(out.boxes if out.boxes is not None else [], out.txts or [], out.scores or []):
        xs, ys = [p[0] for p in b], [p[1] for p in b]
        boxes.append((t.strip(), round(float(s), 4), int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))))
    return sorted(boxes, key=lambda b: (b[3], b[2]))


def read_label(img: Image.Image) -> str:
    """The text of a small screen box (the L2 position box, the R2 view pill), upper case."""
    big = img.resize((img.width * 2, img.height * 2))
    return " ".join(b[0] for b in ocr_image(big) if b[1] > 0.4).strip().upper()


def chip_name(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalnum()) or "?"


def view_name(text: str) -> str:
    return re.sub(r"\s+", " ", text.upper()).strip() or "?"


# ---------------------------------------------------------------------------------------------- the card
LABELS = {"POSITION": "position", "ARCHETYPE": "archetype", "CLASS&NIL": "classnil", "HEIGHT&WEIGHT": "hw",
          "HOMETOWN": "hometown"}


def _norm(t: str) -> str:
    return re.sub(r"[^A-Z&]", "", t.upper())


def _stars_by_pixels(img: Image.Image) -> int:
    """Filled stars on the rank line: the bright pixel share in each of the five star cells."""
    g = img.convert("L")
    n = 0
    for k in range(5):
        x0 = 10 + k * 24
        h = g.crop((x0 + 4, 88, x0 + 18, 102)).histogram()
        if sum(h[200:]) / max(1, sum(h)) > 0.45:
            n += 1
    return n


def parse_card(img: Image.Image) -> dict:
    """One card crop -> its fields (public names). A card that can't be read keeps `error` and its raw boxes."""
    img = img.convert("RGB")
    if img.size != CARD_SIZE:
        img = img.resize(CARD_SIZE, Image.LANCZOS)
    big = img.resize((img.width * 2, img.height * 2))
    boxes = [b for b in ocr_image(big) if b[1] > 0.4]
    boxes = [(t, x0 / 2, y0 / 2, x1 / 2, y1 / 2, s) for t, s, x0, y0, x1, y1 in boxes]
    out = {"raw": [(t, int(x0), int(y0), int(x1), int(y1)) for t, x0, y0, x1, y1, _ in boxes]}
    k = {}
    try:
        top = sorted([b for b in boxes if b[2] < 85], key=lambda b: (b[2], b[1]))
        first = [b for b in top if b[2] < 25 and b[4] <= 45]
        last = [b for b in top if 25 <= b[2] < 60 and b[4] < 95 and "NAT" not in b[0].upper()]
        k["first"] = " ".join(b[0] for b in sorted(first, key=lambda b: b[1]))
        k["last"] = " ".join(b[0] for b in sorted(last, key=lambda b: b[1]))
        rk = " ".join(b[0] for b in boxes if 80 <= (b[2] + b[4]) / 2 <= 112)
        m = re.search(r"N[A4]T\s*:?\s*(\d+).*?ST[A4]\s*:?\s*(\d+).*?P[O0]S\s*:?\s*(\d+)", rk.replace("|", " "), re.I)
        if m:
            k["nat"], k["sta"], k["posrank"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        nstar = rk.count("★")
        k["stars"] = nstar if 1 <= nstar <= 5 else _stars_by_pixels(img)
        labels = {}
        for t, x0, y0, x1, y1, _ in boxes:
            key = _norm(t)
            for lab, name in LABELS.items():
                if key == lab or (lab in key and len(key) <= len(lab) + 2):
                    labels[name] = (x0, y0, x1, y1)
        for name, (lx0, ly0, lx1, ly1) in labels.items():
            col = [b for b in boxes if ly0 + 12 <= b[2] <= ly1 + 40 and lx0 - 15 <= b[1] <= lx0 + 140
                   and (b[1] < lx0 + 60 or name == "classnil") and _norm(b[0]) not in LABELS]
            col.sort(key=lambda b: b[1])
            k[name] = " ".join(b[0] for b in col).strip()
        cn = k.pop("classnil", "")
        m = re.match(r"^\s*(HS|JC\s*\(\s*\w+\s*\)|JC)", cn, re.I)
        k["cls"] = re.sub(r"\s+", " ", m.group(1)).upper().replace("( ", "(").replace(" )", ")") if m else cn
        mn = re.search(r"(\d{1,4})\s*$", cn)                       # the Expected NIL, last in its column
        k["nil"] = int(mn.group(1)) if mn else None
        hw = k.pop("hw", "")
        m = re.search(r"(\d)\s*['’]\s*(\d{1,2})", hw)
        mw = re.search(r"(\d{3})\s*[lI1|]bs?", hw, re.I)           # OCR reads "lbs" as "Ibs" now and then
        k["height"] = int(m.group(1)) * 12 + int(m.group(2)) if m else None
        k["weight"] = int(mw.group(1)) if mw else None
        if "nat" not in k or not k.get("last") or not k.get("hometown"):
            out["error"] = "incomplete"
    except Exception as e:  # noqa: BLE001
        out["error"] = repr(e)
    out.update({
        "national_rank": k.get("nat"), "state_rank": k.get("sta"), "position_rank": k.get("posrank"),
        "first_name": k.get("first") or None, "last_name": k.get("last") or None, "stars": k.get("stars"),
        "position": k.get("position") or None, "archetype": k.get("archetype") or None, "class": k.get("cls") or None,
        "expected_nil": k.get("nil"), "height_in": k.get("height"), "weight_lb": k.get("weight"),
        "hometown": k.get("hometown") or None,
    })
    return out


def _parse_path(item: tuple) -> dict:
    path, meta = item
    rec = parse_card(Image.open(path))
    rec.update({"card": Path(path).stem, "chip": meta.get("chip"), "view": meta.get("view"), "mode": meta.get("mode")})
    return rec


def ocr_folder(folder: Path, workers: int = 2) -> tuple[int, int]:
    """OCR every card crop not yet in reads.jsonl. Returns (new reads, reads with errors among them)."""
    index = {}
    ip = folder / "index.jsonl"
    if ip.exists():
        with ip.open(encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                index[r["card"]] = r
    out = folder / "reads.jsonl"
    done = set()
    if out.exists():
        with out.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["card"])
                except Exception:  # noqa: BLE001  (a line cut by a crash is read again)
                    pass
    todo = [(str(p), index.get(p.stem, {})) for p in sorted((folder / "cards").glob("*.jpg")) if p.stem not in done]
    errors = 0
    if not todo:
        return 0, 0
    with Pool(max(1, workers)) as pool, out.open("a", encoding="utf-8") as fh:
        for rec in pool.imap(_parse_path, todo, chunksize=8):
            errors += 1 if rec.get("error") else 0
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
    return len(todo), errors
