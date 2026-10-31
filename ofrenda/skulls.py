"""Deterministic calavera (sugar skull) portraits: the same name always gets the same face."""

from __future__ import annotations

import hashlib
import math
import random

BONE = "#f8efe2"
INK = "#26133b"
ACCENTS = ("#e6197e", "#ff8c1a", "#1fb5ac", "#8a4fff", "#8cc63f", "#3fa9f5", "#e53935", "#ffc93c")

_SKULL = (
    "M60 8 C30 8 12 28 12 56 C12 72 19 82 28 87 L30 104 C31 116 44 122 60 122 "
    "C76 122 89 116 90 104 L92 87 C101 82 108 72 108 56 C108 28 90 8 60 8 Z"
)
_HEART = "M0 6 C-8 -2 -6 -8 -2 -7 C-1 -7 0 -6 0 -5 C0 -6 1 -7 2 -7 C6 -8 8 -2 0 6 Z"


def _f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def scallop(r: float, bumps: int, bulge: float = 1.2) -> str:
    """A scalloped circle centred on 0,0: the outline of a marigold layer."""
    pts = []
    for k in range(bumps):
        a0 = 2 * math.pi * k / bumps
        a1 = 2 * math.pi * (k + 1) / bumps
        am = (a0 + a1) / 2
        if k == 0:
            pts.append(f"M{_f(r * math.cos(a0))} {_f(r * math.sin(a0))}")
        pts.append(
            f"Q{_f(r * bulge * math.cos(am))} {_f(r * bulge * math.sin(am))} {_f(r * math.cos(a1))} {_f(r * math.sin(a1))}"
        )
    return " ".join(pts) + " Z"


def marigold(x: float, y: float, scale: float = 1.0) -> str:
    layers = ((9, "#e8590c"), (6.6, "#ff8c1a"), (4.2, "#ffb627"))
    rings = "".join(
        f'<path d="{scallop(r, 12)}" fill="{c}" stroke="{INK}" stroke-width="0.6"/>' for r, c in layers
    )
    return f'<g transform="translate({_f(x)} {_f(y)}) scale({scale})">{rings}<circle r="1.6" fill="#b4400a"/></g>'


def _eye(x: float, y: float, style: str, a: str, b: str, petals: int) -> str:
    parts = []
    if style == "petals":
        for k in range(petals):
            ang = 360 * k / petals
            rad = math.radians(ang)
            cx, cy = x + 19 * math.cos(rad), y + 19 * math.sin(rad)
            fill = a if k % 2 == 0 else b
            parts.append(
                f'<ellipse cx="{_f(cx)}" cy="{_f(cy)}" rx="4.2" ry="7" fill="{fill}" stroke="{INK}" '
                f'stroke-width="1" transform="rotate({_f(ang + 90)} {_f(cx)} {_f(cy)})"/>'
            )
    elif style == "scallop":
        for k in range(12):
            rad = 2 * math.pi * k / 12
            parts.append(
                f'<circle cx="{_f(x + 17 * math.cos(rad))}" cy="{_f(y + 17 * math.sin(rad))}" r="4.3" '
                f'fill="{a if k % 3 else b}" stroke="{INK}" stroke-width="1"/>'
            )
    else:  # rays
        for k in range(10):
            rad = 2 * math.pi * k / 10
            c, s = math.cos(rad), math.sin(rad)
            parts.append(
                f'<line x1="{_f(x + 15 * c)}" y1="{_f(y + 15 * s)}" x2="{_f(x + 22 * c)}" y2="{_f(y + 22 * s)}" '
                f'stroke="{a}" stroke-width="3" stroke-linecap="round"/>'
                f'<circle cx="{_f(x + 25.5 * c)}" cy="{_f(y + 25.5 * s)}" r="1.6" fill="{b}"/>'
            )
    parts.append(f'<circle cx="{x}" cy="{y}" r="12.5" fill="{INK}"/>')
    parts.append(f'<circle cx="{x - 4}" cy="{y - 4}" r="3" fill="#fff" opacity=".85"/>')
    return "".join(parts)


