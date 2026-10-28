"""census: capture every recruit card on the College Football 27 Prospect List.

Every command works on one capture folder: --folder PATH, else the CENSUS_FOLDER environment variable, else the
current directory. Run `python -m census <command> -h` for a command's options. LLM_INSTRUCTIONS.md is the order.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time

from . import FORMAT, __version__


def _folder(a):
    from .folder import Folder
    return Folder.open(a.folder)


def _capture(f, need_keys: bool = False):
    from .capture import Capture
    from .geometry import boxes_with
    from .keys import make_keys
    from .screen import make_source
    s = f.setup()
    if not s.get("source"):
        raise SystemExit("no frame source yet: run `census setup --source window:<title>` (or region:x,y,w,h)")
    keys = make_keys(s.get("keys") or "none")
    if need_keys and keys.name == "none":
        raise SystemExit("this capture has no key backend (watch mode): the player presses the buttons")
    return Capture(f, make_source(s["source"]), keys, boxes_with(s.get("boxes")))


def _save_frame(f, img, label: str) -> str:
    from PIL import ImageDraw
    d = f.path / "frames"
    d.mkdir(exist_ok=True)
    img.save(d / (label + ".png"))
    view = img.resize((1280, 720))
    view.save(d / (label + ".jpg"), quality=85)
    return str(d / (label + ".jpg"))


def _boxes_image(f, img, label: str, boxes: dict) -> str:
    from PIL import ImageDraw
    im = img.copy()
    dr = ImageDraw.Draw(im)
    colors = {"card": (0, 255, 0), "header": (255, 200, 0), "tab": (255, 0, 255), "chip": (0, 200, 255),
              "view": (255, 80, 80)}
    for k, b in boxes.items():
        dr.rectangle(b, outline=colors.get(k, (255, 255, 255)), width=5)
        dr.text((b[0] + 6, b[3] + 4), k, fill=colors.get(k, (255, 255, 255)))
    p = f.path / "frames" / (label + "_boxes.jpg")
    im.resize((1280, 720)).save(p, quality=85)
    return str(p)


# ---------------------------------------------------------------------------------------------- commands
def cmd_init(a):
    from .folder import Folder
    f = Folder.create(a.league, a.folder)
    print("capture folder:", f.path)
    print("league:", f.meta()["league"])


def cmd_setup(a):
    f = _folder(a)
    s = f.setup()
    if a.source:
        s["source"] = a.source
    if a.keys:
        s["keys"] = a.keys
    if a.clear_boxes:
        s.pop("boxes", None)
    for spec in a.box or []:
        name, _, vals = spec.partition("=")
        nums = [int(v) for v in vals.split(",")]
        if len(nums) != 4:
            raise SystemExit("--box needs name=x0,y0,x1,y1 in 2560x1440 reference pixels")
        s.setdefault("boxes", {})[name] = nums
    f.save_setup(s)
    f.log("setup: %s" % json.dumps(s))
    print(json.dumps(s, indent=1))


def cmd_doctor(a):
    print("python", sys.version.split()[0], "|", platform.platform())
    ok = True
    for mod in ("PIL", "numpy", "mss", "rapidocr", "onnxruntime"):
        try:
            m = __import__(mod)
            print("  %-12s %s" % (mod, getattr(m, "__version__", "ok")))
        except Exception as e:  # noqa: BLE001
            ok = False
            print("  %-12s MISSING (%s): pip install -r requirements.txt" % (mod, e))
    if ok:
        t0 = time.time()
        from .ocr import engine
        engine()
        print("  OCR engine ready (%.1f s; the first run downloads the models)" % (time.time() - t0))
    from .screen import IS_WIN, list_windows
    if IS_WIN:
        print("  %d visible windows (census windows lists them)" % len(list_windows()))
    else:
        print("  not Windows: use --source region:x,y,w,h and watch mode (--keys none)")
    print("doctor:", "OK" if ok else "install the missing packages")


def cmd_windows(a):
    from .screen import IS_WIN, list_windows
    if not IS_WIN:
        raise SystemExit("window listing is Windows only; use census screenshot and a region")
    for w in sorted(list_windows(), key=lambda w: -w["client"][2] * w["client"][3]):
        x, y, cw, ch = w["client"]
        if a.all or (cw >= 640 and ch >= 360):
            ratio = cw / ch if ch else 0
            print("%-48s %-28s client %5dx%-5d at %d,%d%s" % (w["title"][:48], w["class"][:28], cw, ch, x, y,
                                                             "  16:9" if abs(ratio / (16 / 9) - 1) < 0.02 else ""))


def cmd_screenshot(a):
    from .screen import full_screen_grab
    f = _folder(a)
    img = full_screen_grab()
    d = f.path / "frames"
    d.mkdir(exist_ok=True)
    img.save(d / "screen.png")
    small = img.copy()
    small.thumbnail((1600, 1600))
    small.save(d / "screen.jpg", quality=85)
    print("full screen %dx%d -> %s (scaled copy %s)" % (img.width, img.height, d / "screen.png", d / "screen.jpg"))


def cmd_fit_window(a):
    from .screen import fit_window
    w, h = (int(x) for x in a.size.lower().split("x"))
    print("client area now %dx%d" % fit_window(a.title, w, h))


def cmd_grab(a):
    f = _folder(a)
    cap = _capture(f)
    img = cap.grab()
    from .capture import tab_is_lit
    jpg = _save_frame(f, img, a.label)
    boxes = _boxes_image(f, img, a.label, cap.boxes)
    chip, view = cap.labels(img)
    print("picture %s from %s" % ("x".join(map(str, cap.source.raw_size)), cap.source.describe()))
    print("frame: %s   boxes: %s" % (jpg, boxes))
    print("Prospect List open: %s   L2 box: %s   R2 pill: %s" % (tab_is_lit(img, cap.boxes["tab"]), chip, view))


def cmd_try(a):
    f = _folder(a)
    cap = _capture(f)
    img = cap.grab()
    from .ocr import parse_card
    card = cap.crop(img, "card")
    d = f.path / "frames"
    d.mkdir(exist_ok=True)
    card.save(d / "try_card.jpg", quality=92)
    r = parse_card(card)
    r.pop("raw", None)
    print(json.dumps(r, indent=1, ensure_ascii=False))
    print("card crop:", d / "try_card.jpg")
    missing = [k for k in ("national_rank", "state_rank", "position_rank", "first_name", "last_name", "stars",
                           "position", "archetype", "class", "height_in", "weight_lb", "hometown") if r.get(k) is None]
    print("try: OK, every field read" if not missing and not r.get("error") else "try: NOT READ: %s" % ", ".join(missing))


def cmd_start(a):
    f = _folder(a)
    r = _capture(f).start()
    print(json.dumps(r))
    if not r["ok"]:
        raise SystemExit("start: not on the Prospect List (or a label is unreadable): check the frame (census grab)")


def cmd_press(a):
    f = _folder(a)
    cap = _capture(f, need_keys=True)
    if a.until_chip or a.until_view:
        kind, target = ("chip", a.until_chip) if a.until_chip else ("view", a.until_view)
        r = cap.press_until(a.button, kind, target, max_presses=a.max, wait=a.wait)
        print(json.dumps(r))
        if not r["reached"]:
            raise SystemExit("press: %s never read %r" % (kind, target))
        return
    for i in range(a.times):
        cap.keys.press(a.button)
        time.sleep(a.wait)
    f.log("press %s x%d" % (a.button, a.times))
    img = cap.grab()
    jpg = _save_frame(f, img, a.label)
    chip, view = cap.labels(img)
    print("pressed %s x%d; frame %s; L2 box %s; R2 pill %s" % (a.button, a.times, jpg, chip, view))


def cmd_walk(a):
    r = _capture(_folder(a), need_keys=True).walk(max_rows=a.max_rows, settle=a.settle)
    print(json.dumps(r))


def cmd_chips(a):
    for r in _capture(_folder(a), need_keys=True).chips(max_chips=a.max_chips, settle=a.settle):
        print(json.dumps(r))


def cmd_watch(a):
    r = _capture(_folder(a)).watch(idle=a.idle, fps=a.fps, still_frames=a.still, beep=a.beep, on_top=a.on_top)
    print(json.dumps(r))


def cmd_stop(a):
    f = _folder(a)
    (f.path / "STOP").write_text("stop", encoding="utf-8")
    print("asked the running watch to stop")


def cmd_meta(a):
    f = _folder(a)
    m = f.meta()
    for kv in a.pairs:
        key, _, val = kv.partition("=")
        if not _:
            raise SystemExit("meta takes KEY=VALUE pairs, e.g. season=2028 counters_open.hours=700/700")
        v = val.strip()
        if key in ("season", "class_year"):
            v = int(v)
        node = m
        parts = key.split(".")
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = v
        f.log("meta %s = %r" % (key, v))
    if a.pairs:
        f.save_meta(m)
    print(json.dumps(f.meta(), indent=1, ensure_ascii=False))


def cmd_ocr(a):
    from .ocr import ocr_folder
    f = _folder(a)
    t0 = time.time()
    n, errs = ocr_folder(f.path, workers=a.workers)
    f.log("ocr: %d new reads, %d unreadable, %.0f s" % (n, errs, time.time() - t0))
    print("ocr: %d new reads (%d unreadable) in %.0f s" % (n, errs, time.time() - t0))


def cmd_check(a):
    from .data import print_report, run_checks
    rep = run_checks(_folder(a), class_size=a.class_size)
    print_report(rep)
    if not rep["ok"]:
        raise SystemExit(1)


def cmd_fix(a):
    f = _folder(a)
    fx = f.fixes()
    entry = fx.get(a.card, {})
    if a.drop:
        entry = {"drop": True}
    for kv in a.pairs:
        key, _, val = kv.partition("=")
        entry[key] = val if val != "" else None
    fx[a.card] = entry
    f.save_fixes(fx)
    f.log("fix %s: %s" % (a.card, json.dumps(entry, ensure_ascii=False)))
    print(json.dumps({a.card: entry}, ensure_ascii=False))


def cmd_build(a):
    from .data import build
    build(_folder(a), allow_failures=a.allow_failures, make_zip=not a.no_zip, with_cards=a.with_cards,
          class_size=a.class_size)


def cmd_status(a):
    f = _folder(a)
    m = f.meta()
    idx = f.count_index()
    reads = len(f.jsonl("reads.jsonl"))
    print("league %r | crops %d | reads %d | lists walked: %s" % (
        m.get("league"), idx, reads, ", ".join("%s %d" % (x["chip"], x["rows"]) for x in f.lists()) or "-"))


# ---------------------------------------------------------------------------------------------- parser
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="census", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version="%(prog)s " + __version__ + " (" + FORMAT + ")")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--folder", default=None, help="the capture folder (default: $CENSUS_FOLDER, else here)")
        p.set_defaults(fn=fn)
        return p

    p = cmd("init", cmd_init, "start a capture folder; the league name is required")
    p.add_argument("--league", required=True, help="the league's name, exactly as the prompt gave it")
    cmd("doctor", cmd_doctor, "check Python, the packages and the OCR engine")
    p = cmd("windows", cmd_windows, "list visible windows (Windows)")
    p.add_argument("--all", action="store_true")
    cmd("screenshot", cmd_screenshot, "grab every screen, to find the game picture for a region source")
    p = cmd("setup", cmd_setup, "set the frame source, the key backend, box overrides")
    p.add_argument("--source", help="window:<title> (Windows; '=<title>' for an exact title) or region:x,y,w,h")
    p.add_argument("--keys", help="chiaki (chiaki-ng on Windows, default keyboard mapping) or none (watch mode)")
    p.add_argument("--box", action="append", help="name=x0,y0,x1,y1 in 2560x1440 reference pixels")
    p.add_argument("--clear-boxes", action="store_true")
    p = cmd("fit-window", cmd_fit_window, "resize a window's client area to 16:9 (Windows)")
    p.add_argument("title")
    p.add_argument("--size", default="1920x1080")
    p = cmd("grab", cmd_grab, "save the current frame and a copy with the boxes drawn")
    p.add_argument("label", nargs="?", default="grab")
    cmd("try", cmd_try, "read the card on screen now and print its fields")
    cmd("start", cmd_start, "confirm the Prospect List is open and keep its tab strip as the popup reference")
    p = cmd("press", cmd_press, "press one allowed button (chiaki backend), then grab")
    p.add_argument("button", choices=["up", "down", "left", "right", "l1", "r1", "l2", "r2", "square", "circle"])
    p.add_argument("--times", type=int, default=1)
    p.add_argument("--wait", type=float, default=2.0, help="seconds after each press")
    p.add_argument("--until-chip", help="press until the L2 box reads this (e.g. WR)")
    p.add_argument("--until-view", help="press until the R2 pill reads this (e.g. '1 STAR PROSPECTS')")
    p.add_argument("--max", type=int, default=80, help="most presses for --until-*")
    p.add_argument("--label", default="press")
    p = cmd("walk", cmd_walk, "auto: press Down to the end of the open list, saving every card")
    p.add_argument("--max-rows", type=int, default=620)
    p.add_argument("--settle", type=float, default=0.8)
    p = cmd("chips", cmd_chips, "auto: walk every position list from the open one (L2 between lists)")
    p.add_argument("--max-chips", type=int, default=25)
    p.add_argument("--settle", type=float, default=0.8)
    p = cmd("watch", cmd_watch, "watch mode: record every new card the player brings up")
    p.add_argument("--idle", type=float, default=180, help="stop after this many seconds without a new card")
    p.add_argument("--fps", type=float, default=12)
    p.add_argument("--still", type=int, default=3, help="frames a card must hold still to count")
    p.add_argument("--beep", action="store_true", help="beep on every new card")
    p.add_argument("--on-top", action="store_true", help="keep the game window above other windows")
    cmd("stop", cmd_stop, "stop a running watch")
    p = cmd("meta", cmd_meta, "show or set what the session records (KEY=VALUE ...)")
    p.add_argument("pairs", nargs="*")
    p = cmd("ocr", cmd_ocr, "read every new card crop")
    p.add_argument("--workers", type=int, default=2)
    p = cmd("check", cmd_check, "run every check on the reads")
    p.add_argument("--class-size", type=int, default=4100)
    p = cmd("fix", cmd_fix, "correct a read by hand (FIELD=VALUE ...) or --drop it")
    p.add_argument("card")
    p.add_argument("pairs", nargs="*")
    p.add_argument("--drop", action="store_true")
    p = cmd("build", cmd_build, "write the output (capture.json + recruits.jsonl) and its zip")
    p.add_argument("--allow-failures", action="store_true")
    p.add_argument("--no-zip", action="store_true")
    p.add_argument("--with-cards", action="store_true", help="put the card crops in the zip too")
    p.add_argument("--class-size", type=int, default=4100)
    cmd("status", cmd_status, "counts so far")

    a = ap.parse_args(argv)
    a.fn(a)
    return 0
