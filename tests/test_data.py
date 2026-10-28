"""Checks and build on synthetic reads (made-up recruits): python -m unittest discover tests"""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from census.capture import POSITION_CHIPS
from census.data import build, run_checks
from census.folder import Folder

LABEL = {"QB": "QB (R)", "OT": "LT", "OG": "RG", "EDGE": "LEDG", "OLB": "SAM"}
STATES = ["TX", "OH", "CA"]


def synthetic_class(per_list: int = 2, wr: int = 2) -> list[dict]:
    """per_list recruits on each of the 17 position lists (wr on WR), national ranks 1..n, state ranks per state."""
    recs, nat, seen = [], 0, {}
    for chip in POSITION_CHIPS:
        for p in range(1, (wr if chip == "WR" else per_list) + 1):
            nat += 1
            st = STATES[nat % 3]
            seen[st] = seen.get(st, 0) + 1
            recs.append({"national_rank": nat, "state_rank": seen[st], "position_rank": p,
                         "first_name": "JOHN", "last_name": "SMITH" + "".join(chr(65 + int(d)) for d in str(nat)), "stars": 3,
                         "position": LABEL.get(chip, chip), "archetype": "Field General", "class": "HS",
                         "expected_nil": 25, "height_in": 74, "weight_lb": 210, "hometown": "Springfield, %s" % st,
                         "chip": chip, "view": "ANY STATE"})
    return recs


def write_folder(tmp, recs, meta=True, counters_close=None) -> Folder:
    f = Folder.create("Sample League", str(Path(tmp) / "cap"))
    with (f.path / "reads.jsonl").open("w", encoding="utf-8") as rf, \
            (f.path / "index.jsonl").open("w", encoding="utf-8") as xf:
        for i, r in enumerate(recs, 1):
            r = dict(r, card="c%05d" % i, mode="auto")
            rf.write(json.dumps(r) + "\n")
            xf.write(json.dumps({"card": r["card"], "chip": r["chip"], "view": r["view"], "mode": "auto",
                                 "t": "2026-11-02T20:00:00"}) + "\n")
    if meta:
        m = f.meta()
        m.update({"team": "Sample U", "platform": "PS5", "season": 2028, "class_year": 2029, "stage": "Preseason"})
        c = {"remaining": "1,000", "targets": "0/35", "hours": "500/500", "scholarships": "0/35"}
        m["counters_open"], m["counters_close"] = dict(c), dict(counters_close or c)
        f.save_meta(m)
    return f


def status(rep, name):
    return next((x["status"] for x in rep["results"] if x["check"] == name), None)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_complete_class_passes(self):
        recs = synthetic_class()
        rep = run_checks(write_folder(self.tmp.name, recs), class_size=len(recs))
        self.assertTrue(rep["ok"], rep["results"])

    def test_a_missing_recruit_fails_three_ways(self):
        recs = [r for r in synthetic_class() if r["national_rank"] != 7]
        rep = run_checks(write_folder(self.tmp.name, recs), class_size=34)
        self.assertEqual(status(rep, "national ranks"), "FAIL")
        self.assertEqual(status(rep, "state ranks"), "FAIL")
        self.assertEqual(status(rep, "position lists"), "FAIL")

    def test_double_reads_must_agree(self):
        recs = synthetic_class()
        recs.append(dict(recs[4], chip="ANY", state_rank=recs[4]["state_rank"] + 1))
        rep = run_checks(write_folder(self.tmp.name, recs), class_size=34)
        self.assertEqual(status(rep, "double reads agree"), "FAIL")

    def test_ocr_slips_are_fixed(self):
        recs = synthetic_class()
        recs[0]["hometown"] = "Englewood, Co"
        recs[1]["hometown"] = "lowa City, IA"
        recs[2]["position"] = "qb(r)"
        recs[2]["chip"] = "QB"
        f = write_folder(self.tmp.name, recs)
        rep = run_checks(f, class_size=34)
        by = rep["by"]
        self.assertEqual(by[1][0]["hometown"], "Englewood, CO")
        self.assertEqual(by[2][0]["hometown"], "Iowa City, IA")
        self.assertEqual(by[3][0]["position"], "QB (R)")

    def test_counters_that_moved_fail(self):
        recs = synthetic_class()
        moved = {"remaining": "1,000", "targets": "1/35", "hours": "500/500", "scholarships": "0/35"}
        rep = run_checks(write_folder(self.tmp.name, recs, counters_close=moved), class_size=34)
        self.assertEqual(status(rep, "meta"), "FAIL")

    def test_a_list_cut_at_600_fails(self):
        recs = synthetic_class(per_list=1, wr=600)
        rep = run_checks(write_folder(self.tmp.name, recs), class_size=len(recs))
        self.assertEqual(status(rep, "position lists"), "FAIL")

    def test_a_list_past_600_passes(self):
        recs = synthetic_class(per_list=1, wr=640)
        rep = run_checks(write_folder(self.tmp.name, recs), class_size=len(recs))
        self.assertEqual(status(rep, "position lists"), "PASS")

    def test_hand_fix_and_drop(self):
        recs = synthetic_class()
        recs[5]["hometown"] = "Spr1ngfield TX"
        f = write_folder(self.tmp.name, recs)
        self.assertEqual(status(run_checks(f, class_size=34), "fields"), "FAIL")
        f.save_fixes({"c00006": {"hometown": "Springfield, %s" % recs[5]["hometown"][-2:]}})
        self.assertTrue(run_checks(f, class_size=34)["ok"])
        recs2 = synthetic_class()
        recs2.append(dict(recs2[0], chip="ANY", last_name="GARBLE"))
        f2 = write_folder(self.tmp.name + "/b", recs2)
        self.assertEqual(status(run_checks(f2, class_size=34), "double reads agree"), "FAIL")
        f2.save_fixes({"c00035": {"drop": True}})
        self.assertTrue(run_checks(f2, class_size=34)["ok"])


class BuildTests(unittest.TestCase):
    def test_build_writes_the_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            recs = synthetic_class()
            f = write_folder(tmp, recs)
            out = build(f, class_size=34)
            cap = json.loads((out / "capture.json").read_text(encoding="utf-8"))
            self.assertEqual(cap["league"], "Sample League")
            self.assertEqual(cap["format"], "cfb27-prospect-census/1")
            self.assertEqual(cap["counts"]["recruits"], 34)
            with (out / "recruits.jsonl").open(encoding="utf-8") as fh:
                rows = [json.loads(x) for x in fh]
            self.assertEqual([r["national_rank"] for r in rows], list(range(1, 35)))
            self.assertEqual(set(rows[0]) - {"fixes"}, {
                "national_rank", "state_rank", "position_rank", "first_name", "last_name", "stars", "position",
                "archetype", "class", "expected_nil", "height_in", "weight_lb", "hometown", "position_list", "card",
                "reads"})
            with zipfile.ZipFile(out.with_suffix(".zip")) as z:
                self.assertEqual(sorted(n.split("/")[-1] for n in z.namelist()), ["capture.json", "recruits.jsonl"])

    def test_build_refuses_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            recs = [r for r in synthetic_class() if r["national_rank"] != 3]
            f = write_folder(tmp, recs)
            with self.assertRaises(SystemExit):
                build(f, class_size=34)
            out = build(f, class_size=34, allow_failures=True)
            cap = json.loads((out / "capture.json").read_text(encoding="utf-8"))
            self.assertTrue(cap["known_gaps"])


if __name__ == "__main__":
    unittest.main()