def _brow(rnd: random.Random, a: str, b: str) -> str:
    motif = rnd.choice(("flower", "diamond", "heart", "sun", "dots"))
    if motif == "flower":
        petals = "".join(
            f'<ellipse cx="60" cy="21" rx="4.5" ry="8" fill="{b}" stroke="{INK}" stroke-width="1" '
            f'transform="rotate({k * 60} 60 29)"/>'
            for k in range(6)
        )
        return petals + f'<circle cx="60" cy="29" r="4.5" fill="{a}" stroke="{INK}" stroke-width="1"/>'
    if motif == "diamond":
        return (
            f'<path d="M60 15 L71 30 L60 45 L49 30 Z" fill="{b}" stroke="{INK}" stroke-width="1.2"/>'
            f'<path d="M60 22 L65.5 30 L60 38 L54.5 30 Z" fill="{a}"/>'
        )
    if motif == "heart":
        dots = "".join(
            f'<circle cx="{_f(60 + 16 * math.cos(math.radians(d)))}" cy="{_f(31 + 16 * math.sin(math.radians(d)))}" r="1.8" fill="{b}"/>'
            for d in range(200, 341, 28)
        )
        return f'<path d="{_HEART}" transform="translate(60 31) scale(1.9)" fill="{a}" stroke="{INK}" stroke-width=".6"/>' + dots
    if motif == "sun":
        rays = "".join(
            f'<path d="M-2.4 -9 L0 -15 L2.4 -9 Z" fill="{b}" transform="translate(60 30) rotate({k * 30})"/>' for k in range(12)
        )
        return rays + f'<circle cx="60" cy="30" r="7.5" fill="{a}" stroke="{INK}" stroke-width="1"/>'
    return "".join(
        f'<circle cx="{cx}" cy="{cy}" r="3.2" fill="{a if (cx, cy) == (60, 30) else b}" stroke="{INK}" stroke-width=".8"/>'
        for cx, cy in ((60, 20), (50, 30), (60, 30), (70, 30), (60, 40))
    )


def _cheeks(rnd: random.Random, c: str) -> str:
    style = rnd.choice(("swirl", "dots", "petal"))
    out = []
    for x, flip in ((25, -1), (95, 1)):
        if style == "swirl":
            out.append(
                f'<path d="M{x} 84 c{3 * flip} -4 {7 * flip} 0 {4 * flip} 4 c{-2 * flip} 2 {-5 * flip} 0 {-3 * flip} -2" '
                f'fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"/>'
            )
        elif style == "dots":
            out.append("".join(f'<circle cx="{x + dx * flip}" cy="{84 + dy}" r="2" fill="{c}"/>' for dx, dy in ((0, 0), (4, -3), (4, 3))))
        else:
            out.append(
                "".join(
                    f'<ellipse cx="{x}" cy="80.5" rx="1.8" ry="3.5" fill="{c}" transform="rotate({k * 90} {x} 84)"/>'
                    for k in range(4)
                )
            )
    return "".join(out)


def _mouth() -> str:
    parts = [f'<path d="M36 99 Q60 112 84 99" fill="none" stroke="{INK}" stroke-width="2.5" stroke-linecap="round"/>']
    for k in range(1, 8):
        t = k / 8
        px = (1 - t) ** 2 * 36 + 2 * (1 - t) * t * 60 + t**2 * 84
        py = (1 - t) ** 2 * 99 + 2 * (1 - t) * t * 112 + t**2 * 99
        parts.append(
            f'<line x1="{_f(px)}" y1="{_f(py - 5)}" x2="{_f(px)}" y2="{_f(py + 5)}" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>'
        )
    return "".join(parts)


def portrait(seed: str, crowned: bool = False, title: str = "") -> str:
    rnd = random.Random(hashlib.sha256(seed.encode()).digest())
    a, b, c = rnd.sample(ACCENTS, 3)
    style = rnd.choice(("petals", "scallop", "rays"))
    petals = rnd.choice((6, 8, 10))
    parts = [f'<path d="{_SKULL}" fill="{BONE}" stroke="{INK}" stroke-width="2.5"/>']
    if crowned:
        for deg in (-150, -120, -90, -60, -30):
            rad = math.radians(deg)
            parts.append(marigold(60 + 49 * math.cos(rad), 57 + 49 * math.sin(rad), 1.05))
    parts.append(_brow(rnd, a, b))
    parts.append(_eye(40, 62, style, a, b, petals))
    parts.append(_eye(80, 62, style, a, b, petals))
    parts.append(f'<path d="{_HEART}" transform="translate(60 81) rotate(180) scale(1.15)" fill="{INK}"/>')
    parts.append(_mouth())
    parts.append(_cheeks(rnd, c))
    parts.append("".join(f'<circle cx="{x}" cy="{y}" r="1.7" fill="{c}"/>' for x, y in ((53, 116), (60, 118), (67, 116))))
    label = f' aria-label="{title}"' if title else ' aria-hidden="true"'
    return f'<svg class="skull" viewBox="0 -8 120 138" role="img"{label}>{"".join(parts)}</svg>'
