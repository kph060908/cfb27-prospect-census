"""From card reads to the output: one record per recruit, the checks, capture.json and recruits.jsonl.

Every card is read once per crop. A recruit seen on several lists (the top 600, his position list, the ATH list)
has several reads; they must agree. The record kept is a position-list read without errors.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from . import FORMAT, TOOL, __version__
from .capture import LIST_CAP, POSITION_CHIPS
from .folder import Folder, slug

CLASS_SIZE = 4100
STATE_CODES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
                  "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
POSITION_LIST = {"QB": "QB", "QB (R)": "QB", "QB (L)": "QB", "HB": "HB", "FB": "FB", "WR": "WR", "TE": "TE",
                 "LT": "OT", "RT": "OT", "LG": "OG", "RG": "OG", "C": "C", "LEDG": "EDGE", "REDG": "EDGE", "DT": "DT",
                 "SAM": "OLB", "WILL": "OLB", "MIKE": "MIKE", "CB": "CB", "FS": "FS", "SS": "SS", "K": "K", "P": "P",
                 "ATH": None}
CLASS_LABELS = {"HS", "JC (FR)", "JC (SO)", "JC (JR)", "JC (SR)"}
FIELDS = ["national_rank", "state_rank", "position_rank", "first_name", "last_name", "stars", "position",
          "archetype", "class", "expected_nil", "height_in", "weight_lb", "hometown"]
INT_FIELDS = {"national_rank", "state_rank", "position_rank", "stars", "expected_nil", "height_in", "weight_lb"}
META_REQUIRED = ["league", "team", "platform", "season", "class_year", "stage"]
COUNTERS = ["remaining", "targets", "hours", "scholarships"]


# ---------------------------------------------------------------------------------------------- reads
def auto_fix(r: dict) -> list[str]:
    """OCR slips with one right answer. Case and spacing of labels are tidied silently; changed text is listed."""
    out = []
    pos = r.get("position")
    if pos:
        r["position"] = re.sub(r"^QB\(([RL])\)$", r"QB (\1)", re.sub(r"\s+", "", pos.upper()))
    cls = r.get("class")
    if cls:
        r["class"] = re.sub(r"^JC\s*\(\s*(\w+)\s*\)$", lambda m: "JC (%s)" % m.group(1).upper(), cls.strip().upper())
    town = r.get("hometown")
    if town:
        t = re.sub(r",\s*([A-Za-z]{2})\s*$", lambda m: ", " + m.group(1).upper(), town.strip())
        t = re.sub(r"^l(?=[a-z])", "I", t)                     # no town starts lower case: 'lowa' is 'Iowa'
        if t != town:
            out.append("hometown %r -> %r" % (town, t))
            r["hometown"] = t
    return out


def load_reads(folder: Folder) -> list[dict]:
    if not (folder.path / "reads.jsonl").exists():
        raise SystemExit("no reads.jsonl: run `census ocr` first")
    reads = folder.jsonl("reads.jsonl")
    fixes = folder.fixes()
    out = []
    for r in reads:
        r["fixes"] = auto_fix(r)
        hand = fixes.get(r["card"])
        if hand:
            if hand.get("drop"):
                continue
            for k, v in hand.items():
                if k in FIELDS:
                    v = int(v) if (k in INT_FIELDS and v is not None and v != "") else v
                    r["fixes"].append("hand: %s %r -> %r" % (k, r.get(k), v))
                    r[k] = v
            if r.get("error") and all(r.get(f) is not None for f in ("national_rank", "last_name", "hometown")):
                r.pop("error")
        out.append(r)
    return out


def _pref(r: dict) -> tuple:
    chip = r.get("chip") or "?"
    return (bool(r.get("error")), chip not in POSITION_CHIPS, chip == "ATH", r["card"])


def choose(reads: list[dict]) -> dict[int, list[dict]]:
    """National rank -> its reads, the preferred read first."""
    by = defaultdict(list)
    for r in reads:
        if isinstance(r.get("national_rank"), int):
            by[r["national_rank"]].append(r)
    for v in by.values():
        v.sort(key=_pref)
    return by


def _runs(nums: list[int]) -> str:
    runs = []
    for n in sorted(nums):
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    s = ", ".join(str(a) if a == b else "%d-%d" % (a, b) for a, b in runs[:25])
    return s + (" ..." if len(runs) > 25 else "")


# ---------------------------------------------------------------------------------------------- checks
def run_checks(folder: Folder, class_size: int = CLASS_SIZE) -> dict:
    reads = load_reads(folder)
    by = choose(reads)
    chosen = {nat: rs[0] for nat, rs in by.items()}
    res = []

    def add(status, name, detail):
        res.append({"status": status, "check": name, "detail": detail})

    errs = [r["card"] for r in reads if r.get("error")]
    add("PASS" if not errs else "WARN", "card reads",
        "%d reads, %d unreadable%s" % (len(reads), len(errs), (": " + ", ".join(errs[:12])) if errs else ""))

    missing = [n for n in range(1, class_size + 1) if n not in by]
    extra = sorted(n for n in by if not 1 <= n <= class_size)
    add("PASS" if not missing and not extra else "FAIL", "national ranks",
        "%d of %d present%s%s" % (class_size - len(missing), class_size,
                                  ("; missing " + _runs(missing)) if missing else "",
                                  ("; outside 1-%d (misreads, or a bigger class: check --class-size): %s"
                                   % (class_size, _runs(extra))) if extra else ""))

    bad = []
    for nat, rs in sorted(by.items()):
        keys = {((r.get("last_name") or "").casefold(), r.get("state_rank"), r.get("position_rank"))
                for r in rs if not r.get("error")}
        if len(keys) > 1:
            bad.append("NAT %d: %s" % (nat, "; ".join("%s %s STA %s POS %s" % (r["card"], r.get("last_name"),
                                                                              r.get("state_rank"), r.get("position_rank"))
                                                      for r in rs if not r.get("error"))))
    add("PASS" if not bad else "FAIL", "double reads agree",
        "every recruit read more than once reads the same" if not bad else "%d disagree: %s" % (len(bad), " | ".join(bad[:8])))

    states = defaultdict(list)
    for r in chosen.values():
        m = re.search(r",\s*([A-Z]{2})$", r.get("hometown") or "")
        if m:
            states[m.group(1)].append(r.get("state_rank"))
    st_bad = []
    for s, ranks in sorted(states.items()):
        ok = [x for x in ranks if isinstance(x, int)]
        if sorted(ok) != list(range(1, len(ranks) + 1)):
            have = set(ok)
            st_bad.append("%s (%d recruits; missing %s)" % (s, len(ranks),
                                                           _runs([k for k in range(1, len(ranks) + 1) if k not in have])))
    add("PASS" if not st_bad else "FAIL", "state ranks",
        "%d states, every state's ranks run 1..n" % len(states) if not st_bad else "; ".join(st_bad[:10]))

    lists, wrong_list = {}, []
    for chip in POSITION_CHIPS:
        pos = {}
        for r in reads:
            if r.get("error") or r.get("chip") != chip or not isinstance(r.get("position_rank"), int):
                continue
            grp = POSITION_LIST.get((r.get("position") or "").upper(), "?")
            if grp not in (chip, None):
                wrong_list.append("%s (%s on the %s list)" % (r["card"], r.get("position"), chip))
                continue
            pos.setdefault(r["position_rank"], r.get("national_rank"))
        lists[chip] = pos
    l_bad = []
    for chip, pos in lists.items():
        if not pos:
            l_bad.append("%s never read" % chip)
            continue
        gaps = [k for k in range(1, max(pos) + 1) if k not in pos]
        if gaps:
            l_bad.append("%s missing position ranks %s" % (chip, _runs(gaps)))
        elif max(pos) == LIST_CAP:
            l_bad.append("%s stops at exactly %d: the list was cut at the cap, read its tail" % (chip, LIST_CAP))
    longer = ", ".join("%s %d" % (c, max(p)) for c, p in lists.items() if p and max(p) > LIST_CAP)
    add("PASS" if not l_bad else "FAIL", "position lists",
        ("all 17 lists run 1..n" + ("; past the 600 cap: " + longer if longer else "")) if not l_bad
        else "; ".join(l_bad[:12]))
    if wrong_list:
        add("WARN", "list labels", "%d reads sit on another position's list (left out of the list check): %s"
            % (len(wrong_list), ", ".join(wrong_list[:10])))

    f_bad, f_warn = [], []
    for nat, r in sorted(chosen.items()):
        probs = []
        for f in FIELDS:
            if f != "expected_nil" and r.get(f) in (None, ""):
                probs.append("no " + f)
        town = r.get("hometown") or ""
        m = re.match(r"^[A-Z][^,]*, ([A-Z]{2})$", town)
        if town and (not m or m.group(1) not in STATE_CODES):
            probs.append("hometown %r" % town)
        if r.get("position") and r["position"].upper() not in POSITION_LIST:
            probs.append("position %r" % r["position"])
        if r.get("class") and r["class"] not in CLASS_LABELS:
            probs.append("class %r" % r["class"])
        if isinstance(r.get("stars"), int) and not 1 <= r["stars"] <= 5:
            probs.append("stars %r" % r["stars"])
        if isinstance(r.get("height_in"), int) and not 60 <= r["height_in"] <= 90:
            probs.append("height %r" % r["height_in"])
        if isinstance(r.get("weight_lb"), int) and not 120 <= r["weight_lb"] <= 420:
            probs.append("weight %r" % r["weight_lb"])
        if r.get("error"):
            probs.append("unreadable card")
        if probs:
            f_bad.append("NAT %d (%s): %s" % (nat, r["card"], ", ".join(probs)))
        if r.get("expected_nil") is None:
            f_warn.append("NAT %d (%s)" % (nat, r["card"]))
        for name in ("first_name", "last_name"):
            v = r.get(name) or ""
            if v and not re.match(r"^[A-Z][A-Z'’.\- ]*$", v.upper()):
                f_warn.append("NAT %d %s %r" % (nat, name, v))
    add("PASS" if not f_bad else "FAIL", "fields",
        "every record complete and well formed" if not f_bad else "%d records: %s" % (len(f_bad), " | ".join(f_bad[:10])))
    if f_warn:
        add("WARN", "fields to eyeball", "%d: %s" % (len(f_warn), ", ".join(f_warn[:10])))

    meta = folder.meta()
    m_bad = [k for k in META_REQUIRED if meta.get(k) in (None, "")]
    for which in ("counters_open", "counters_close"):
        c = meta.get(which) or {}
        m_bad += ["%s.%s" % (which, k) for k in COUNTERS if c.get(k) in (None, "")]
    if not m_bad:
        if [str(meta["counters_open"][k]) for k in COUNTERS] != [str(meta["counters_close"][k]) for k in COUNTERS]:
            m_bad.append("the counters changed between open and close: was a recruiting action taken?")
        if isinstance(meta.get("season"), int) and isinstance(meta.get("class_year"), int) \
                and meta["class_year"] != meta["season"] + 1:
            add("WARN", "class year", "class_year %s is not season + 1 (%s)" % (meta["class_year"], meta["season"]))
    add("PASS" if not m_bad else "FAIL", "meta",
        "league %r, %s" % (meta.get("league"), "complete" if not m_bad else "missing or wrong: " + ", ".join(m_bad)))

    return {"results": res, "ok": all(x["status"] != "FAIL" for x in res), "reads": reads, "by": by,
            "lists": lists, "meta": meta}


def print_report(rep: dict) -> None:
    for x in rep["results"]:
        print("%-4s  %-20s %s" % (x["status"], x["check"], x["detail"]))
    print("ALL CHECKS PASS" if rep["ok"] else "NOT READY: fix every FAIL line (LLM_INSTRUCTIONS.md, section 9)")


# ---------------------------------------------------------------------------------------------- build
def record(nat: int, rs: list[dict]) -> dict:
    r = rs[0]
    rec = {f: r.get(f) for f in FIELDS}
    rec["national_rank"] = nat
    lists = sorted({x.get("chip") for x in rs if x.get("chip") in POSITION_CHIPS and x.get("chip") != "ATH"})
    rec["position_list"] = lists[0] if len(lists) == 1 else (lists or [None])[0]
    rec["card"] = r["card"]
    rec["reads"] = len(rs)
    if r.get("fixes"):
        rec["fixes"] = r["fixes"]
    return rec


def build(folder: Folder, allow_failures: bool = False, make_zip: bool = True, with_cards: bool = False,
          class_size: int = CLASS_SIZE) -> Path:
    rep = run_checks(folder, class_size)
    print_report(rep)
    if not rep["ok"] and not allow_failures:
        raise SystemExit("build refused: the checks above have FAIL lines (or pass --allow-failures to send a "
                         "partial capture with its gaps listed)")
    meta, by, reads = rep["meta"], rep["by"], rep["reads"]
    index = folder.jsonl("index.jsonl")
    modes = sorted({i.get("mode") for i in index if i.get("mode")})
    captured_on = index[0]["t"][:10] if index else dt.date.today().isoformat()
    recs = [record(nat, rs) for nat, rs in sorted(by.items()) if 1 <= nat <= class_size]
    lists = [{"list": c, "recruits": len(p), "max_position_rank": max(p) if p else 0}
             for c, p in rep["lists"].items()]
    cap = {
        "format": FORMAT,
        "league": meta.get("league"),
        "league_as_shown": meta.get("league_as_shown"),
        "team": meta.get("team"),
        "platform": meta.get("platform"),
        "capture_mode": "+".join(modes) or None,
        "season": meta.get("season"),
        "class_year": meta.get("class_year"),
        "stage": meta.get("stage"),
        "captured_on": captured_on,
        "counters_open": meta.get("counters_open"),
        "counters_close": meta.get("counters_close"),
        "class_size": class_size,
        "counts": {"recruits": len(recs), "card_reads": len(reads),
                   "reads_with_errors": sum(1 for r in reads if r.get("error")),
                   "records_with_fixes": sum(1 for r in recs if r.get("fixes"))},
        "lists": lists,
        "checks": {x["check"]: x["status"] for x in rep["results"]},
        "known_gaps": [x["check"] + ": " + x["detail"] for x in rep["results"] if x["status"] == "FAIL"],
        "notes": meta.get("notes") or "",
        "tool": {"name": TOOL, "version": __version__},
    }
    name = "%s-class%s-%s" % (slug(meta.get("league")), meta.get("class_year") or "x", captured_on)
    out = folder.path / "out" / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "capture.json").write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    with (out / "recruits.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    folder.log("build: %s (%d recruits, checks %s)" % (out, len(recs), "PASS" if rep["ok"] else "with gaps"))
    if make_zip:
        zp = out.with_suffix(".zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(out / "capture.json", name + "/capture.json")
            z.write(out / "recruits.jsonl", name + "/recruits.jsonl")
            if with_cards:
                for r in recs:
                    p = folder.path / "cards" / (r["card"] + ".jpg")
                    if p.exists():
                        z.write(p, name + "/cards/" + p.name, compress_type=zipfile.ZIP_STORED)
        print("zip:", zp)
    print("output:", out)
    return out
