"""Colour and layout for the terminal altar."""

from __future__ import annotations

import os
import shutil
import sys
import textwrap

from .history import Ghost, Graveyard
from .words import day, span

MARIGOLD, MAGENTA, VIOLET, BONE, TEAL, RED, GOLD = "38;5;208", "38;5;199", "38;5;141", "38;5;230", "38;5;44", "38;5;203", "38;5;221"
DIM, BOLD, ITALIC = "2", "1", "3"


class Ink:
    def __init__(self, stream=sys.stdout, force: bool | None = None):
        if force is None:
            force = stream.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"
        self.on = force

    def __call__(self, text: str, *codes: str) -> str:
        if not self.on or not codes:
            return text
        return f"\x1b[{';'.join(codes)}m{text}\x1b[0m"


def width() -> int:
    return max(48, min(96, shutil.get_terminal_size((88, 24)).columns))


def _wrap(text: str, indent: str, w: int) -> list[str]:
    return textwrap.wrap(text, w - len(indent), initial_indent=indent, subsequent_indent=indent) or [indent]


def epitaph(g: Ghost, ink: Ink) -> str:
    w = width()
    pad = "      "
    lived = (
        f"{day(g.born.when)} → {day(g.died.when)} · {span(g.lifespan_days)}"
        if g.born and g.lifespan_days is not None
        else f"before memory → {day(g.died.when)}"
    )
    out = [f"  {ink('🕯', MARIGOLD)}  {ink(g.label, BOLD, BONE)}  {ink(lived, GOLD)}"]
    who = f"{g.path} · written by {g.born.author}" if g.born else g.path
    who += f" · laid to rest by {g.died.author}" + (" (its own author)" if g.by_own_hand else "")
    out += [ink(line, DIM) for line in _wrap(who, pad, w)]
    out += [ink(line, VIOLET) for line in _wrap(f"cause: {g.cause} — “{g.died.subject}”", pad, w)]
    if g.remembrance:
        out += _wrap(g.remembrance, pad, w)
    for line in g.calavera:
        out.append(ink(f"{pad}  {line}", ITALIC, MAGENTA))
    if g.survived_by:
        out.append(ink(f"{pad}survived by: {', '.join(g.survived_by)}", TEAL))
    if g.calls_left:
        h = next(h for h in g.haunts if h.is_call)
        out.append(ink(f"{pad}⚠ unfinished business: still called at {h.where}", RED))
    elif g.haunts:
        out.append(ink(f"{pad}still spoken of in {g.haunts[0].where}", TEAL))
    return "\n".join(out)


def header(graveyard: Graveyard, shown: int, ink: Ink) -> str:
    w = width()
    title = f" OFRENDA · {graveyard.name} "
    bar = "─" * max(4, (w - len(title) - 4) // 2)
    lines = [
        "",
        ink(f"  {bar}{title}{bar}", MARIGOLD),
        ink(
            f"  {len(graveyard.ghosts)} departed across {graveyard.commits} commits"
            + (f" · showing {shown}" if shown < len(graveyard.ghosts) else ""),
            DIM,
        ),
        "",
    ]
    return "\n".join(lines)
