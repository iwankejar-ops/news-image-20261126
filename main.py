#!/usr/bin/env python3
"""World News, Thursday 26 November 2026 -- one image.

A hand-written renderer: it draws a newspaper front page that sums up
the six most consequential world stories of Thursday 26 November 2026,
each verified against the day's reporting:

    1. Russia's own figures put its Ukraine war dead at nearly 500,000
    2. The Nasdaq sinks nearly 4% as AI fears and Trump tariffs spook
       Wall Street
    3. A fuel tanker crash on a Cairo highway kills 31 in a huge fire
    4. Iran says ships hit underwater mines in the Strait of Hormuz
    5. Trump unveils new tariffs on Japan, China and the EU; Taiwan
       is set at 15%
    6. North Korea expels the Swiss diplomat and orders Switzerland
       to close its new office in Pyongyang

Pure Python standard library. No network, no files read, no randomness:
running it twice writes byte-identical PNGs. Output is 1024x1024, well
under the 1 MiB limit.
"""

import binascii
import os
import struct
import zlib
from math import cos, radians, sin, sqrt

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 242, 231)      # warm newspaper cream
PANEL = (255, 253, 247)      # panel white
INK = (18, 22, 30)           # near-black text
NAVY = (18, 40, 75)          # header band
NAVY_DARK = (10, 26, 52)
GOLD = (201, 162, 39)
RED = (178, 34, 34)
DARKRED = (120, 20, 20)
GREY = (110, 112, 118)
LIGHTGREY = (200, 200, 196)
SKY = (140, 180, 215)
SEA = (28, 80, 110)
SEA_DARK = (16, 52, 78)
ORANGE = (235, 120, 30)
AMBER = (245, 180, 60)
YELLOW = (250, 220, 90)
GREEN = (70, 130, 70)
FIELD = (52, 64, 54)         # dark battlefield green-grey
BROWN = (120, 85, 50)
DESERT = (225, 170, 90)
SUNSET = (235, 130, 60)
DUSK = (60, 64, 78)          # overcast war sky
STEEL = (52, 58, 70)         # chart-panel dark
CONTAINER_RED = (196, 52, 44)
CONTAINER_BLUE = (42, 92, 150)
CONTAINER_GREEN = (52, 130, 78)


