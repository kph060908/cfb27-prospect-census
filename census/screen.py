"""Frame sources. Every grab comes back as a 2560 x 1440 RGB image, scaled from any 16:9 picture.

    window:<title>      Windows only: the client area of a visible window whose title contains <title>
                        (case-insensitive); when several match, the smallest one (chiaki-ng shows a host-list
                        window and a stream window with the same title; the stream is the smaller).
    region:x,y,w,h      any OS: a fixed rectangle of the screen, in physical pixels.

The grab copies what is on the screen, so the game picture must be visible: not minimized and not covered.
"""
from __future__ import annotations

import sys

from PIL import Image

from .geometry import ASPECT_TOLERANCE, MIN_WIDTH, REF_SIZE

IS_WIN = sys.platform.startswith("win")

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    try:                                    # true pixel coordinates on scaled displays
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass
    user32 = ctypes.windll.user32
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_uint]


class FrameError(RuntimeError):
    """The picture can't be used: no window, wrong shape, too small."""


def normalize(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    if h == 0 or abs((w / h) / (16 / 9) - 1) > ASPECT_TOLERANCE:
        raise FrameError("the picture is %dx%d, not 16:9. Resize the window (census fit-window), or set a region "
                         "that holds only the game picture." % (w, h))
    if w < MIN_WIDTH:
        raise FrameError("the picture is %dx%d; it needs to be at least 1280x720 (1920x1080 or more reads best)"
                         % (w, h))
    if (w, h) != REF_SIZE:
        img = img.resize(REF_SIZE, Image.LANCZOS)
    return img


# ---------------------------------------------------------------------------------------------- Windows windows
def client_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    rc = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rc)):
        return None
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return (int(pt.x), int(pt.y), int(rc.right - rc.left), int(rc.bottom - rc.top))


def list_windows() -> list[dict]:
    """Visible, not minimized top-level windows that have a title: handle, title, class, client rect."""
    if not IS_WIN:
        return []
    found = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _):
        if not user32.IsWindowVisible(h) or user32.IsIconic(h):
            return True
        n = user32.GetWindowTextLengthW(h)
        if n <= 0:
            return True
        title = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(h, title, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        rect = client_rect(h)
        if rect and rect[2] > 0 and rect[3] > 0:
            found.append({"hwnd": int(h), "title": title.value, "class": cls.value, "client": rect})
        return True

    user32.EnumWindows(proc(cb), 0)
    return found


def find_window(title: str, class_prefix: str = "") -> dict | None:
    """A title starting with '=' must match exactly (case-insensitive); otherwise containing it is enough."""
    exact = title.startswith("=")
    want = (title[1:] if exact else title).casefold()
    cands = [w for w in list_windows()
             if (w["title"].casefold() == want if exact else want in w["title"].casefold())
             and w["class"].startswith(class_prefix) and w["client"][2] >= 640 and w["client"][3] >= 360]
    if not cands:
        return None
    return min(cands, key=lambda w: w["client"][2] * w["client"][3])


def set_topmost(hwnd: int, on: bool) -> None:
    """Keep the picture visible over other windows while grabbing (no focus change)."""
    if IS_WIN and hwnd:
        user32.SetWindowPos(hwnd, wintypes.HWND(-1 if on else -2), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)


def fit_window(title: str, width: int = 1920, height: int = 1080) -> tuple[int, int]:
    """Resize a window so its client area is exactly width x height (16:9). Returns the new client size."""
    w = find_window(title)
    if w is None:
        raise FrameError("no visible window with %r in its title" % title)
    hwnd = w["hwnd"]
    wr = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    cx, cy, cw, ch = w["client"]
    extra_w = (wr.right - wr.left) - cw
    extra_h = (wr.bottom - wr.top) - ch
    user32.SetWindowPos(hwnd, None, 0, 0, width + extra_w, height + extra_h, 0x0002 | 0x0004 | 0x0010)
    rect = client_rect(hwnd)
    return (rect[2], rect[3]) if rect else (0, 0)


# ---------------------------------------------------------------------------------------------- sources
def _grab_rect(x: int, y: int, w: int, h: int) -> Image.Image:
    if IS_WIN:
        try:
            from PIL import ImageGrab
            return ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        except Exception:  # noqa: BLE001  (fall back to mss)
            pass
    import mss
    with mss.mss() as sct:
        shot = sct.grab({"left": x, "top": y, "width": w, "height": h})
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


class WindowSource:
    def __init__(self, title: str):
        if not IS_WIN:
            raise FrameError("window:<title> works on Windows only; use region:x,y,w,h on this OS")
        self.title = title
        self.hwnd = None
        self.raw_size = None

    def locate(self) -> dict:
        w = find_window(self.title)
        if w is None:
            raise FrameError("no visible window with %r in its title (run `census windows`)" % self.title)
        self.hwnd = w["hwnd"]
        return w

    def grab(self) -> Image.Image:
        if self.hwnd is None or not user32.IsWindow(self.hwnd) or user32.IsIconic(self.hwnd):
            self.locate()
        rect = client_rect(self.hwnd)
        if rect is None or rect[2] <= 0 or rect[3] <= 0:
            rect = self.locate()["client"]
        x, y, w, h = rect
        img = _grab_rect(x, y, w, h)
        self.raw_size = img.size
        return normalize(img)

    def hold_on_top(self, on: bool) -> None:
        if self.hwnd is None:
            self.locate()
        set_topmost(self.hwnd, on)

    def describe(self) -> str:
        return "window:%s" % self.title


class RegionSource:
    def __init__(self, x: int, y: int, w: int, h: int):
        self.rect = (x, y, w, h)
        self.raw_size = None

    def grab(self) -> Image.Image:
        img = _grab_rect(*self.rect)
        self.raw_size = img.size
        return normalize(img)

    def hold_on_top(self, on: bool) -> None:
        pass

    def describe(self) -> str:
        return "region:%d,%d,%d,%d" % self.rect


def make_source(spec: str):
    kind, _, arg = (spec or "").partition(":")
    if kind == "window" and arg:
        return WindowSource(arg)
    if kind == "region" and arg:
        parts = [int(p) for p in arg.split(",")]
        if len(parts) != 4:
            raise FrameError("region needs x,y,w,h")
        return RegionSource(*parts)
    raise FrameError("unknown source %r: use window:<title> or region:x,y,w,h" % spec)


def full_screen_grab() -> Image.Image:
    """Every monitor in one image (for finding the game picture when setting a region)."""
    if IS_WIN:
        from PIL import ImageGrab
        return ImageGrab.grab(all_screens=True).convert("RGB")
    import mss
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[0])
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
