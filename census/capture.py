"""Capture card crops off the Prospect List.

Two ways, writing the same files (cards/<name>.jpg plus one index.jsonl line per crop):

  auto   the tool presses Down itself (chiaki-ng on Windows) and grabs after each press, to the end of the list.
  watch  the player presses the buttons; the tool records every new card that holds still on screen.

A list's end: Down no longer changes the card. A dropped press looks the same, so Down is pressed three more
times before a list counts as finished. Any change of the Recruiting tab strip (a popup, another screen) stops
the capture with the frame saved.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image, ImageChops

from .ocr import chip_name, read_label, view_name

CHIPS = ["QB", "HB", "FB", "WR", "TE", "OT", "OG", "C", "EDGE", "DT", "OLB", "MIKE", "CB", "FS", "SS", "K", "P", "ATH"]
POSITION_CHIPS = CHIPS[:-1]          # every recruit is on one of these 17 lists; ATH repeats recruits listed elsewhere
LIST_CAP = 600                       # every Prospect List view stops at 600 rows
SAME_CARD = 5.0                      # mean pixel difference under this = the same card (cards differ by 11+)
HEADER_CHANGED = 8.0                 # tab strip difference over this = a popup or another screen
STILL = 2.5                          # watch mode: two grabs this close = the card is holding still


def mean_diff(a: Image.Image, b: Image.Image) -> float:
    h = ImageChops.difference(a, b).convert("L").histogram()
    return sum(i * n for i, n in enumerate(h)) / max(1, sum(h))


def tab_is_lit(img: Image.Image, box) -> bool:
    """The Prospect List tab is a white pill when it is the open tab."""
    h = img.crop(box).convert("L").histogram()
    return sum(i * n for i, n in enumerate(h)) / max(1, sum(h)) > 150   # lit ~208, unlit 65-85


class Capture:
    def __init__(self, folder, source, keys, boxes: dict):
        self.folder = folder
        self.source = source
        self.keys = keys
        self.boxes = boxes
        (folder.path / "cards").mkdir(exist_ok=True)
        self.seq = folder.count_index()

    # ------------------------------------------------------------------ basics
    def grab(self) -> Image.Image:
        return self.source.grab()

    def crop(self, img: Image.Image, name: str) -> Image.Image:
        return img.crop(self.boxes[name])

    def labels(self, img: Image.Image) -> tuple[str, str]:
        return chip_name(read_label(self.crop(img, "chip"))), view_name(read_label(self.crop(img, "view")))

    def header_ref(self) -> Image.Image:
        p = self.folder.path / "header_ref.png"
        if not p.exists():
            raise SystemExit("no header_ref.png: open the Prospect List and run `census start` first")
        return Image.open(p).convert("RGB")

    def on_list(self, img: Image.Image, ref: Image.Image) -> bool:
        return mean_diff(self.crop(img, "header"), ref) <= HEADER_CHANGED

    def save_card(self, card: Image.Image, chip: str, view: str, mode: str) -> str:
        self.seq += 1
        name = "c%05d" % self.seq
        card.save(self.folder.path / "cards" / (name + ".jpg"), quality=92)
        self.folder.add_index({"card": name, "chip": chip, "view": view, "mode": mode,
                               "t": time.strftime("%Y-%m-%dT%H:%M:%S")})
        return name

    def stop_frame(self, img: Image.Image, why: str) -> str:
        p = self.folder.path / "frames" / ("stop_%s.png" % time.strftime("%H%M%S"))
        p.parent.mkdir(exist_ok=True)
        img.save(p)
        self.folder.log("STOP: %s (frame %s)" % (why, p.name))
        return str(p)

    # ------------------------------------------------------------------ start
    def start(self) -> dict:
        """Check the screen is the Prospect List and keep its tab strip as the reference for popups."""
        img = self.grab()
        lit = tab_is_lit(img, self.boxes["tab"])
        chip, view = self.labels(img)
        ok = lit and chip in (["ANY"] + CHIPS) and view != "?"
        if ok:
            self.crop(img, "header").save(self.folder.path / "header_ref.png")
            self.folder.log("start: on the Prospect List, chip %s, view %s" % (chip, view))
        return {"prospect_list_open": lit, "chip": chip, "view": view, "ok": ok}

    # ------------------------------------------------------------------ auto
    def walk(self, max_rows: int = LIST_CAP + 20, settle: float = 0.8, retries: int = 3) -> dict:
        """Press Down from the highlighted row to the end of the list, saving every card."""
        ref = self.header_ref()
        self.source.hold_on_top(True)
        try:
            img = self.grab()
            if not self.on_list(img, ref):
                return {"rows": 0, "why": "not on the Prospect List (or a popup is open)",
                        "frame": self.stop_frame(img, "walk refused: not on the list")}
            chip, view = self.labels(img)
            t0, rows, prev, why, frame = time.time(), 0, None, "max rows", None
            while rows < max_rows:
                if not self.on_list(img, ref):
                    why, frame = "screen changed", self.stop_frame(img, "screen changed in %s row %d" % (chip, rows))
                    break
                card = self.crop(img, "card")
                if prev is not None and mean_diff(card, prev) < SAME_CARD:
                    time.sleep(0.7)
                    img = self.grab()
                    card = self.crop(img, "card")
                    for _ in range(retries):         # a dropped press looks like the end: press again first
                        if mean_diff(card, prev) >= SAME_CARD:
                            break
                        self.keys.press("down")
                        time.sleep(settle + 0.4)
                        img = self.grab()
                        card = self.crop(img, "card")
                    if mean_diff(card, prev) < SAME_CARD:
                        why = "end of list"
                        break
                self.save_card(card, chip, view, "auto")
                rows += 1
                prev = card
                if rows >= max_rows:
                    break
                self.keys.press("down")
                time.sleep(settle)
                img = self.grab()
            self.folder.log("walk %s / %s: %d rows, %s, %.0f s" % (chip, view, rows, why, time.time() - t0))
            return {"chip": chip, "view": view, "rows": rows, "why": why, "frame": frame,
                    "seconds": round(time.time() - t0)}
        finally:
            self.source.hold_on_top(False)

    def press_until(self, button: str, kind: str, target: str, max_presses: int = 80, wait: float = 2.5) -> dict:
        """Press one button at a time until the chip box or the view pill reads `target`."""
        target = chip_name(target) if kind == "chip" else view_name(target)
        seen = []
        for i in range(max_presses + 1):
            img = self.grab()
            chip, view = self.labels(img)
            now = chip if kind == "chip" else view
            seen.append(now)
            if now == target:
                self.folder.log("press_until %s=%s after %d presses" % (kind, target, i))
                return {"reached": True, "presses": i, "labels": seen[-5:]}
            if i == max_presses:
                break
            self.keys.press(button)
            time.sleep(wait)
        return {"reached": False, "presses": max_presses, "labels": seen[-5:]}

    def chips(self, max_chips: int = 25, settle: float = 0.8) -> list[dict]:
        """Walk every position list from the open one, L2 after each, until the box reads ANY again."""
        done = {c["chip"] for c in self.folder.lists()}
        results = []
        for _ in range(max_chips):
            img = self.grab()
            chip, view = self.labels(img)
            if chip not in CHIPS:                    # one more look before giving up on a misread
                time.sleep(1.0)
                chip, view = self.labels(self.grab())
            if chip == "ANY":
                break
            if chip not in CHIPS:
                results.append({"chip": chip, "why": "position box unreadable: stopped"})
                break
            if view != "ANY STATE":
                results.append({"chip": chip, "view": view, "why": "the view is not ANY STATE: stopped"})
                break
            if chip in done:
                self.keys.press("l2")
                time.sleep(2.5)
                continue
            r = self.walk(settle=settle)
            results.append(r)
            if r["why"] not in ("end of list", "max rows"):
                break
            self.folder.add_list({"chip": chip, "rows": r["rows"], "capped": r["rows"] >= LIST_CAP,
                                  "seconds": r["seconds"]})
            done.add(chip)
            self.keys.press("l2")
            time.sleep(2.5)
        return results

    # ------------------------------------------------------------------ watch
    def watch(self, idle: float = 180.0, fps: float = 12.0, still_frames: int = 3, beep: bool = False,
              on_top: bool = False) -> dict:
        """Record every new card the player brings up, until `census stop` or `idle` seconds without a new card.
        The window is not raised by default: a raised window can sit over the chat the player is using."""
        ref = self.header_ref()
        stop = self.folder.path / "STOP"
        if stop.exists():
            stop.unlink()
        self.source.hold_on_top(on_top)
        saved, last_saved, cand, cand_n = 0, None, None, 0
        chip = view = "?"
        chip_img = view_img = None
        t_new = time.time()
        why = "idle"
        try:
            while True:
                if stop.exists():
                    why = "stopped"
                    stop.unlink()
                    break
                if time.time() - t_new > idle:
                    break
                t_frame = time.time()
                img = self.grab()
                if not self.on_list(img, ref):
                    cand, cand_n = None, 0
                    time.sleep(0.2)
                    continue
                c_img, v_img = self.crop(img, "chip"), self.crop(img, "view")
                if chip_img is None or mean_diff(c_img, chip_img) > HEADER_CHANGED:
                    chip, chip_img = chip_name(read_label(c_img)), c_img
                if view_img is None or mean_diff(v_img, view_img) > HEADER_CHANGED:
                    view, view_img = view_name(read_label(v_img)), v_img
                card = self.crop(img, "card")
                if last_saved is not None and mean_diff(card, last_saved) < SAME_CARD:
                    cand, cand_n = None, 0
                elif cand is not None and mean_diff(card, cand) < STILL:
                    cand_n += 1
                else:
                    cand, cand_n = card, 1
                if cand is not None and cand_n >= still_frames:
                    self.save_card(cand, chip, view, "watch")
                    saved += 1
                    last_saved, cand, cand_n = cand, None, 0
                    t_new = time.time()
                    if beep:
                        _beep()
                    if saved % 100 == 0:
                        self.folder.log("watch: %d cards (now %s / %s)" % (saved, chip, view))
                time.sleep(max(0.0, 1.0 / fps - (time.time() - t_frame)))
        finally:
            self.source.hold_on_top(False)
        self.folder.log("watch ended (%s): %d cards" % (why, saved))
        return {"cards": saved, "why": why}


def _beep() -> None:
    try:
        import winsound
        winsound.Beep(1400, 40)
    except Exception:  # noqa: BLE001
        print("\a", end="", flush=True)
