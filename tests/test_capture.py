"""The capture logic on a simulated screen: python -m unittest discover tests"""
import json
import tempfile
import time
import types
import unittest
from pathlib import Path

from census import capture as cap_mod
from census.capture import Capture
from census.folder import Folder
from census.geometry import BOXES

from fakes import FakeScreen, ScriptedWatch

CHIPS = ["ANY", "QB", "HB", "FB"]
VIEWS = ["ANY STATE", "TOP PROSPECTS", "1 STAR PROSPECTS"]
NO_WAIT = types.SimpleNamespace(sleep=lambda s: None, time=time.time, strftime=time.strftime)


def make(screen, tmp):
    f = Folder.create("Fake League", str(Path(tmp) / "cap"))
    c = Capture(f, screen, screen, dict(BOXES))
    c.labels = screen.labels                     # no OCR in the tests
    cap_mod.time = NO_WAIT                       # no waiting either
    screen.render().crop(BOXES["header"]).save(f.path / "header_ref.png")
    return f, c


def index(f):
    return f.jsonl("index.jsonl")


class WalkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def lists(self):
        return {("ANY", "ANY STATE"): list(range(1, 41)), ("QB", "ANY STATE"): list(range(100, 137)),
                ("HB", "ANY STATE"): list(range(200, 251)), ("FB", "ANY STATE"): list(range(300, 309)),
                ("ANY", "1 STAR PROSPECTS"): list(range(900, 912))}

    def test_walk_reads_every_row_once(self):
        s = FakeScreen(self.lists(), CHIPS, VIEWS)
        f, c = make(s, self.tmp.name)
        r = c.walk()
        self.assertEqual((r["rows"], r["why"]), (40, "end of list"))
        self.assertEqual(len(index(f)), 40)

    def test_dropped_presses_are_pressed_again(self):
        s = FakeScreen(self.lists(), CHIPS, VIEWS, drop_every=4)
        f, c = make(s, self.tmp.name)
        r = c.walk()
        self.assertEqual((r["rows"], r["why"]), (40, "end of list"))

    def test_a_popup_stops_the_walk(self):
        s = FakeScreen(self.lists(), CHIPS, VIEWS)
        f, c = make(s, self.tmp.name)
        real = s.press

        def press(button, hold=0.0):
            real(button, hold)
            if s.cursor == 10:
                s.popup = True
        s.press = press
        r = c.walk()
        self.assertEqual(r["why"], "screen changed")
        self.assertEqual(r["rows"], 10)

    def test_chips_walks_every_list_then_stops_on_any(self):
        s = FakeScreen(self.lists(), CHIPS, VIEWS)
        f, c = make(s, self.tmp.name)
        s.press("l2")                            # the player is on QB
        out = c.chips()
        self.assertEqual([x["rows"] for x in out], [37, 51, 9])
        self.assertEqual([x["chip"] for x in f.lists()], ["QB", "HB", "FB"])
        self.assertEqual(s.chip, "ANY")
        self.assertEqual(len(index(f)), 37 + 51 + 9)

    def test_chips_refuses_a_filtered_view(self):
        s = FakeScreen(self.lists(), CHIPS, VIEWS)
        f, c = make(s, self.tmp.name)
        s.press("l2")
        s.press("r2")
        out = c.chips()
        self.assertIn("not ANY STATE", out[0]["why"])
        self.assertEqual(f.lists(), [])

    def test_press_until_a_view(self):
        s = FakeScreen(self.lists(), CHIPS, VIEWS)
        f, c = make(s, self.tmp.name)
        r = c.press_until("r2", "view", "1 star prospects")
        self.assertTrue(r["reached"])
        self.assertEqual(r["presses"], 2)
        self.assertEqual(s.view, "1 STAR PROSPECTS")


class WatchTests(unittest.TestCase):
    def test_every_card_that_holds_still_is_saved_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Folder.create("Fake League", str(Path(tmp) / "cap"))
            ids = list(range(500, 530))
            script = []
            for i, rid in enumerate(ids):
                if i:
                    script.append(("blend", ids[i - 1], rid))          # a frame caught mid-change
                script += [rid] * 4                                     # then it holds still
            script += [("chip", "QB", 600)] * 4 + [601] * 2 + [("blend", 601, 602)] + [602] * 5
            s = ScriptedWatch(script, f.path / "STOP", lists={}, chips=CHIPS, views=VIEWS)
            c = Capture(f, s, s, dict(BOXES))
            c.labels = s.labels
            cap_mod.time = NO_WAIT
            s.render(500).crop(BOXES["header"]).save(f.path / "header_ref.png")
            calls = []
            cap_mod.read_label = lambda img: calls.append(1) or "QB"
            r = c.watch(idle=60, fps=1000, still_frames=3)
            self.assertEqual(r["why"], "stopped")
            got = index(f)
            # 30 + 600 + 602; 601 held for 2 frames only, so it never counted
            self.assertEqual(len(got), 32)


if __name__ == "__main__":
    unittest.main()
