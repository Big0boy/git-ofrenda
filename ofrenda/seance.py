"""Light a candle, speak a name, and talk with the ghost of a deleted function."""

from __future__ import annotations

import re
import sys
import time

from .history import Ghost, Graveyard
from .spirits import Medium, persona
from .terminal import BONE, DIM, GOLD, ITALIC, MARIGOLD, RED, TEAL, VIOLET, Ink
from .words import day, span

BOLD_BONE = f"1;{BONE}"
COMMANDS = "/code  /life  /haunts  /resurrect  /leave"
_LEAVE = {"/leave", "/bye", "/exit", "/quit", "exit", "quit", "bye", "goodbye"}
_INTRO = (
    "*A candle is lit on your ofrenda and your name is spoken aloud.* "
    "Introduce yourself in two or three sentences: who you were, what you did, and how you died."
)


class OfflineGhost:
    """Answers from the facts alone, for nights when no local model is awake."""

    def __init__(self, ghost: Ghost):
        self.g = ghost

    def reply(self, question: str) -> str:
        g, q = self.g, question.lower()
        born = f"{g.born.author} wrote me on {day(g.born.when)}" if g.born else "I was here before your history began"
        if q.startswith("*a candle"):
            return (
                f"I am {g.label}, from {g.path}. {born}. "
                f"On {day(g.died.when)}, {g.died.author} let me go: “{g.died.subject}”."
            )
        if re.search(r"\b(who|wrote|write|made|create|born|birth|author)", q) and not re.search(r"kill|delet|remov", q):
            return f"{born}, in a commit called “{g.born.subject}”." if g.born else born + "."
        if re.search(r"\b(kill|delet|remov|die|died|death|why|how did you)", q):
            text = f"{g.died.author} removed me on {day(g.died.when)}, in commit {g.died.short}: “{g.died.subject}”. {g.cause}."
            if g.survived_by:
                text += f" {', '.join(g.survived_by)} took my place."
            return text
        if re.search(r"\b(code|body|source|look like|show)", q):
            return f"This is what I was:\n{g.source}" if g.source else "My body was lost; even git could not find it."
        if re.search(r"\b(back|resurrect|restore|return|revive)", q):
            return f"My body rests in `{g.resurrect_command}`. Whether I should return is yours to decide."
        if re.search(r"\b(haunt|unfinished|still|linger|call)", q):
            if g.haunts:
                return "They still speak my name: " + "; ".join(h.where for h in g.haunts[:4]) + "."
            return "Nothing holds me here. I left no unfinished business."
        if re.search(r"\b(what|do|did|purpose|job)", q):
            return g.remembrance or f"I was a {g.lang.name} {g.kind}. My first line was `{g.signature}`."
        return "The candle gutters. Without a local model to carry my voice, I can only tell you who made me, who ended me, and what I was. Ask me those."


def _pause(ink: Ink, seconds: float) -> None:
    if ink.on:
        time.sleep(seconds)


def _ritual(g: Ghost, ink: Ink, medium: Medium) -> None:
    lived = f"born {day(g.born.when)} · died {day(g.died.when)}" if g.born else f"died {day(g.died.when)}"
    if g.lifespan_days is not None:
        lived += f" · lived {span(g.lifespan_days)}"
    lines = [
        f"  {ink('🕯', MARIGOLD)}  You light a candle and speak its name: {ink(g.label, BOLD_BONE)}",
        f"  {ink('🌼', MARIGOLD)}  Marigold petals mark the path from {ink(g.path, GOLD)}",
        f"  {ink('✦', VIOLET)}  {ink(lived, DIM)}",
    ]
    if g.calls_left:
        h = next(h for h in g.haunts if h.is_call)
        lines.append(f"  {ink('⚠', RED)}  {ink(f'Something still calls it, at {h.where}', RED)}")
    lines.append(f"  {ink('The flame leans toward you. Something is here.', ITALIC, VIOLET)}")
    print()
    for line in lines:
        print(line)
        _pause(ink, 0.35)
    voice = f"voice: {medium.model} (local)" if medium.ready else f"voice: offline ({medium.problem})"
    print(ink(f"\n  {COMMANDS}    {voice}\n", DIM))


def _speak(g: Ghost, medium: Medium, offline: OfflineGhost, messages: list[dict], ink: Ink) -> str:
    prefix = ink(f"{g.label} ›", BOLD_BONE) + " "
    sys.stdout.write(prefix)
    sys.stdout.flush()
    if medium.ready:
        parts: list[str] = []
        try:
            for piece in medium.stream_chat(messages):
                if not parts:
                    piece = piece.lstrip()
                parts.append(piece)
                sys.stdout.write(ink(piece, TEAL))
                sys.stdout.flush()
            if parts:
                print()
                return "".join(parts)
        except (OSError, ValueError):
            if parts:
                print(ink("  …the voice fades.", DIM))
                return "".join(parts)
    text = offline.reply(messages[-1]["content"])
    print(ink(text, TEAL))
    return text


def _command(cmd: str, g: Ghost, ink: Ink) -> bool:
    """Handle a slash command. Returns True if it was one."""
    if cmd == "/code":
        print(ink(f"\n{g.source or '(its body could not be recovered)'}\n", GOLD))
    elif cmd == "/life":
        if not g.memories:
            print(ink("  No other commits shaped it.", DIM))
        for m in reversed(g.memories):
            print(f"  {ink(day(m.when), GOLD)}  {m.author}: {m.subject}  {ink(m.short, DIM)}")
    elif cmd == "/haunts":
        if not g.haunts:
            print(ink("  Nothing in today's code speaks its name.", DIM))
        for h in g.haunts:
            tag = ink("still called", RED) if h.is_call else ink("mentioned", TEAL)
            print(f"  {tag}  {ink(h.where, GOLD)}  {h.text}")
    elif cmd == "/resurrect":
        print(ink("  Its body rests here; run this to see it whole:", DIM))
        print(f"    {ink(g.resurrect_command, GOLD)}")
    elif cmd in ("/help", "/?"):
        print(ink(f"  {COMMANDS}", DIM))
    else:
        return False
    return True


def hold(graveyard: Graveyard, g: Ghost, medium: Medium, ask: str | None = None, ink: Ink | None = None) -> int:
    ink = ink or Ink()
    offline = OfflineGhost(g)
    system = {"role": "system", "content": persona(graveyard, g)}
    history: list[dict] = []

    def turn(text: str) -> None:
        history.append({"role": "user", "content": text})
        answer = _speak(g, medium, offline, [system, *history[-12:]], ink)
        history.append({"role": "assistant", "content": answer})

    if ask:
        turn(ask)
        return 0
    _ritual(g, ink, medium)
    turn(_INTRO)
    while True:
        try:
            question = input("\n" + ink("you ›", MARIGOLD) + " ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            question = "/leave"
        if not question:
            continue
        if question.lower() in _LEAVE:
            print(ink(f"\n  The candle gutters out. {g.label} returns to the history.\n", ITALIC, VIOLET))
            return 0
        if question.startswith("/") and _command(question.split()[0].lower(), g, ink):
            continue
        turn(question)
