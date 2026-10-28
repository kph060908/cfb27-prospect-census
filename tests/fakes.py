"""A simulated Prospect List screen for the tests: no game, no OCR."""
import random

from PIL import Image, ImageDraw

from census.geometry import BOXES, REF_SIZE


def card_pattern(rid: int, size) -> Image.Image:
    """A recruit's card: blocks of colour drawn from his id, so two recruits differ a lot and one recruit never does."""
    rnd = random.Random(rid)
    small = Image.new("RGB", (8, 6))
    small.putdata([tuple(rnd.randrange(256) for _ in range(3)) for _ in range(48)])
    return small.resize(size, Image.NEAREST)


class FakeScreen:
    """Lists keyed (chip, view) -> recruit ids. Down moves the cursor (clamped at the end), L2 the chip, R2 the view.
    drop_every=N loses every Nth press, the way a busy stream does."""

    def __init__(self, lists: dict, chips: list, views: list, drop_every: int = 0):
        self.lists, self.chips, self.views = lists, chips, views
        self.chip, self.view, self.cursor = chips[0], views[0], 0
        self.drop_every, self.presses, self.popup = drop_every, 0, False
        self.raw_size = REF_SIZE

    # source
    def rows(self):
        return self.lists.get((self.chip, self.view), [])

    def current(self):
        rows = self.rows()
        return rows[self.cursor] if rows else None

    def render(self, rid=None, blend_with=None) -> Image.Image:
        img = Image.new("RGB", REF_SIZE, (40, 40, 40))
        d = ImageDraw.Draw(img)
        d.rectangle(BOXES["header"], fill=(30, 30, 30) if self.popup else (200, 120, 40))
        d.rectangle(BOXES["tab"], fill=(240, 240, 240))
        d.rectangle(BOXES["chip"], fill=(60 + 9 * self.chips.index(self.chip), 50, 50))
        d.rectangle(BOXES["view"], fill=(50, 60 + 9 * self.views.index(self.view), 50))
        box = BOXES["card"]
        size = (box[2] - box[0], box[3] - box[1])
        rid = self.current() if rid is None else rid
        if rid is not None:
            card = card_pattern(rid, size)
            if blend_with is not None:
                card = Image.blend(card, card_pattern(blend_with, size), 0.5)
            img.paste(card, box[:2])
        return img

    def grab(self):
        return self.render()

    def hold_on_top(self, on):
        pass

    def describe(self):
        return "fake"

    # keys
    name = "fake"

    def press(self, button, hold=0.0):
        self.presses += 1
        if self.drop_every and self.presses % self.drop_every == 0:
            return
        if button == "down":
            self.cursor = min(self.cursor + 1, max(0, len(self.rows()) - 1))
        elif button == "up":
            self.cursor = max(0, self.cursor - 1)
        elif button == "l2":
            self.chip = self.chips[(self.chips.index(self.chip) + 1) % len(self.chips)]
            self.cursor = 0
        elif button == "r2":
            self.view = self.views[(self.views.index(self.view) + 1) % len(self.views)]
            self.cursor = 0

    def labels(self, img):
        return self.chip, self.view


class ScriptedWatch(FakeScreen):
    """Watch mode: each grab shows the next step of a script (recruit id, or ('blend', a, b) mid-change);
    when the script runs out it writes the STOP file and keeps showing the last frame."""

    def __init__(self, script, stop_file, **kw):
        super().__init__(**kw)
        self.script, self.i, self.stop_file = script, 0, stop_file

    def grab(self):
        step = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        if self.i >= len(self.script):
            self.stop_file.write_text("stop", encoding="utf-8")
        if isinstance(step, tuple) and step[0] == "blend":
            return self.render(step[1], blend_with=step[2])
        if isinstance(step, tuple) and step[0] == "chip":
            self.chip = step[1]
            return self.render(step[2])
        return self.render(step)
