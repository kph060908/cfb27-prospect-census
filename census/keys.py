"""Button presses the tool sends itself. One backend: chiaki-ng on Windows.

chiaki-ng (the open-source PS5 Remote Play client) maps keyboard keys to controller buttons. This backend posts
chiaki-ng's DEFAULT keyboard keys straight to its stream window (PostMessage: no focus change, nothing typed into
any other app). If the chiaki-ng keyboard mapping was changed from its defaults, don't use this backend: use
watch mode (`--keys none`), where the player presses the buttons and the tool records what appears.

Only these buttons can ever be sent: up, down, left, right, l1, r1, l2, r2, square, circle.
Cross and Triangle are never sent. On the Prospect List, Cross adds the highlighted recruit to the recruiting
board (a change to the live league) and Triangle opens a search form (held, it removes a board target).
"""
from __future__ import annotations

import sys
import time

ALLOWED = ("up", "down", "left", "right", "l1", "r1", "l2", "r2", "square", "circle")

# chiaki-ng's shipped keyboard defaults: (Windows virtual-key code, extended-key flag)
CHIAKI_DEFAULT_KEYS = {
    "up": (0x26, True), "down": (0x28, True), "left": (0x25, True), "right": (0x27, True),  # arrow keys
    "l2": (0x31, False), "l1": (0x32, False), "r1": (0x33, False), "r2": (0x34, False),    # 1 2 3 4
    "square": (0xDC, False),                                                                # backslash
    "circle": (0x08, False),                                                                # backspace
}


class KeyError_(RuntimeError):
    pass


class NoKeys:
    name = "none"

    def press(self, button: str, hold: float = 0.06) -> None:
        raise KeyError_("this setup has no key backend (watch mode): ask the player to press %s" % button.upper())


class ChiakiKeys:
    """Posts chiaki-ng default keys to the chiaki-ng stream window."""
    name = "chiaki"

    def __init__(self, title: str = "chiaki-ng"):
        if not sys.platform.startswith("win"):
            raise KeyError_("the chiaki key backend works on Windows only; use watch mode (--keys none)")
        import ctypes
        from ctypes import wintypes

        from . import screen
        self._screen = screen
        self.title = title
        self.user32 = ctypes.windll.user32
        self.user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.PostMessageW.restype = wintypes.BOOL
        self.user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
        self.user32.MapVirtualKeyW.restype = wintypes.UINT
        self.wintypes = wintypes
        self.hwnd = None

    def _target(self) -> int:
        if self.hwnd is None or not self.user32.IsWindow(self.hwnd):
            # chiaki-ng's own Qt window, title exactly "chiaki-ng": a browser tab about chiaki-ng never matches
            w = self._screen.find_window("=" + self.title, class_prefix="Qt")
            if w is None:
                raise KeyError_("no chiaki-ng stream window found (title exactly %r, a Qt window)" % self.title)
            self.hwnd = w["hwnd"]
        return self.hwnd

    def _post(self, vk: int, ext: bool, down: bool) -> None:
        scan = self.user32.MapVirtualKeyW(vk, 0)
        lp = 1 | (scan << 16) | ((1 << 24) if ext else 0)
        if not down:
            lp |= (1 << 30) | (1 << 31)
        ok = self.user32.PostMessageW(self._target(), 0x0100 if down else 0x0101,
                                      self.wintypes.WPARAM(vk), self.wintypes.LPARAM(lp))
        if not ok:
            raise KeyError_("PostMessage to the chiaki-ng window failed")

    def press(self, button: str, hold: float = 0.06) -> None:
        button = button.lower()
        if button not in ALLOWED:
            raise KeyError_("%s is not a button this tool sends (allowed: %s)" % (button, ", ".join(ALLOWED)))
        vk, ext = CHIAKI_DEFAULT_KEYS[button]
        self._post(vk, ext, True)
        time.sleep(hold)
        self._post(vk, ext, False)


def make_keys(spec: str | None):
    kind, _, arg = (spec or "none").partition(":")
    if kind in ("", "none"):
        return NoKeys()
    if kind == "chiaki":
        return ChiakiKeys(arg or "chiaki-ng")
    raise KeyError_("unknown key backend %r: use chiaki or none" % spec)
