"""The weekly giveaway draw: one random entry from the open GitHub issues labelled `entry`.

    python -m giveaway.draw list                      # the entries a draw would use today
    python -m giveaway.draw draw                      # dry run: picks a winner, changes nothing
    python -m giveaway.draw draw --go                 # comments on the winner, labels it `winner`, logs DRAWS.md
    python -m giveaway.draw fetch <issue> [--out DIR] # downloads the zip attached to an entry

Needs the GitHub CLI (`gh`), signed in; only the repository's owner can run `--go`. Commit DRAWS.md after a draw.

Who is in a draw: open issues labelled `entry` and not labelled `winner` or `invalid`. One entry per league and class
year: when two people enter the same league's class, the earliest entry counts and the later one sits out. The pick
uses Python's `secrets` module (the operating system's random source), so nobody, the owner included, chooses it.
"""
import argparse
import json
import re
import secrets
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

REPO = "kph060908/cfb27-prospect-census"
ROOT = Path(__file__).resolve().parent.parent
DRAWS = ROOT / "DRAWS.md"
SKIP = {"winner", "invalid"}
ZIP_URL = re.compile(r"https://github\.com/user-attachments/files/\d+/[^\s)\]]+?\.zip", re.I)


def field(body, label):
    """The answer under one heading of an issue-form body ("### League name" then the text)."""
    m = re.search(rf"^###\s+{re.escape(label)}\s*\n+(.*?)(?=\n###\s|\Z)", body or "", re.M | re.S)
    if not m:
        return ""
    text = m.group(1).strip()
    return "" if text == "_No response_" else text


def entry(issue):
    body = issue.get("body") or ""
    return {"number": issue["number"], "created": issue.get("createdAt", ""),
            "league": field(body, "League name"), "team": field(body, "Team"),
            "class_year": field(body, "Class year"), "labels": {l["name"] for l in issue.get("labels", [])},
            "zips": ZIP_URL.findall(body)}


def eligible(entries):
    """Entries in today's draw: not already won or turned down, holding a zip, one per league + class year."""
    seen, out = set(), []
    for e in sorted(entries, key=lambda e: (e["created"], e["number"])):
        if e["labels"] & SKIP or not e["zips"]:
            continue
        key = (e["league"].strip().casefold(), e["class_year"].strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit(f"gh {' '.join(args[:3])} failed:\n{r.stderr.strip()}")
    return r.stdout


def open_entries():
    out = gh("issue", "list", "--repo", REPO, "--label", "entry", "--state", "open", "--limit", "500",
             "--json", "number,createdAt,body,labels")
    return [entry(i) for i in json.loads(out)]


def label(e):
    return f"#{e['number']} ({e['league']} · {e['team']} · {e['class_year']})"


def log_draw(day, pool, winner):
    text = DRAWS.read_text(encoding="utf-8") if DRAWS.exists() else "# Giveaway draws\n"
    text = text.replace("_No draws yet._\n", "")
    row = f"| {day} | {', '.join('#%d' % e['number'] for e in pool)} | {label(winner)} |\n"
    DRAWS.write_bytes((text.rstrip("\n") + "\n" + row).encode("utf-8"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "draw", "fetch"])
    ap.add_argument("issue", nargs="?", type=int)
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    if a.cmd == "fetch":
        if not a.issue:
            sys.exit("fetch needs an issue number")
        e = entry(json.loads(gh("issue", "view", str(a.issue), "--repo", REPO, "--json", "number,body,labels")))
        if not e["zips"]:
            sys.exit(f"#{a.issue} has no zip attached")
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        for url in e["zips"]:
            dest = out / url.rsplit("/", 1)[-1]
            urllib.request.urlretrieve(url, dest)
            print(f"{dest}  {dest.stat().st_size:,} bytes")
        return
    pool = eligible(open_entries())
    print(f"{len(pool)} entries in the draw: " + (", ".join(label(e) for e in pool) or "none"))
    if a.cmd == "list" or not pool:
        return
    winner = secrets.choice(pool)
    day = date.today().isoformat()
    print(f"winner: {label(winner)}" + ("" if a.go else "  (dry run: nothing changed)"))
    if not a.go:
        return
    gh("issue", "comment", str(winner["number"]), "--repo", REPO, "--body",
       f"Drawn in the giveaway of {day}, out of {len(pool)} entries (logged in DRAWS.md). Your class is next: the "
       f"file will be linked here when it's ready, and the link comes down once you say you have it.")
    gh("issue", "edit", str(winner["number"]), "--repo", REPO, "--add-label", "winner")
    log_draw(day, pool, winner)
    print("DRAWS.md updated: commit and push it")


if __name__ == "__main__":
    main()
