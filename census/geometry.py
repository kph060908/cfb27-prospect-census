"""Where things sit on the Prospect List screen, in 2560 x 1440 reference pixels.

Every grab is scaled to 2560 x 1440 before anything is cropped, so these boxes hold for any 16:9 picture of
1280 x 720 or more. A picture that sits differently (a console screen-size setting, a capture with borders) gets
its own boxes in setup.json after a calibration grab (`census setup --box card=x0,y0,x1,y1`).
"""

REF_SIZE = (2560, 1440)
CARD_SIZE = (502, 368)              # the card crop at reference scale; the card reader expects this size

BOXES = {
    "card": (1984, 440, 2486, 808),     # the recruit card on the right: first name down to hometown
    "header": (100, 140, 1140, 180),    # the Recruiting tab strip (Recruiting Board, Prospect List, ...)
    "tab": (376, 138, 544, 180),        # the Prospect List tab: a white pill when it is the open tab
    "chip": (182, 462, 624, 512),       # the L2 position box (ANY, QB, HB ...)
    "view": (1390, 462, 1832, 512),     # the R2 view pill (ANY STATE, 1 STAR PROSPECTS ...)
}

ASPECT_TOLERANCE = 0.02             # a picture this far from 16:9 is refused rather than stretched
MIN_WIDTH = 1280


def boxes_with(overrides: dict | None) -> dict:
    out = dict(BOXES)
    for k, v in (overrides or {}).items():
        out[k] = tuple(int(x) for x in v)
    return out
