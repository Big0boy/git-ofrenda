"""git-ofrenda: a Día de los Muertos altar for the code your repository has lost.

Installed on PATH as `git-ofrenda`, so git runs it as `git ofrenda`.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import time
import webbrowser
from pathlib import Path

from . import __version__, altar, gitio, seance
from .history import choose, find_ghosts, recall_memories
from .spirits import Medium, Scribe
from .terminal import DIM, GOLD, MARIGOLD, RED, TEAL, Ink, epitaph, header
from .words import day, span

SUBCOMMANDS = ("build", "list", "summon", "haunts")


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-C", "--repo", default=".", metavar="PATH", help="repository to read (default: here)")
    p.add_argument("--rev", default="HEAD", help="the present day to compare against (default: HEAD)")
    p.add_argument("--since", metavar="DATE", help="only walk history after DATE (anything git log --since takes)")
    p.add_argument("--tests", action="store_true", help="include deleted tests among the departed")


def _voice(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", help="Ollama model to channel (default: qwen3:8b, or the best one installed)")
    p.add_argument("--host", help="Ollama server (default: $OLLAMA_HOST or 127.0.0.1:11434)")
    p.add_argument("--no-ai", action="store_true", help="skip the model and use offline verses")


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="git ofrenda",
        description="Build a Día de los Muertos altar for the functions your repository deleted, "
        "and talk with their ghosts. Everything runs on this machine.",
    )
    top.add_argument("--version", action="version", version=f"git-ofrenda {__version__}")
    sub = top.add_subparsers(dest="command", metavar="command")

    b = sub.add_parser("build", help="build the altar (the default)")
    _common(b)
    _voice(b)
    b.add_argument("-n", "--limit", type=int, default=12, help="how many spirits the altar holds (default: 12)")
    b.add_argument("--all", action="store_true", help="honor every departed function")
    b.add_argument("--sort", choices=("recent", "lifespan", "size", "haunting"), default="recent")
    b.add_argument("-o", "--output", metavar="FILE", help="where to write the HTML altar (default: .git/ofrenda/ofrenda.html)")
    b.add_argument("--open", action="store_true", help="open the altar in a browser")
    b.add_argument("--fresh", action="store_true", help="ignore cached calaveras and write new ones")
    b.add_argument("--json", action="store_true", help="print the departed as JSON instead")
    b.add_argument("-q", "--quiet", action="store_true", help="only print where the altar was written")
    b.set_defaults(func=build)

    ls = sub.add_parser("list", help="list the departed, no model needed")
    _common(ls)
    ls.add_argument("--sort", choices=("recent", "lifespan", "size", "haunting"), default="recent")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=list_ghosts)

    s = sub.add_parser("summon", help="hold a séance with one departed function")
    _common(s)
    _voice(s)
    s.add_argument("name", help="the function or class to call back")
    s.add_argument("--ask", metavar="QUESTION", help="ask one question and print the answer")
    s.set_defaults(func=summon)

    h = sub.add_parser("haunts", help="find lines that still name dead code")
    _common(h)
    h.add_argument("--strict", action="store_true", help="exit 1 if any line still calls dead code (for CI)")
    h.set_defaults(func=haunts)
    return top


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0] not in SUBCOMMANDS and argv[0] not in ("-h", "--help", "--version")):
        argv.insert(0, "build")
    args = parser().parse_args(argv)
    try:
        return args.func(args)
    except gitio.GitError as exc:
        print(f"git-ofrenda: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


def _yard(args):
    return find_ghosts(args.repo, rev=args.rev, since=args.since, include_tests=args.tests)


def build(args) -> int:
    err = Ink(sys.stderr)
    say = (lambda *_: None) if args.quiet or args.json else (lambda msg: print(msg, file=sys.stderr))
    say(err(f"🕯  Walking the history of {gitio.toplevel(args.repo).name}…", MARIGOLD))
    yard = _yard(args)
    shown = choose(yard.ghosts, args.sort, None if args.all else max(1, args.limit))
    say(err(f"💀 {len(yard.ghosts)} departed found across {yard.commits} commits. Exhuming their last words…", DIM))
    for g in shown:
        g.memories = recall_memories(yard.root, g)

    medium = Medium(args.model, args.host, enabled=not args.no_ai)
    if medium.ready:
        say(err(f"🌼 Channeling them through {medium.model}, running locally in Ollama…", MARIGOLD))
    elif shown:
        say(err(f"🌼 No local model is awake ({medium.problem}). Writing offline verses.", DIM))
    scribe = Scribe(medium, gitio.git_dir(yard.root) / "ofrenda" / "spirits.json", fresh=args.fresh)
    for i, g in enumerate(shown, 1):
        started = time.monotonic()
        wrote = scribe.remember(g)
        note = f"{time.monotonic() - started:.1f}s" if wrote else ("remembered" if g.voice != "offline" else "offline")
        say(err(f"   [{i}/{len(shown)}] {g.label}  ", DIM) + err(note, DIM))
    scribe.save()

    if args.json:
        print(json.dumps({"repository": yard.name, "commits": yard.commits, "departed": [g.to_dict() for g in shown]}, indent=2, ensure_ascii=False))
        return 0

    out = Path(args.output) if args.output else gitio.git_dir(yard.root) / "ofrenda" / "ofrenda.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(altar.render(yard, shown, medium.label), encoding="utf-8")
    uri = out.resolve().as_uri()

    ink = Ink()
    if not args.quiet:
        print(header(yard, len(shown), ink))
        for g in shown:
            print(epitaph(g, ink))
            print()
        if not shown:
            print("  No departed code was found. This history has lost nothing, yet.\n")
        print(f"  {ink('Altar built:', MARIGOLD)} {uri}")
        if shown:
            print(f"  {ink('Speak with one:', MARIGOLD)} git ofrenda summon {shown[0].name}\n")
    else:
        print(uri)
    if args.open:
        webbrowser.open(uri)
    return 0


def list_ghosts(args) -> int:
    yard = _yard(args)
    ghosts = choose(yard.ghosts, args.sort, None)
    if args.json:
        print(json.dumps([g.to_dict() for g in ghosts], indent=2, ensure_ascii=False))
        return 0
    ink = Ink()
    if not ghosts:
        print("No departed code was found.")
    for g in ghosts:
        lived = span(g.lifespan_days) if g.lifespan_days is not None else "before memory"
        haunt = ink(f"  ⚠ still called {g.calls_left}×", RED) if g.calls_left else ""
        print(
            f"{ink(g.label, GOLD)}  {ink(g.path, DIM)}  died {day(g.died.when)} ({g.died.short}) "
            f"by {g.died.author} · lived {lived}{haunt}"
        )
    return 0


def summon(args) -> int:
    yard = _yard(args)
    ghost = yard.find(args.name)
    if ghost is None and not args.tests:
        args.tests = True
        yard = _yard(args)
        ghost = yard.find(args.name)
    if ghost is None:
        print(f"No spirit named {args.name!r} answers.", file=sys.stderr)
        close = difflib.get_close_matches(args.name, sorted({g.name for g in yard.ghosts}), n=5, cutoff=0.5)
        if close:
            print("Perhaps you meant: " + ", ".join(close), file=sys.stderr)
        elif yard.ghosts:
            print("Run `git ofrenda list` to see who can be called.", file=sys.stderr)
        return 1
    ghost.memories = recall_memories(yard.root, ghost, limit=20)
    medium = Medium(args.model, args.host, enabled=not args.no_ai)
    return seance.hold(yard, ghost, medium, ask=args.ask)


def haunts(args) -> int:
    yard = _yard(args)
    ink = Ink()
    rows = [(g, h) for g in yard.ghosts for h in g.haunts]
    if not rows:
        print("No unfinished business. Every dead name has been laid to rest.")
        return 0
    rows.sort(key=lambda r: (not r[1].is_call, r[1].path, r[1].line))
    for g, h in rows:
        tag = ink("still called", RED) if h.is_call else ink("mentioned   ", TEAL)
        print(f"{tag}  {ink(h.where, GOLD)}  {h.text}")
        print(ink(f"              ↳ {g.label} died {day(g.died.when)} in {g.died.short}: {g.died.subject}", DIM))
    calls = sum(g.calls_left for g in yard.ghosts)
    mentions = sum(g.haunt_count for g in yard.ghosts) - calls
    print(f"\n{calls} call{'s' if calls != 1 else ''} to dead code, {mentions} mention{'s' if mentions != 1 else ''}.")
    return 1 if args.strict and calls else 0
