"""Walk a repository's history and find the code that no longer lives at HEAD."""

from __future__ import annotations

import re
import subprocess
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import gitio
from .langs import Lang, block_span, favorite_calls, lang_for

_REC, _UNIT = "\x1e", "\x1f"
LOG_FORMAT = f"{_REC}%H{_UNIT}%an{_UNIT}%ae{_UNIT}%aI{_UNIT}%s"

CALLABLE = frozenset({"function", "method"})

# First match wins, so the specific causes come before the generic "remove".
_CAUSES = (
    (r"\brevert", "Reverted, unmade as if it had never lived"),
    (r"\b(security|vuln|cve|exploit|xss|injection)", "Put down for the safety of others"),
    (
        r"\b(unused|dead code|no longer (used|needed)|obsolete|deprecat|nobody (\w+ )?(uses|used|calls|needs)|not used|orphan)",
        "Died of loneliness: no one called anymore",
    ),
    (r"\b(replac|migrat|switch(ed)? to|rewr[io]te|port(ed)? to|in favou?r of|supersed)", "Replaced by a younger function"),
    (r"\b(perf|optimi[sz]|speed|faster|too slow)", "Too slow for this world"),
    (r"\b(fix|bug|crash|outage|broke|hotfix|incident)", "Fell in the line of a bugfix"),
    (r"\b(refactor|clean ?up|tidy|simplif|restructur|reorgani[sz])", "Refactored out of existence"),
    (r"\b(died|dead|farewell|goodbye|retire|rip\b|sunset)", "Retired, and mourned"),
    (r"\b(remove|delete|drop|kill|purge|rip(ped)? out)", "Laid to rest on purpose"),
)


def cause_of_death(subject: str) -> str:
    text = subject.lower()
    for pattern, cause in _CAUSES:
        if re.search(pattern, text):
            return cause
    return "Passed quietly, without explanation"


@dataclass(frozen=True)
class Commit:
    sha: str
    author: str
    email: str
    when: datetime
    subject: str

    @classmethod
    def parse(cls, header: str) -> Commit:
        sha, author, email, iso, subject = header.split(_UNIT, 4)
        return cls(sha, author, email, datetime.fromisoformat(iso), subject)

    @property
    def short(self) -> str:
        return self.sha[:8]

    def to_dict(self) -> dict:
        return {
            "sha": self.sha,
            "author": self.author,
            "email": self.email,
            "date": self.when.isoformat(),
            "subject": self.subject,
        }


@dataclass
class Haunt:
    """A place in today's code that still speaks a dead name."""

    path: str
    line: int
    text: str
    is_call: bool

    @property
    def where(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class Ghost:
    name: str
    kind: str
    lang: Lang
    path: str
    born: Commit | None
    died: Commit
    homes: list[str]
    returns: int = 0
    file_deleted: bool = False
    source: str = ""
    signature: str = ""
    start_line: int = 0
    end_line: int = 0
    favorites: list[str] = field(default_factory=list)
    survived_by: list[str] = field(default_factory=list)
    haunts: list[Haunt] = field(default_factory=list)
    haunt_count: int = 0
    call_count: int = 0
    memories: list[Commit] = field(default_factory=list)
    # Filled in by the scribe (a local model, or the offline verses).
    remembrance: str = ""
    calavera: list[str] = field(default_factory=list)
    voice: str = ""

    @property
    def label(self) -> str:
        return f"{self.name}()" if self.kind in CALLABLE else self.name

    @property
    def key(self) -> str:
        return f"{self.lang.family}:{self.name}@{self.died.sha[:12]}"

    @property
    def lifespan_days(self) -> float | None:
        if not self.born:
            return None
        return max(0.0, (self.died.when - self.born.when).total_seconds() / 86400)

    @property
    def lines(self) -> int:
        return len(self.source.splitlines())

    @property
    def cause(self) -> str:
        return cause_of_death(self.died.subject)

    @property
    def by_own_hand(self) -> bool:
        return bool(self.born) and self.born.email.lower() == self.died.email.lower()

    @property
    def calls_left(self) -> int:
        return self.call_count

    @property
    def resurrect_command(self) -> str:
        cmd = f"git show {self.died.short}^:{self.path}"
        if self.start_line:
            cmd += f" | sed -n '{self.start_line},{self.end_line}p'"
        return cmd

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "language": self.lang.name,
            "path": self.path,
            "homes": self.homes,
            "born": self.born.to_dict() if self.born else None,
            "died": self.died.to_dict(),
            "lifespan_days": None if self.lifespan_days is None else round(self.lifespan_days, 2),
            "cause": self.cause,
            "returns": self.returns,
            "file_deleted": self.file_deleted,
            "signature": self.signature,
            "lines": [self.start_line, self.end_line],
            "source": self.source,
            "favorites": self.favorites,
            "survived_by": self.survived_by,
            "haunts": [{"where": h.where, "text": h.text, "call": h.is_call} for h in self.haunts],
            "haunt_count": self.haunt_count,
            "call_count": self.call_count,
            "memories": [m.to_dict() for m in self.memories],
            "remembrance": self.remembrance,
            "calavera": self.calavera,
            "voice": self.voice,
            "resurrect": self.resurrect_command,
        }