# ---------------------------------------------------------------- canvas
class Canvas:
    """An RGB canvas backed by one flat bytearray."""

    def __init__(self, w, h, fill):
        self.w = w
        self.h = h
        self.buf = bytearray(bytes(fill) * (w * h))
        self.cx0, self.cy0, self.cx1, self.cy1 = 0, 0, w, h

    def set_clip(self, x, y, w, h):
        """Restrict all drawing to a rectangle (scenes stay in their box)."""
        self.cx0, self.cy0 = max(0, x), max(0, y)
        self.cx1, self.cy1 = min(self.w, x + w), min(self.h, y + h)

    def reset_clip(self):
        self.cx0, self.cy0, self.cx1, self.cy1 = 0, 0, self.w, self.h

    def px(self, x, y, c):
        if self.cx0 <= x < self.cx1 and self.cy0 <= y < self.cy1:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def rect(self, x, y, w, h, c):
        """Fill a rectangle, clipped to the canvas and the clip box."""
        x0 = max(self.cx0, x)
        y0 = max(self.cy0, y)
        x1 = min(self.cx1, x + w)
        y1 = min(self.cy1, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.buf[i:i + len(row)] = row

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        """Straight line by digital differential steps."""
        steps = max(1, max(abs(x1 - x0), abs(y1 - y0)))
        dx = (x1 - x0) / steps
        dy = (y1 - y0) / steps
        for i in range(steps + 1):
            self.px(round(x0 + dx * i), round(y0 + dy * i), c)

    def disc(self, cx, cy, r, c):
        """Filled disc, swept row by row from the centre outward."""
        for dy in range(0, r + 1):
            half = int(sqrt(r * r - dy * dy))
            self.rect(cx - half, cy - dy, 2 * half + 1, 1, c)
            if dy:
                self.rect(cx - half, cy + dy, 2 * half + 1, 1, c)

    def ring(self, cx, cy, r, c):
        """A one-pixel outline circle, for emblems and ornaments."""
        for ang in range(360):
            rad = radians(ang)
            self.px(cx + int(r * cos(rad)), cy + int(r * sin(rad)), c)

    def poly(self, pts, c):
        """Fill a polygon with a scanline fill."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x_a, y_a = pts[i]
                x_b, y_b = pts[(i + 1) % n]
                if y_a == y_b:
                    continue
                if (y_a <= y < y_b) or (y_b <= y < y_a):
                    t = (y - y_a) / (y_b - y_a)
                    xs.append(x_a + t * (x_b - x_a))
            if len(xs) >= 2:
                xs.sort()
                self.rect(int(xs[0]), y, int(xs[-1]) - int(xs[0]) + 1, 1, c)

    def vgrad(self, x, y, w, h, top, bottom):
        """Blend from the top colour down to the bottom colour."""
        steps = max(1, h - 1)
        dr = (bottom[0] - top[0]) / steps
        dg = (bottom[1] - top[1]) / steps
        db = (bottom[2] - top[2]) / steps
        for row in range(h):
            shade = (int(top[0] + dr * row),
                     int(top[1] + dg * row),
                     int(top[2] + db * row))
            self.rect(x, y + row, w, 1, shade)


# ---------------------------------------------------------------- PNG out
def write_png(cv, path):
    """Encode the canvas as a deterministic PNG (filter 0 rows)."""
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(kind, data):
        body = kind + data
        head = struct.pack(">I", len(data))
        tail = struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)
        return head + body + tail

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    magic = b"\x89PNG\r\n\x1a\n"
    png = magic + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- font
# A hand-drawn 5x7 pixel font. '#' is a set pixel. Every glyph is written
# out here by hand; the renderer draws them scaled, with 1 unit of space
# between letters. Text is rendered in capitals.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".....", "..#.."),
    ",": (".....", ".....", ".....", ".....", ".....", "..#..", "..#.."),
    ":": (".....", "..#..", ".....", ".....", ".....", "..#..", "....."),
    ";": (".....", "..#..", ".....", ".....", ".....", "..#..", "..#.."),
    "-": (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    "'": ("..#..", "..#..", ".....", ".....", ".....", ".....", "....."),
    "(": ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ")": (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    "&": (".##..", "#..#.", "#..#.", ".#...", "#.#.#", "#..#.", ".##.#"),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "%": ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.##.", "#..##"),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "+": (".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."),
    "=": (".....", ".....", "#####", ".....", "#####", ".....", "....."),
    '"': (".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."),
    "$": ("..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."),
    "#": (".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."),
}

BLANK = (".....", ".....", ".....", ".....", ".....", ".....", ".....")


def text_w(s, scale):
    """Pixel width of a string at a scale (5 px glyph + 1 px gap)."""
    return len(s) * 6 * scale - scale if s else 0


def draw_text(cv, x, y, s, scale, color):
    """Draw one line of text, capitals, left aligned at (x, y)."""
    s = s.upper()
    cx = x
    for ch in s:
        glyph = FONT.get(ch, BLANK)
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "#":
                    cv.rect(cx + col * scale, y + row * scale,
                            scale, scale, color)
        cx += 6 * scale


def draw_centred(cv, cx, y, s, scale, color):
    draw_text(cv, cx - text_w(s, scale) // 2, y, s, scale, color)


def wrap(s, max_px, scale):
    """Greedy word wrap into lines that fit max_px at the scale."""
    words = s.upper().split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_w(trial, scale) <= max_px or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- scenes
# Each scene draws inside the rectangle (x, y, w, h). All shapes are
# primitives: rectangles, lines, discs, triangles, gradients.

def scene_russia(cv, x, y, w, h):
    """A battlefield memorial under an overcast sky: rows of white
    crosses on a dark field, one red poppy in the foreground."""
    cv.vgrad(x, y, w, h, (58, 62, 76), (118, 120, 128))
    # pale sun behind cloud
    cv.disc(x + w - 90, y + 36, 18, (210, 208, 196))
    # ruined skyline on the horizon
    hor = y + h - 92
    for bx, bw, bh in ((0, 60, 30), (70, 40, 52), (120, 80, 26),
                       (210, 46, 60), (266, 90, 34), (366, 52, 48),
                       (428, 70, 28), (508, 60, 55), (578, 70, 30)):
        cv.rect(x + bx, hor - bh, bw, bh, (44, 48, 56))
        # broken tops: a few jagged roofs
        if bh > 44:
            cv.poly(((x + bx, hor - bh), (x + bx + bw // 2, hor - bh - 12),
                     (x + bx + bw, hor - bh)), (44, 48, 56))
    # dark field
    cv.rect(x, hor, w, h - (hor - y), FIELD)
    # rows of white crosses, shrinking into the distance
    for row, (cy, size, gap) in enumerate(((hor + 14, 5, 26),
                                           (hor + 30, 7, 34),
                                           (hor + 50, 10, 46))):
        cx = x + 24 + row * 8
        while cx < x + w - 20:
            cv.vline(cx, cy - size, 2 * size, (232, 230, 224))
            cv.hline(cx - size // 2 + 1, cy - size + 2, size, (232, 230, 224))
            cx += gap
    # one red poppy, foreground right
    px, py = x + w - 120, hor + 62
    for dx, dy in ((-9, -4), (9, -4), (-7, 8), (7, 8), (0, -10)):
        cv.disc(px + dx, py + dy, 8, RED)
    cv.disc(px, py, 6, DARKRED)
    cv.disc(px, py, 3, INK)
    cv.vline(px, py + 8, 18, GREEN)


def scene_nasdaq(cv, x, y, w, h):
    """A stock chart on a dark panel: the line plunges, red, to the
    bottom right, with a down arrow and the day's drop."""
    cv.rect(x, y, w, h, STEEL)
    # grid
    for gx in range(x + 24, x + w, 28):
        cv.vline(gx, y + 6, h - 12, (38, 44, 56))
    for gy in range(y + 10, y + h - 6, 16):
        cv.hline(x + 6, gy, w - 12, (38, 44, 56))
    # plunging line: steps down across the panel
    pts = [(x + 10, y + 14), (x + 60, y + 20), (x + 110, y + 18),
           (x + 150, y + 30), (x + 190, y + 26), (x + 230, y + 44),
           (x + 270, y + 58), (x + 310, y + 78)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        cv.line(x0, y0, x1, y1, RED)
        cv.line(x0, y0 + 1, x1, y1 + 1, RED)
    # down arrow at the end
    ax, ay = x + w - 26, y + h - 16
    cv.poly(((ax - 10, ay - 14), (ax + 10, ay - 14), (ax, ay)), RED)
    cv.vline(ax - 2, ay - 26, 14, RED)
    cv.vline(ax + 1, ay - 26, 14, RED)
    # the drop, in red, top right where the chart is empty
    draw_text(cv, x + w - 62, y + 8, "-4%", 2, (255, 90, 80))


def scene_cairo(cv, x, y, w, h):
    """A night highway: a fuel tanker under a huge fireball, smoke
    rising, headlights cutting the dark."""
    cv.vgrad(x, y, w, h, (16, 14, 26), (52, 44, 52))
    # distant city glow
    cv.disc(x + 40, y + h - 40, 22, (120, 80, 40))
    cv.disc(x + w - 30, y + h - 46, 18, (100, 70, 36))
    # road
    road = y + h - 26
    cv.rect(x, road, w, 26, (34, 34, 38))
    cv.hline(x, road, w, (210, 200, 170))
    for dx in range(10, w - 10, 34):
        cv.rect(x + dx, road + 12, 16, 3, (210, 200, 170))
    # tanker truck: cab + cylindrical tank
    tx = x + w // 2 - 90
    cv.rect(tx, road - 26, 180, 26, (70, 74, 82))
    cv.disc(tx + 20, road - 13, 12, (96, 100, 110))
    cv.rect(tx + 128, road - 34, 52, 34, (52, 56, 64))
    cv.rect(tx + 132, road - 30, 22, 12, (150, 200, 235))
    cv.disc(tx + 14, road, 7, (18, 18, 20))
    cv.disc(tx + 166, road, 7, (18, 18, 20))
    # headlight beam
    cv.poly(((tx + 180, road - 8), (x + w - 4, road + 6),
             (x + w - 4, road - 2)), (240, 220, 140))
    # fireball over the tank
    fx, fy = tx + 60, road - 34
    cv.disc(fx, fy, 20, (200, 70, 20))
    cv.disc(fx, fy, 14, ORANGE)
    cv.disc(fx, fy, 8, AMBER)
    cv.disc(fx, fy, 4, YELLOW)
    cv.poly(((fx - 12, fy - 16), (fx - 2, fy - 30), (fx + 8, fy - 16)),
            ORANGE)
    cv.poly(((fx + 4, fy - 14), (fx + 12, fy - 26), (fx + 20, fy - 14)),
            AMBER)
    # smoke puffs drifting to the sides
    for sx, sy, sr in ((fx - 30, fy - 14, 8), (fx + 32, fy - 18, 9),
                       (fx - 38, fy - 2, 7), (fx + 40, fy - 6, 8)):
        cv.disc(sx, sy, sr, (74, 72, 78))


def scene_hormuz(cv, x, y, w, h):
    """The Strait of Hormuz at dusk: a tanker crossing a dark sea,
    naval mines floating in its path, a low sun."""
    cv.vgrad(x, y, w, h, (250, 190, 110), (196, 96, 66))
    cv.disc(x + w - 58, y + 40, 20, (255, 236, 170))
    sea = y + 118
    cv.rect(x, sea, w, h - (sea - y), SEA)
    cv.rect(x, sea, w, 3, (120, 180, 210))
    # tanker: hull, deck, bridge tower, funnel
    hx = x + 30
    cv.poly(((hx, sea + 58), (hx + 14, sea + 34), (hx + 220, sea + 34),
             (hx + 234, sea + 58)), (24, 28, 36))
    cv.rect(hx + 18, sea + 22, 200, 14, (40, 46, 56))
    cv.rect(hx + 176, sea - 2, 34, 26, (52, 58, 68))
    cv.rect(hx + 184, sea - 14, 18, 12, (200, 60, 40))
    cv.rect(hx + 24, sea + 26, 12, 6, (250, 210, 110))
    cv.rect(hx + 120, sea + 26, 12, 6, (250, 210, 110))
    # wake
    for wx in range(hx + 10, hx + 230, 30):
        cv.line(wx, sea + 66, wx + 18, sea + 66, (120, 180, 210))
    # naval mines: spiked black spheres in the water
    for mx, my in ((x + 250, sea + 84), (x + 272, sea + 104),
                   (x + 232, sea + 120)):
        cv.disc(mx, my, 9, INK)
        for ang in range(0, 360, 45):
            ex = mx + int(14 * cos(radians(ang)))
            ey = my + int(14 * sin(radians(ang)))
            cv.line(mx, my, ex, ey, INK)
        cv.disc(mx, my, 9, INK)
    # wave lines
    for wy in (sea + 96, sea + 132, sea + 150):
        for wx in range(8, w - 20, 44):
            cv.line(x + wx, wy, x + wx + 22, wy, (90, 160, 200))


def scene_tariffs(cv, x, y, w, h):
    """A container port: stacked shipping containers, the front one
    marked 15%, a crane reaching over the yard."""
    cv.vgrad(x, y, w, h, (168, 196, 220), (226, 228, 224))
    cv.disc(x + 46, y + 30, 16, (255, 222, 130))
    # crane: mast, jib, hook line
    cv.vline(x + 34, y + 30, h - 60, (60, 64, 72))
    cv.hline(x + 34, y + 34, w - 60, (60, 64, 72))
    cv.line(x + 34, y + 34, x + 70, y + 84, (60, 64, 72))
    cv.vline(x + w - 44, y + 34, 66, (60, 64, 72))
    cv.rect(x + w - 52, y + 100, 16, 12, (60, 64, 72))
    # yard ground
    gy = y + h - 34
    cv.rect(x, gy, w, 34, (96, 96, 92))
    # container stacks
    def container(cx, cy, cw, ch, col):
        cv.rect(cx, cy, cw, ch, col)
        cv.rect(cx, cy, cw, 3, (255, 255, 255))
        for vx in range(cx + 12, cx + cw - 6, 14):
            cv.vline(vx, cy + 5, ch - 10, (0, 0, 0))
    container(x + 16, gy - 52, 96, 52, CONTAINER_BLUE)
    container(x + 120, gy - 52, 96, 52, CONTAINER_GREEN)
    container(x + 224, gy - 52, 84, 52, CONTAINER_RED)
    container(x + 16, gy - 104, 96, 52, CONTAINER_RED)
    container(x + 120, gy - 104, 96, 52, CONTAINER_BLUE)
    # front container, marked with the tariff rate
    container(x + 66, gy - 156, 190, 52, CONTAINER_RED)
    draw_text(cv, x + 66 + 95 - text_w("15%", 3) // 2, gy - 146, "15%", 3,
              (255, 255, 255))


def scene_pyongyang(cv, x, y, w, h):
    """An embassy at dusk: a grey ministry building, the Swiss flag
    lowered on its pole, a closed gate, a plane leaving the sky."""
    cv.vgrad(x, y, w, h, (188, 196, 210), (228, 226, 220))
    # departing plane
    px, py = x + w - 74, y + 26
    cv.poly(((px, py), (px + 26, py + 6), (px, py + 8)), (70, 74, 82))
    cv.line(px + 4, py + 2, px - 12, py - 6, (70, 74, 82))
    cv.line(px + 4, py + 4, px - 12, py + 12, (70, 74, 82))
    # ministry building
    bx, by = x + 56, y + 92
    cv.rect(bx, by, 210, 118, (150, 146, 140))
    cv.rect(bx, by - 14, 210, 14, (128, 124, 118))
    cv.poly(((bx + 20, by - 14), (bx + 105, by - 34), (bx + 190, by - 14)),
            (112, 108, 102))
    for col in range(bx + 18, bx + 200, 34):
        cv.rect(col, by + 16, 14, 88, (176, 172, 166))
    cv.rect(bx + 92, by + 76, 26, 28, (60, 56, 52))
    # steps
    cv.rect(bx - 8, by + 118, 226, 6, (128, 124, 118))
    cv.rect(bx - 16, by + 124, 242, 6, (112, 108, 102))
    # flagpole with the Swiss flag lowered to half mast
    fx = x + 40
    cv.vline(fx, y + 56, by + 130 - (y + 56), INK)
    cv.disc(fx, y + 52, 3, GOLD)
    cv.rect(fx + 2, y + 96, 44, 30, RED)
    cv.rect(fx + 20, y + 102, 8, 18, (255, 255, 255))
    cv.rect(fx + 12, y + 110, 24, 8, (255, 255, 255))
    # closed gate across the front
    gy = by + 138
    cv.rect(x + 8, gy, w - 16, 6, (50, 50, 54))
    for vx in range(x + 16, x + w - 12, 18):
        cv.vline(vx, gy, 22, (50, 50, 54))


# ---------------------------------------------------------------- panels
def panel(cv, x, y, w, h):
    cv.rect(x, y, w, h, PANEL)
    edges = ((x, y, w, 2), (x, y + h - 2, w, 2),
             (x, y, 2, h), (x + w - 2, y, 2, h))
    for (ex, ey, ew, eh) in edges:
        cv.rect(ex, ey, ew, eh, INK)


def story_text(cv, x, y, w, headline, caption, hscale=2, cscale=2):
    """Headline lines then caption lines inside a panel text zone."""
    yy = y
    for line in headline:
        draw_text(cv, x, yy, line, hscale, INK)
        yy += 7 * hscale + 4
    yy += 2
    for line in caption:
        draw_text(cv, x, yy, line, cscale, (70, 70, 74))
        yy += 7 * cscale + 3
    return yy


# ---------------------------------------------------------------- compose
def compose():
    cv = Canvas(W, H, PAPER)

    # header band
    cv.rect(0, 0, W, 100, NAVY)
    cv.rect(0, 100, W, 4, GOLD)
    # small globe emblem at the left of the masthead
    cv.ring(54, 50, 27, GOLD)
    cv.ring(54, 50, 19, GOLD)
    cv.vline(54, 23, 54, GOLD)
    cv.hline(27, 50, 54, GOLD)
    draw_centred(cv, W // 2, 14, "WORLD NEWS", 6, (250, 248, 240))
    draw_centred(cv, W // 2, 66, "THURSDAY 26 NOVEMBER 2026", 3, GOLD)

    # ---- lead story: Russia's own count of its Ukraine war dead
    panel(cv, 12, 116, 652, 396)
    cv.set_clip(14, 118, 648, 240)
    scene_russia(cv, 14, 118, 648, 240)
    cv.reset_clip()
    draw_text(cv, 28, 368, "LEAD STORY - UKRAINE WAR", 2, RED)
    draw_text(cv, 28, 390, "RUSSIA'S OWN TOLL:", 3, INK)
    draw_text(cv, 28, 415, "NEARLY 500,000 DEAD", 3, INK)
    cy = 448
    for line in wrap("Moscow's figures put its Ukraine war deaths at "
                     "almost half a million", 620, 2):
        draw_text(cv, 28, cy, line, 2, (70, 70, 74))
        cy += 17

    # ---- right column, top: Nasdaq sinks
    panel(cv, 676, 116, 336, 192)
    cv.set_clip(678, 118, 332, 92)
    scene_nasdaq(cv, 678, 118, 332, 92)
    cv.reset_clip()
    story_text(cv, 688, 218, 312,
               ["NASDAQ SINKS", "NEARLY 4%"],
               ["AI FEARS AND TRUMP TARIFFS", "SPOOK WALL STREET"])

    # ---- right column, bottom: Cairo tanker fire
    panel(cv, 676, 320, 336, 192)
    cv.set_clip(678, 322, 332, 92)
    scene_cairo(cv, 678, 322, 332, 92)
    cv.reset_clip()
    story_text(cv, 688, 422, 312,
               ["CAIRO TANKER", "FIRE KILLS 31"],
               ["FUEL TANKER CRASHES ON", "HIGHWAY; HUGE BLAZE"])

    # ---- bottom row, three stories
    # Strait of Hormuz: mines in the shipping lane
    panel(cv, 12, 524, 325, 428)
    cv.set_clip(14, 526, 321, 274)
    scene_hormuz(cv, 14, 526, 321, 274)
    cv.reset_clip()
    story_text(cv, 26, 812, 309,
               ["MINES IN THE", "STRAIT OF HORMUZ"],
               ["IRAN SAYS SHIPS HIT MINES;", "WARNS VESSELS TO",
                "COORDINATE PASSAGE"])
    # Trump tariffs: Taiwan set at 15%
    panel(cv, 349, 524, 326, 428)
    cv.set_clip(351, 526, 322, 274)
    scene_tariffs(cv, 351, 526, 322, 274)
    cv.reset_clip()
    story_text(cv, 363, 812, 309,
               ["TRUMP UNVEILS", "NEW TARIFFS"],
               ["TAIWAN SET AT 15% IN US", "PLAN FOR DUTIES ON",
                "JAPAN, CHINA AND EU"])
    # North Korea expels the Swiss diplomat
    panel(cv, 687, 524, 325, 428)
    cv.set_clip(689, 526, 321, 274)
    scene_pyongyang(cv, 689, 526, 321, 274)
    cv.reset_clip()
    story_text(cv, 701, 812, 309,
               ["NORTH KOREA", "EXPELS SWISS ENVOY"],
               ["PYONGYANG ORDERS", "SWITZERLAND TO CLOSE",
                "ITS NEW OFFICE"])

    # footer
    cv.rect(0, 960, W, 2, GOLD)
    draw_centred(cv, W // 2, 976, "SIX STORIES THAT DEFINED THE DAY", 2, INK)

    return cv


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    size = write_png(compose(), path)
    print("wrote %s (%d bytes, %dx%d)" % (path, size, W, H))


if __name__ == "__main__":
    main()
