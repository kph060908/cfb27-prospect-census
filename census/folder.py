"""The capture folder: what a session writes and reads.

    meta.json      the league and what the session records about it (census init / census meta)
    setup.json     the frame source, the key backend, any box overrides (census setup)
    header_ref.png the Recruiting tab strip on the Prospect List (census start)
    cards/         card crops, c00001.jpg ...
    index.jsonl    one line per crop: card, chip, view, mode, time
    lists.json     auto mode: every position list walked to its end
    reads.jsonl    one OCR read per crop (census ocr)
    fixes.json     hand corrections (census fix)
    frames/        full grabs and calibration images
    steps.log      what was done, when
    out/           the finished output (census build)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").casefold()).strip("-") or "league"


class Folder:
    def __init__(self, path):
        self.path = Path(path).resolve()

    @classmethod
    def create(cls, league: str, path: str | None = None) -> "Folder":
        league = (league or "").strip()
        if not league:
            raise SystemExit("the league name is required: census init --league \"<league name>\"")
        p = Path(path) if path else Path("census-%s-%s" % (slug(league), dt.date.today().strftime("%Y%m%d")))
        p.mkdir(parents=True, exist_ok=True)
        f = cls(p)
        if (f.path / "meta.json").exists():
            raise SystemExit("%s already holds a capture (meta.json); pick another folder" % f.path)
        f.save_meta({
            "league": league, "league_as_shown": None, "team": None, "platform": None,
            "season": None, "class_year": None, "stage": None,
            "counters_open": {"remaining": None, "targets": None, "hours": None, "scholarships": None},
            "counters_close": {"remaining": None, "targets": None, "hours": None, "scholarships": None},
            "notes": "", "created": dt.datetime.now().isoformat(timespec="seconds"),
        })
        f.log("init: league %r" % league)
        return f

    @classmethod
    def open(cls, path: str | None) -> "Folder":
        p = path or os.environ.get("CENSUS_FOLDER") or "."
        f = cls(p)
        if not (f.path / "meta.json").exists():
            raise SystemExit("%s is not a capture folder (no meta.json). Run `census init --league ...` or pass "
                             "--folder" % f.path)
        return f

    # ------------------------------------------------------------------ json files
    def _load(self, name: str, default):
        p = self.path / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

    def _save(self, name: str, data) -> None:
        (self.path / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def meta(self) -> dict:
        return self._load("meta.json", {})

    def save_meta(self, m: dict) -> None:
        self._save("meta.json", m)

    def setup(self) -> dict:
        return self._load("setup.json", {})

    def save_setup(self, s: dict) -> None:
        self._save("setup.json", s)

    def lists(self) -> list:
        return self._load("lists.json", [])

    def add_list(self, entry: dict) -> None:
        ls = self.lists()
        ls.append(entry)
        self._save("lists.json", ls)

    def fixes(self) -> dict:
        return self._load("fixes.json", {})

    def save_fixes(self, fx: dict) -> None:
        self._save("fixes.json", fx)

    # ------------------------------------------------------------------ index and log
    def jsonl(self, name: str) -> list:
        p = self.path / name
        if not p.exists():
            return []
        with p.open(encoding="utf-8") as fh:
            return [json.loads(x) for x in fh if x.strip()]

    def count_index(self) -> int:
        p = self.path / "index.jsonl"
        if not p.exists():
            return 0
        with p.open(encoding="utf-8") as fh:
            return sum(1 for _ in fh)

    def add_index(self, entry: dict) -> None:
        with (self.path / "index.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log(self, msg: str) -> None:
        with (self.path / "steps.log").open("a", encoding="utf-8") as fh:
            fh.write("%s %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