@dataclass
class Graveyard:
    root: Path
    rev: str
    commits: int
    ghosts: list[Ghost]

    @property
    def name(self) -> str:
        return self.root.name

    def find(self, name: str) -> Ghost | None:
        name = name.removesuffix("()")
        matches = [g for g in self.ghosts if g.name == name] or [
            g for g in self.ghosts if g.name.lower() == name.lower()
        ]
        return max(matches, key=lambda g: g.died.when, default=None)


@dataclass
class _FileChange:
    path: str
    lang: Lang
    deleted: bool
    added: dict[str, str] = field(default_factory=dict)
    removed: dict[str, str] = field(default_factory=dict)


@dataclass
class _Trace:
    name: str
    kind: str
    lang: Lang
    born: Commit | None = None
    died: Commit | None = None
    path: str = ""
    homes: list[str] = field(default_factory=list)
    returns: int = 0
    file_deleted: bool = False


def _diff_path(spec: str) -> str | None:
    spec = spec.rstrip("\t")
    if spec == "/dev/null":
        return None
    if spec.startswith('"') and spec.endswith('"'):
        spec = spec[1:-1]
    return spec[2:] if spec[:2] in ("a/", "b/") else spec


def _changes(repo: Path, rev: str, since: str | None):
    """Yield (commit, [file changes]) oldest first, reading definitions out of each diff."""
    args = [
        "log", "--reverse", "-p", "--unified=0", "--no-ext-diff", "--no-renames",
        "--src-prefix=a/", "--dst-prefix=b/", f"--format={LOG_FORMAT}",
    ]
    if since:
        args.append(f"--since={since}")
    args.append(rev)
    proc = subprocess.Popen(
        gitio.command(repo, *args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
    )
    commit: Commit | None = None
    files: list[_FileChange] = []
    current: _FileChange | None = None
    in_header, minus_path = False, None
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        if line.startswith(_REC):
            if commit:
                yield commit, files
            commit, files, current = Commit.parse(line[1:]), [], None
            continue
        if line.startswith("diff --git "):
            in_header, current, minus_path = True, None, None
            continue
        if in_header:
            if line.startswith("--- "):
                minus_path = _diff_path(line[4:])
            elif line.startswith("+++ "):
                plus = _diff_path(line[4:])
                path = plus or minus_path
                lang = lang_for(path)
                current = _FileChange(path, lang, deleted=plus is None) if path and lang else None
                if current:
                    files.append(current)
            elif line.startswith("@@"):
                in_header = False
            continue
        if current is None or line.startswith("@@"):
            continue
        sign = line[:1]
        if sign in ("+", "-"):
            hit = current.lang.match(line[1:])
            if hit:
                (current.added if sign == "+" else current.removed)[hit[1]] = hit[0]
    if commit:
        yield commit, files
    proc.wait()
    if proc.returncode != 0:
        err = proc.stderr.read().strip() if proc.stderr else ""
        raise gitio.GitError(err or "git log failed")


def _trace(repo: Path, rev: str, since: str | None):
    traces: dict[tuple[str, str], _Trace] = {}
    births: dict[str, list[tuple[str, str, str]]] = {}
    commits = 0
    for commit, files in _changes(repo, rev, since):
        commits += 1
        for fc in files:
            family = fc.lang.family
            for name, kind in fc.removed.items():
                if name in fc.added:
                    continue  # the signature changed; nobody died
                t = traces.setdefault((family, name), _Trace(name, kind, fc.lang))
                t.died, t.path, t.lang, t.kind, t.file_deleted = commit, fc.path, fc.lang, kind, fc.deleted
            for name, kind in fc.added.items():
                if name in fc.removed:
                    continue
                t = traces.setdefault((family, name), _Trace(name, kind, fc.lang))
                if t.born is None:
                    t.born = commit
                elif t.died is not None and t.died.sha != commit.sha:
                    t.returns += 1
                if fc.path not in t.homes:
                    t.homes.append(fc.path)
                births.setdefault(commit.sha, []).append((family, name, fc.path))
    return traces, births, commits


def _living(repo: Path, rev: str) -> set[tuple[str, str]]:
    """Every (family, name) still defined at `rev`."""
    paths = [p for p in gitio.ls_files(repo, rev) if lang_for(p)]
    blobs = gitio.cat_files(repo, [f"{rev}:{p}" for p in paths])
    alive: set[tuple[str, str]] = set()
    for path in paths:
        text = blobs.get(f"{rev}:{path}")
        if not text:
            continue
        lang = lang_for(path)
        assert lang is not None
        grouped = False
        for line in text.splitlines():
            hit = lang.match(line)
            if hit:
                alive.add((lang.family, hit[1]))
            if lang.family == "go":  # names declared inside a `type ( ... )` group
                if _GO_GROUP.match(line):
                    grouped = True
                elif grouped and line.startswith(")"):
                    grouped = False
                elif grouped and (m := _GO_MEMBER.match(line)):
                    alive.add(("go", m.group(1)))
    return alive


_GO_GROUP = re.compile(r"type\s*\(\s*$")
_GO_MEMBER = re.compile(r"\t([A-Za-z_]\w*)\s+[^\s=]")


_TEST_PATH = re.compile(r"(^|/)(tests?|spec|specs|__tests__|testing)/|(^|/)test_[^/]*$|[._-](test|spec)\.[^/]+$")


def _is_test(name: str, path: str) -> bool:
    return bool(re.match(r"_*[Tt]est", name) or _TEST_PATH.search(path))


def _exhume(repo: Path, ghosts: list[Ghost]) -> None:
    """Cut each ghost's body out of its file as it was just before it died."""
    specs = {g.key: f"{g.died.sha}^:{g.path}" for g in ghosts}
    blobs = gitio.cat_files(repo, list(specs.values()))
    for g in ghosts:
        text = blobs.get(specs[g.key])
        if not text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            hit = g.lang.match(line)
            if hit and hit[1] == g.name:
                first, last = block_span(lines, i, g.lang)
                g.source = textwrap.dedent("\n".join(lines[first : last + 1]))
                g.signature = line.strip()
                g.start_line, g.end_line = first + 1, last + 1
                g.favorites = favorite_calls(g.source, g.lang, g.name)
                break


def _absorb(ghosts: list[Ghost]) -> list[Ghost]:
    """A method that died along with its class rests inside the class's portrait."""
    graves: dict[tuple[str, str], list[Ghost]] = {}
    for g in ghosts:
        graves.setdefault((g.died.sha, g.path), []).append(g)
    keep = []
    for g in ghosts:
        inside = g.start_line and any(
            other is not g
            and other.start_line
            and other.start_line <= g.start_line
            and g.end_line <= other.end_line
            and other.end_line - other.start_line > g.end_line - g.start_line
            for other in graves[(g.died.sha, g.path)]
        )
        if not inside:
            keep.append(g)
    return keep


def _bereaved(ghosts: list[Ghost], births: dict, alive: set) -> None:
    """Who was born in the very commit that killed each ghost, and is still alive."""
    for g in ghosts:
        kin = [
            (name, path)
            for family, name, path in births.get(g.died.sha, [])
            if family == g.lang.family and name != g.name and (family, name) in alive
        ]
        kin.sort(key=lambda k: k[1] != g.path)
        labels = []
        for name, _ in kin:
            if name not in labels:
                labels.append(name)
        g.survived_by = labels[:3]


def _haunts(repo: Path, rev: str, ghosts: list[Ghost], keep: int = 6) -> None:
    """Find lines at `rev` that still mention a dead name: unfinished business."""
    by_name: dict[str, list[Ghost]] = {}
    for g in ghosts:
        if len(g.name) >= 4:
            by_name.setdefault(g.name, []).append(g)
    names = sorted(by_name)
    patterns = {n: re.compile(rf"(?<![\w$]){re.escape(n)}(?![\w$])") for n in names}
    for start in range(0, len(names), 80):
        chunk = names[start : start + 80]
        args = ["grep", "-I", "-n", "-z", "-w", "-F", "--full-name"]
        for n in chunk:
            args += ["-e", n]
        out = gitio.run(repo, *args, rev, "--", check=False)
        for record in out.split("\n"):
            parts = record.split("\0", 2)
            if len(parts) != 3:
                continue
            spec, lineno, text = parts
            path = spec.split(":", 1)[1] if ":" in spec else spec
            lang = lang_for(path)
            stripped = text.strip()
            commented = bool(lang) and stripped.startswith((*lang.comments, "*", "/*", "#["))
            for n in chunk:
                if not patterns[n].search(text):
                    continue
                code = bool(lang) and not commented
                bare = code and bool(re.search(rf"(?<![\w$.:>]){re.escape(n)}\s*\(", text))
                dotted = code and bool(re.search(rf"(?:\.|::|->){re.escape(n)}\s*\(", text))
                for g in by_name[n]:
                    if lang and lang.family != g.lang.family:
                        continue  # a namesake in another language, not this ghost
                    # `x.close()` says nothing about a dead method named close; it does about a module function
                    is_call = bare or (dotted and g.kind != "method")
                    g.haunts.append(Haunt(path, int(lineno), stripped[:200], is_call))
    for g in ghosts:
        g.haunt_count = len(g.haunts)
        g.call_count = sum(1 for h in g.haunts if h.is_call)
        g.haunts = sorted(g.haunts, key=lambda h: not h.is_call)[:keep]


def recall_memories(repo: Path, ghost: Ghost, limit: int = 8) -> list[Commit]:
    """Every commit that shaped the ghost's body, newest first (via `git log -L`)."""
    if not ghost.start_line:
        return []
    try:
        out = gitio.run(
            repo, "log", f"-L{ghost.start_line},{ghost.end_line}:{ghost.path}", "-s",
            f"--format={LOG_FORMAT}", f"{ghost.died.sha}^", timeout=20,
        )
    except (gitio.GitError, subprocess.TimeoutExpired):
        return []
    commits = [Commit.parse(chunk.split("\n", 1)[0]) for chunk in out.split(_REC) if chunk.strip()]
    return commits[:limit]


def find_ghosts(
    root: str | Path,
    rev: str = "HEAD",
    since: str | None = None,
    include_tests: bool = False,
) -> Graveyard:
    repo = gitio.toplevel(root)
    gitio.resolve(repo, rev)
    traces, births, commits = _trace(repo, rev, since)
    alive = _living(repo, rev)
    ghosts = []
    for (family, name), t in traces.items():
        if t.died is None or (family, name) in alive:
            continue
        if re.fullmatch(r"__\w+__", name) or (not include_tests and _is_test(name, t.path)):
            continue
        ghosts.append(
            Ghost(
                name=name, kind=t.kind, lang=t.lang, path=t.path, born=t.born, died=t.died,
                homes=t.homes or [t.path], returns=t.returns, file_deleted=t.file_deleted,
            )
        )
    ghosts.sort(key=lambda g: g.died.when, reverse=True)
    _exhume(repo, ghosts)
    ghosts = _absorb(ghosts)
    _bereaved(ghosts, births, alive)
    _haunts(repo, rev, ghosts)
    return Graveyard(repo, rev, commits, ghosts)


def choose(ghosts: list[Ghost], order: str = "recent", limit: int | None = 12) -> list[Ghost]:
    keys = {
        "recent": lambda g: g.died.when.timestamp(),
        "lifespan": lambda g: g.lifespan_days if g.lifespan_days is not None else float("inf"),
        "size": lambda g: g.lines,
        "haunting": lambda g: (g.calls_left, g.haunt_count),
    }
    ranked = sorted(ghosts, key=keys[order], reverse=True)
    return ranked if limit is None else ranked[:limit]
