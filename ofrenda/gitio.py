"""Thin, dependable wrappers around the git CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path

# Pin the settings that change git's output format, so a user's config can't break parsing.
_PINNED = ("-c", "core.quotepath=false", "-c", "log.showSignature=false", "-c", "color.ui=never")


class GitError(RuntimeError):
    pass


def command(repo: str | Path, *args: str) -> list[str]:
    return ["git", "-C", str(repo), *_PINNED, *args]


def run(repo: str | Path, *args: str, check: bool = True, timeout: float | None = None) -> str:
    try:
        proc = subprocess.run(
            command(repo, *args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {args[0]} failed")
    return proc.stdout


def toplevel(path: str | Path) -> Path:
    try:
        return Path(run(path, "rev-parse", "--show-toplevel").strip())
    except GitError as exc:
        raise GitError(f"{path} is not inside a git repository") from exc


def git_dir(repo: str | Path) -> Path:
    return Path(run(repo, "rev-parse", "--absolute-git-dir").strip())


def resolve(repo: str | Path, rev: str) -> str:
    try:
        return run(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").strip()
    except GitError as exc:
        raise GitError(f"{rev!r} is not a commit (does the repository have any commits yet?)") from exc


def ls_files(repo: str | Path, rev: str) -> list[str]:
    out = run(repo, "ls-tree", "-r", "-z", "--name-only", rev)
    return [p for p in out.split("\0") if p]


def cat_files(repo: str | Path, specs: list[str]) -> dict[str, str | None]:
    """Read many `rev:path` blobs through one `git cat-file --batch` process.

    Missing objects, trees and binary blobs come back as None.
    """
    specs = list(dict.fromkeys(specs))
    if not specs:
        return {}
    payload = "".join(f"{s}\n" for s in specs).encode()
    proc = subprocess.run(command(repo, "cat-file", "--batch"), input=payload, capture_output=True)
    if proc.returncode != 0:
        raise GitError(proc.stderr.decode(errors="replace").strip() or "git cat-file failed")
    out, pos, found = proc.stdout, 0, {}
    for spec in specs:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].split()
        pos = nl + 1
        if len(header) != 3 or header[2] == b"missing" or not header[2].isdigit():
            found[spec] = None
            continue
        size = int(header[2])
        data = out[pos : pos + size]
        pos += size + 1
        if header[1] != b"blob" or b"\0" in data[:8000]:
            found[spec] = None
        else:
            found[spec] = data.decode("utf-8", errors="replace")
    return found
