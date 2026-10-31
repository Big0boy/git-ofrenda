"""How each language announces a definition, and where that definition ends.

Everything here is a heuristic over plain lines of text. It does not need to parse
a language perfectly; it needs to find where a function was born in a diff and to
cut its body back out of an old version of its file.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath

# Words that look like `name(` at the start of a line but never name a definition.
DEF_STOP = frozenset(
    """if elif else for foreach while do switch case catch try return sizeof typeof
    await yield with function func fn constructor""".split()
)

# Calls too ordinary to count as anyone's favourite thing.
_BORING = frozenset(
    """len str int float bool list dict set tuple range enumerate zip map filter sorted
    reversed min max abs round type repr isinstance hasattr getattr setattr format append
    extend pop get items keys values join split strip lstrip rstrip replace lower upper
    startswith endswith push slice toString String Number Boolean Array Object parseInt
    parseFloat require super not and or in is return lambda assert raise throw except
    elif""".split()
)


def _rules(*pairs: tuple[str, str]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple((kind, re.compile(pattern)) for kind, pattern in pairs)


@dataclass(frozen=True)
class Lang:
    name: str
    family: str  # definitions are compared within a family, so .ts and .js share one
    fence: str  # markdown code-fence label
    exts: tuple[str, ...]
    rules: tuple[tuple[str, re.Pattern[str]], ...]
    block: str = "brace"  # "indent", "brace" or "end"
    comments: tuple[str, ...] = ("//",)
    char_quotes: bool = False  # ' starts a char literal or a lifetime, not a string
    expression_bodies: bool = False  # `=> expr` / `= expr` bodies with no braces

    def match(self, line: str) -> tuple[str, str] | None:
        """Return (kind, name) if this line opens a definition."""
        if len(line) > 400:
            return None
        for kind, pattern in self.rules:
            m = pattern.match(line)
            if m and m.group("name") not in DEF_STOP:
                return kind, m.group("name")
        return None


_JS_RULES = (
    ("function", r"\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(?P<name>[A-Za-z_$][\w$]*)\s*[<(]"),
    (
        "function",
        r"\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?"
        r"(?:function\b|(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::[^=]+)?=>)",
    ),
    ("class", r"\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)"),
    (
        "method",
        r"\s+(?:(?:public|private|protected|static|async|override|readonly|get|set)\s+)*"
        r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^()'\"`]*\)\s*(?::\s*[^{=;]+)?\{\s*$",
    ),
)

_MODS = "public|private|protected|internal|static|final|abstract|synchronized|native|override|virtual|async|sealed|extern|unsafe|partial|default|open"

LANGS: tuple[Lang, ...] = (
    Lang(
        "Python", "python", "python", (".py", ".pyw"),
        _rules(
            ("function", r"(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\s*[\[(]"),
            ("method", r"\s+(?:async\s+)?def\s+(?P<name>[A-Za-z_]\w*)\s*[\[(]"),
            ("class", r"\s*class\s+(?P<name>[A-Za-z_]\w*)\s*[\[(:]"),
        ),
        block="indent", comments=("#",),
    ),
    Lang("JavaScript", "js", "js", (".js", ".jsx", ".mjs", ".cjs"), _rules(*_JS_RULES), expression_bodies=True),
    Lang(
        "TypeScript", "js", "ts", (".ts", ".tsx", ".mts", ".cts"),
        _rules(*_JS_RULES, ("type", r"\s*(?:export\s+)?(?:declare\s+)?interface\s+(?P<name>[A-Za-z_$][\w$]*)")),
        expression_bodies=True,
    ),
    Lang(
        "Go", "go", "go", (".go",),
        _rules(
            ("function", r"func\s+(?P<name>[A-Za-z_]\w*)\s*[\[(]"),
            ("method", r"func\s+\([^)]*\)\s*(?P<name>[A-Za-z_]\w*)\s*[\[(]"),
            ("type", r"type\s+(?P<name>[A-Za-z_]\w*)(?:\[[^\]]*\])?\s+[^\s(]"),
            ("type", r"\t(?P<name>[A-Za-z_]\w*)\s+(?:struct|interface)\s*\{"),  # inside a `type ( ... )` group
        ),
        char_quotes=True,
    ),
    Lang(
        "Rust", "rust", "rust", (".rs",),
        _rules(
            *(
                (
                    kind,
                    indent + r"(?:pub(?:\([^)]*\))?\s+)?(?:default\s+)?(?:const\s+)?(?:async\s+)?(?:unsafe\s+)?"
                    r"(?:extern\s+\"[^\"]*\"\s+)?fn\s+(?P<name>[A-Za-z_]\w*)",
                )
                for kind, indent in (("function", ""), ("method", r"\s+"))
            ),
            ("type", r"\s*(?:pub(?:\([^)]*\))?\s+)?(?:struct|enum|trait|union)\s+(?P<name>[A-Za-z_]\w*)"),
        ),
        char_quotes=True,
    ),
    Lang(
        "Ruby", "ruby", "ruby", (".rb", ".rake"),
        _rules(
            ("method", r"\s*def\s+(?:self\.)?(?P<name>[A-Za-z_]\w*[?!]?)"),
            ("class", r"\s*(?:class|module)\s+(?P<name>[A-Z]\w*)"),
        ),
        block="end", comments=("#",),
    ),
    Lang(
        "Lua", "lua", "lua", (".lua",),
        _rules(("function", r"\s*(?:local\s+)?function\s+(?P<name>[A-Za-z_][\w.:]*)\s*\(")),
        block="end", comments=("--",),
    ),
    Lang(
        "Shell", "shell", "bash", (".sh", ".bash", ".zsh"),
        _rules(
            ("function", r"\s*function\s+(?P<name>[A-Za-z_][\w:-]*)\s*(?:\(\))?\s*(?:\{.*)?$"),
            ("function", r"\s*(?P<name>[A-Za-z_][\w:-]*)\s*\(\)\s*(?:\{.*)?$"),
        ),
        comments=("#",),
    ),
    Lang(
        "PHP", "php", "php", (".php",),
        _rules(
            ("function", r"\s*(?:(?:public|private|protected|static|abstract|final)\s+)*function\s+&?(?P<name>[A-Za-z_]\w*)\s*\("),
            ("class", r"\s*(?:(?:abstract|final|readonly)\s+)*(?:class|interface|trait|enum)\s+(?P<name>[A-Za-z_]\w*)"),
        ),
        comments=("//", "#"),
    ),
    *(
        Lang(
            name, family, family, exts,
            _rules(
                (
                    "method",
                    rf"\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:{_MODS})\s+)+(?:<[^>]+>\s+)?[\w<>\[\],.?]+"
                    rf"(?:\s*<[^>]*>)?(?:\[\])*\s+(?P<name>[A-Za-z_]\w*)\s*\([^;]*$",
                ),
                ("class", rf"\s*(?:@\w+\s+)*(?:(?:{_MODS})\s+)*(?:class|interface|enum|record|struct)\s+(?P<name>[A-Za-z_]\w*)"),
            ),
            char_quotes=True,
        )
        for name, family, exts in (("Java", "java", (".java",)), ("C#", "csharp", (".cs",)))
    ),
    Lang(
        "Kotlin", "kotlin", "kotlin", (".kt", ".kts"),
        _rules(
            ("function", r"\s*(?:@\w+\s+)*(?:[a-z]+\s+)*fun\s+(?:<[^>]+>\s*)?(?:[\w.]+\.)?(?P<name>[A-Za-z_]\w*)\s*\("),
            ("class", r"\s*(?:@\w+\s+)*(?:[a-z]+\s+)*(?:class|interface|object)\s+(?P<name>[A-Za-z_]\w*)"),
        ),
        char_quotes=True, expression_bodies=True,
    ),
    Lang(
        "Swift", "swift", "swift", (".swift",),
        _rules(
            ("function", r"\s*(?:@\w+\s+)*(?:[a-z]+\s+)*func\s+(?P<name>[A-Za-z_]\w*)"),
            ("class", r"\s*(?:@\w+\s+)*(?:[a-z]+\s+)*(?:class|struct|enum|protocol|actor)\s+(?P<name>[A-Za-z_]\w*)"),
        ),
        char_quotes=True,
    ),
    Lang(
        "C", "c", "c", (".c", ".h"),
        _rules(
            ("function", r"(?!(?:return|else|typedef|extern)\b)[A-Za-z_][\w\s*]*?[\s*]+(?P<name>[A-Za-z_]\w*)\s*\([^;]*$"),
            ("type", r"(?:typedef\s+)?(?:struct|union|enum)\s+(?P<name>[A-Za-z_]\w*)\s*\{"),
        ),
        char_quotes=True,
    ),
    Lang(
        "C++", "cpp", "cpp", (".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"),
        _rules(
            (
                "function",
                r"(?!(?:return|else|typedef|extern|using|namespace)\b)[A-Za-z_][\w\s*&:<>,~]*?[\s*&]+"
                r"(?P<name>~?[A-Za-z_]\w*(?:::~?[A-Za-z_]\w*)*)\s*\([^;]*$",
            ),
            ("class", r"(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+(?P<name>[A-Za-z_]\w*)\b[^;]*$"),
        ),
        char_quotes=True,
    ),
)

_BY_EXT = {ext: lang for lang in LANGS for ext in lang.exts}


def lang_for(path: str | None) -> Lang | None:
    if not path:
        return None
    return _BY_EXT.get(PurePosixPath(path).suffix.lower())


def indent_of(line: str) -> int:
    expanded = line.expandtabs(4)
    return len(expanded) - len(expanded.lstrip())


_CHAR_LITERAL = re.compile(r"'(?:\\.[^'\n]{0,8}|[^'\\\n])'")


def strip_code(line: str, lang: Lang, state: str | None = None) -> tuple[str, str | None]:
    """Blank out strings and comments so braces and colons can be counted.

    `state` carries a construct that spans lines: a block comment, a triple-quoted
    string or a template literal. Returns the cleaned line and the state after it.
    """
    out: list[str] = []
    i, n = 0, len(line)
    while i < n:
        if state == "/*":
            end = line.find("*/", i)
            if end < 0:
                return "".join(out), state
            state, i = None, end + 2
            continue
        if state:
            if line[i] == "\\":
                i += 2
            elif line.startswith(state, i):
                i += len(state)
                state = None
            else:
                i += 1
            continue
        ch = line[i]
        comment = next((c for c in lang.comments if line.startswith(c, i)), None)
        if comment and (comment != "#" or lang.family != "shell" or i == 0 or line[i - 1].isspace()):
            break
        if "//" in lang.comments and line.startswith("/*", i):
            state, i = "/*", i + 2
            continue
        if ch in "\"'`":
            if lang.block == "indent" and line.startswith(ch * 3, i):
                state, i = ch * 3, i + 3
                continue
            if ch == "`" and lang.family in ("js", "go"):
                state, i = "`", i + 1
                continue
            if ch == "'" and lang.char_quotes:
                m = _CHAR_LITERAL.match(line, i)
                i = m.end() if m else i + 1
                continue
            j = i + 1
            while j < n and line[j] != ch:
                j += 2 if line[j] == "\\" else 1
            out.append('""')
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out), state


def block_span(lines: list[str], start: int, lang: Lang, limit: int = 300) -> tuple[int, int]:
    """First and last line (0-based, inclusive) of the definition opening at `start`,
    including the decorators and comments resting directly on top of it."""
    if lang.block == "indent":
        end = _indent_end(lines, start, lang, limit)
    elif lang.block == "end":
        end = _end_end(lines, start, lang, limit)
    else:
        end = _brace_end(lines, start, lang, limit)
    return _preamble_start(lines, start, lang), end


def _preamble_start(lines: list[str], start: int, lang: Lang) -> int:
    base = indent_of(lines[start])
    markers = ("@", "/*", "*", "*/", *lang.comments)
    i = start
    while i > 0 and start - i < 20:
        prev = lines[i - 1]
        s = prev.strip()
        if not s or not s.startswith(markers) or s.startswith("#!"):
            break
        if indent_of(prev) != base and not s.startswith("*"):
            break
        i -= 1
    return i


def _indent_end(lines: list[str], start: int, lang: Lang, limit: int) -> int:
    base = indent_of(lines[start])
    depth, state, i = 0, None, start
    # Walk the (possibly multi-line) signature to the colon that opens the body.
    while True:
        if i >= len(lines) or i - start > 40:
            return start
        code, state = strip_code(lines[i], lang, state)
        depth += sum(code.count(c) for c in "([{") - sum(code.count(c) for c in ")]}")
        if depth <= 0 and state is None:
            tail = code.rstrip()
            if tail.endswith(":"):
                break
            if ":" in tail:
                return i  # a one-line body, like `def f(): return 1`
        i += 1
    end, state = i, None
    for j in range(i + 1, min(len(lines), start + limit)):
        line = lines[j]
        if state is None:
            if not line.strip():
                continue
            if indent_of(line) <= base:
                break
        _, state = strip_code(line, lang, state)
        end = j
    return end


_CONTINUES = ("=>", "=", "(", ",", "+", "-", "*", "/", "&&", "||", "?", ":", "\\", "|", "&", ".", "[")


def _brace_end(lines: list[str], start: int, lang: Lang, limit: int) -> int:
    depth = parens = 0
    opened, state, expression = False, None, False
    for i in range(start, min(len(lines), start + limit)):
        code, state = strip_code(lines[i], lang, state)
        if i == start and lang.expression_bodies:
            expression = "=>" in code or bool(re.search(r"\)[^{]*[^=!<>]=[^=>]", code))
        for ch in code:
            if ch in "([":
                parens += 1
            elif ch in ")]":
                parens -= 1
            elif ch == "{":
                depth += 1
                opened = True
            elif ch == "}":
                depth -= 1
                if opened and depth <= 0:
                    return i
            elif ch == ";" and not opened and parens <= 0:
                return i
        if not opened:
            tail = code.rstrip()
            if expression and parens <= 0 and tail and not tail.endswith(_CONTINUES):
                return i
            if lang.family == "go" and i == start and parens <= 0:
                return start  # gofmt keeps the brace on the definition line, so `type ID int` is whole
            if i - start >= 8:
                return start
    return min(len(lines), start + limit) - 1


_END = re.compile(r"\s*end\b")


def _end_end(lines: list[str], start: int, lang: Lang, limit: int) -> int:
    code, _ = strip_code(lines[start], lang)
    if re.search(r"\bend\s*$", code) or re.match(r"\s*def\s+[\w.?!]+\s*(?:\([^)]*\))?\s*=", code):
        return start
    base = indent_of(lines[start])
    for i in range(start + 1, min(len(lines), start + limit)):
        line = lines[i]
        if not line.strip():
            continue
        if indent_of(line) == base and _END.match(line):
            return i
        if indent_of(line) < base:
            return i - 1
    return start


_CALL = re.compile(r"(?<![\w$.])((?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*)\s*\(")


def favorite_calls(source: str, lang: Lang, own_name: str, top: int = 3) -> list[str]:
    """The calls a definition made most often: the company it kept."""
    counts: Counter[str] = Counter()
    state = None
    for line in source.splitlines():
        code, state = strip_code(line, lang, state)
        if lang.match(line):
            continue
        for m in _CALL.finditer(code):
            name = re.sub(r"^(?:self|this|cls)\.", "", m.group(1))
            last = name.rsplit(".", 1)[-1]
            if last in _BORING or last in DEF_STOP or name == own_name:
                continue
            counts[name] += 1
    return [name for name, _ in counts.most_common(top)]
