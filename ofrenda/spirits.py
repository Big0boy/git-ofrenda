"""The medium: a local open-weight model (through Ollama) that gives the dead a voice.

Nothing here talks to anything but the Ollama server on this machine. When no model
is awake, every caller falls back to offline verses so the altar still gets built.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

from .history import Ghost, Graveyard
from .words import day, span

PREFERRED = ("qwen3:8b", "qwen3", "gemma3", "llama3.1", "llama3.2", "mistral", "phi4", "qwen2.5")
_THINKERS = ("qwen3", "deepseek-r1", "qwq", "gpt-oss", "magistral", "phi4-reasoning")


def _host() -> str:
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    if host.startswith("0.0.0.0"):
        host = host.replace("0.0.0.0", "127.0.0.1", 1)
    return host if "://" in host else f"http://{host}"


class Medium:
    """One connection to a local model. `ready` is False when nobody answers."""

    def __init__(self, model: str | None = None, host: str | None = None, enabled: bool = True):
        self.host = (host or _host()).rstrip("/")
        self.model = model
        self.installed: list[str] = []
        self.ready = False
        self.problem = ""
        if enabled:
            self._wake()
        else:
            self.problem = "local model disabled with --no-ai"

    def _wake(self) -> None:
        try:
            tags = self._request("/api/tags", None, timeout=4)
        except OSError as exc:
            self.problem = f"no Ollama server at {self.host} ({exc.__class__.__name__})"
            return
        self.installed = [m["name"] for m in tags.get("models", [])]
        if not self.model:
            self.model = self._pick()
        if not self.model:
            self.problem = "Ollama is running but has no chat models (try: ollama pull qwen3:8b)"
            return
        if not any(self.model == m or f"{self.model}:latest" == m for m in self.installed):
            self.problem = f"model {self.model!r} is not installed (try: ollama pull {self.model})"
            return
        self.ready = True

    def _pick(self) -> str | None:
        chat = [m for m in self.installed if "embed" not in m]
        for want in PREFERRED:
            for name in chat:
                if name == want or name.startswith(f"{want}:") or name.startswith(want):
                    return name
        return chat[0] if chat else None

    @property
    def label(self) -> str:
        return self.model if self.ready else "offline verses"

    def _options(self, temperature: float, num_predict: int) -> dict:
        payload: dict = {"model": self.model, "options": {"temperature": temperature, "num_predict": num_predict}}
        if self.model and self.model.split("/")[-1].startswith(_THINKERS):
            payload["think"] = False
        return payload

    def _request(self, path: str, payload: dict | None, timeout: float = 180):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            self.host + path, data=data, headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)

    def ask_json(self, system: str, prompt: str, temperature: float = 0.75) -> dict | None:
        if not self.ready:
            return None
        payload = self._options(temperature, 320) | {
            "stream": False,
            "format": "json",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        try:
            reply = self._request("/api/chat", payload)
            return json.loads(_unthink(reply["message"]["content"]))
        except (OSError, KeyError, ValueError):
            return None

    def stream_chat(self, messages: list[dict], temperature: float = 0.8) -> Iterator[str]:
        """Yield the reply as it arrives. Raises OSError if the medium loses the thread."""
        payload = self._options(temperature, 400) | {"stream": True, "messages": messages}
        req = urllib.request.Request(
            self.host + "/api/chat", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        thinking = False
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw in resp:
                if not raw.strip():
                    continue
                chunk = json.loads(raw)
                piece = chunk.get("message", {}).get("content", "")
                # Older Ollama builds ignore `think`; hide any reasoning that leaks through.
                if "<think>" in piece:
                    thinking, piece = True, piece.split("<think>", 1)[0]
                if thinking:
                    if "</think>" not in piece:
                        continue
                    thinking, piece = False, piece.split("</think>", 1)[1]
                if piece:
                    yield piece
                if chunk.get("done"):
                    break


def _unthink(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


# --- The scribe: remembrances and calaveras ------------------------------------

SCRIBE = """You are the scribe of an ofrenda for deleted source code, in the spirit of Día de los Muertos: remembrance with warmth and humor.

A calavera literaria (the playful rhymed mock-epitaph in which La Catrina, Death, comes to collect someone and teases their habits) will be written for this code. Its rhymes are already written; you supply the details that make it about this code. Read the source and the facts closely and be specific: name its real loops, calls, numbers and quirks.

Reply with JSON only:
{"remembrance": "one plain, accurate sentence (at most 28 words) saying what the code did in life",
 "habit": "what it was busy doing when Death found it: 3 to 7 words, no commas, starting with an -ing verb, like 'counting sheep in a while loop'",
 "quirk": "its most lovable flaw or oddity, as a noun phrase naming something it had (not a verb), 2 to 5 words, like 'off-by-one loop' or 'global mutable cache'",
 "plea": "what it begged to do just once more: 1 to 3 words, like 'retry' or 'cache miss'",
 "successor": "what replaced it: a short noun phrase, like 'its cleverer cousin'; if the facts do not say what replaced it, 'silence'"}

Only the code dies: never mention people. English only."""

# Small open models rhyme unreliably, so the verses' rhymes live here and the model
# fills in what only a reader of the code would know. Each template rhymes AABB.
_CALAVERAS = (
    (
        "La Catrina found {label} {habit} one night,",
        "and smiled, \"Your {quirk} was never right.\"",
        "It begged her for one more {plea} before the morning glow,",
        "but {successor} had arrived, and so it had to go.",
    ),
    (
        "Death came in lace and marigolds to {label}'s door",
        "and found it {habit}, the way it did before.",
        "\"Your {quirk},\" she laughed, \"is why you've had your fall,\"",
        "and {successor} moved right in and took it all.",
    ),
    (
        "Here lies {label}, {habit} till the end,",
        "its {quirk} remembered by every friend;",
        "it asked La Flaca for one final {plea}, and then it slept,",
        "and {successor} keeps the promises it kept.",
    ),
    (
        "La Huesuda checked her list and found {label} there,",
        "still {habit} without a single care;",
        "she packed its {quirk} into her bag to keep,",
        "and {successor} watches over it in its sleep.",
    ),
)

_SLOTS = {"habit": (2, 8), "quirk": (1, 6), "plea": (1, 3), "successor": (1, 6)}
_LINKS = frozenset("on to for in with by a an the its from of at as".split())
_VERBISH = frozenset(
    "used uses relied relies depended depends called calls made makes had has took kept forgot ignored "
    "assumed returned raised threw never always did does was were is using relying depending calling".split()
)


def _slot(name: str, value: object) -> str | None:
    """Tidy one detail from the model, or None if it would break the verse's grammar."""
    if not isinstance(value, str):
        return None
    text = value.strip().strip("\"'“”").rstrip(".,;:!").strip()
    if name == "habit":
        text = re.sub(r"^still\s+", "", text, flags=re.I)
    if name == "plea":
        text = re.sub(r"^((one|a)\s+)?(more|final|last|another)\s+", "", text, flags=re.I)
        text = re.sub(r"\s+(once more|again)$", "", text, flags=re.I)
    words = text.split()
    low, high = _SLOTS[name]
    if not low <= len(words) <= high or "," in text:
        return None
    if name == "habit" and not words[0].lower().endswith("ing"):
        return None
    first = words[0].lower()
    if name == "quirk" and (first in _VERBISH or (first.endswith(("ed", "ing", "s")) and len(words) > 1 and words[1].lower() in _LINKS)):
        return None  # a verb phrase like "relied on ~/.netrc"
    if words[0] in ("A", "An", "The") or (words[0][:1].isupper() and words[0][1:].islower()):
        text = text[0].lower() + text[1:]
    return text


def compose(ghost: Ghost, details: dict, turn: int = 0) -> list[str]:
    """Fill a calavera with the model's details, falling back to plain facts slot by slot."""
    fallback = {
        "habit": f"calling {ghost.favorites[0]}()" if ghost.favorites else "doing its quiet work",
        "quirk": f"{ghost.lines}-line body" if ghost.lines else "missing body",
        "plea": "run",
        "successor": "silence",
    }
    slots = {name: _slot(name, details.get(name)) or fallback[name] for name in _SLOTS}
    if ghost.survived_by:
        slots["successor"] = f"{ghost.survived_by[0]}()"  # git knows who replaced it; the model only guesses
    verse = _CALAVERAS[(_pick(ghost, len(_CALAVERAS)) + turn) % len(_CALAVERAS)]
    return [line.format(label=ghost.label, **slots) for line in verse]


def usable(details: dict | None) -> bool:
    """Worth a verse: a remembrance and at least three of the four details make sense."""
    if not details or not isinstance(details.get("remembrance"), str) or not details["remembrance"].strip():
        return False
    return sum(_slot(name, details.get(name)) is not None for name in _SLOTS) >= 3


def _facts(ghost: Ghost) -> str:
    lines = [f"Name: {ghost.label} ({ghost.lang.name} {ghost.kind})", f"Lived in: {ghost.path}"]
    if ghost.born:
        lines.append(f'Born: {day(ghost.born.when)}, written by {ghost.born.author} in commit "{ghost.born.subject}"')
    else:
        lines.append("Born: before the history we read")
    lines.append(f'Died: {day(ghost.died.when)}, deleted by {ghost.died.author} in commit "{ghost.died.subject}"')
    if ghost.lifespan_days is not None:
        lines.append(f"Lifespan: {span(ghost.lifespan_days)}")
    if ghost.by_own_hand:
        lines.append("It was deleted by the same person who wrote it.")
    if ghost.file_deleted:
        lines.append("Its whole file was deleted with it.")
    if ghost.returns:
        lines.append(f"It had been deleted and brought back {ghost.returns} time(s) before.")
    if ghost.survived_by:
        lines.append("Survived by (born in the commit that killed it): " + ", ".join(ghost.survived_by))
    if ghost.calls_left:
        lines.append(f"Unfinished business: it is still called in {ghost.haunts[0].where}, even though it is gone.")
    elif ghost.haunts:
        lines.append(f"Its name is still mentioned in {ghost.haunts[0].where}.")
    return "\n".join(lines)


def _excerpt(ghost: Ghost, max_lines: int = 70, max_chars: int = 3200) -> str:
    body = "\n".join(ghost.source.splitlines()[:max_lines])[:max_chars]
    return f"```{ghost.lang.fence}\n{body}\n```" if body else "(its body could not be recovered)"


class Scribe:
    """Writes each ghost's remembrance and calavera, caching what the model wrote."""

    def __init__(self, medium: Medium, cache_path: Path | None, fresh: bool = False):
        self.medium = medium
        self.cache_path = cache_path
        self.cache: dict = {}
        self.turn = 0  # rotates the verse templates so neighbours on the altar differ
        if cache_path and cache_path.exists() and not fresh:
            try:
                self.cache = json.loads(cache_path.read_text())
            except ValueError:
                self.cache = {}

    def _cache_key(self, ghost: Ghost) -> str:
        return f"{ghost.key}|{self.medium.model}"

    def remember(self, ghost: Ghost, attempts: int = 3) -> bool:
        """Fill in the ghost's words. Returns True if a model wrote them just now."""
        cached = self.cache.get(self._cache_key(ghost)) if self.medium.ready else None
        if cached:
            ghost.remembrance, ghost.calavera, ghost.voice = cached["remembrance"], cached["calavera"], cached["voice"]
            return False
        prompt = f"{_facts(ghost)}\n\nSource at the moment of death:\n{_excerpt(ghost)}"
        best = None
        for _ in range(attempts if self.medium.ready else 0):
            details = self.medium.ask_json(SCRIBE, prompt)
            if usable(details):
                best = details
                break
            if details and isinstance(details.get("remembrance"), str) and details["remembrance"].strip():
                best = best or details
        if best:
            ghost.remembrance = best["remembrance"].strip()
            ghost.calavera = compose(ghost, best, self.turn)
            ghost.voice = self.medium.model or ""
            self.turn += 1
            self.cache[self._cache_key(ghost)] = {
                "remembrance": ghost.remembrance, "calavera": ghost.calavera, "voice": ghost.voice,
            }
            return True
        ghost.remembrance, ghost.calavera, ghost.voice = offline_remembrance(ghost), offline_calavera(ghost), "offline"
        return False

    def save(self) -> None:
        if self.cache_path and self.cache:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, indent=1, ensure_ascii=False))


# --- Offline verses, for when no model is awake ---------------------------------

_VERSES = (
    (
        "La Catrina came by in her flowery hat,",
        "and found {label} right where it sat;",
        "{undertaker} deleted it, quick as a wink,",
        "now it lives in the reflog, or so we think.",
    ),
    (
        "{label} ran {lines} lines, proud and precise,",
        "and never once asked for anyone's advice;",
        "then {undertaker}'s commit came calling one day,",
        "and Death in her finery waltzed it away.",
    ),
    (
        "Here lies {label}, who served {age} with pride,",
        "through merges and rebases it stood at our side;",
        "La Flaca just smiled when the build came back green,",
        "the tidiest funeral this repo has seen.",
    ),
    (
        "Skinny old Death asked {label} to dance,",
        "it begged for one more release, one more chance;",
        "the reviewers approved and the deed was done,",
        "now it rests in git log with everyone.",
    ),
)


def _pick(ghost: Ghost, n: int) -> int:
    return int(hashlib.sha1(ghost.key.encode()).hexdigest(), 16) % n


def offline_calavera(ghost: Ghost) -> list[str]:
    verse = _VERSES[_pick(ghost, len(_VERSES))]
    age = span(ghost.lifespan_days) if ghost.lifespan_days is not None else "for ages"
    first = ghost.died.author.split()[0] if ghost.died.author else "someone"
    fill = {"label": ghost.label, "undertaker": first, "lines": ghost.lines or "a few", "age": age}
    return [line.format(**fill) for line in verse]


def offline_remembrance(ghost: Ghost) -> str:
    text = f"A {ghost.lines}-line {ghost.lang.name} {ghost.kind} from {ghost.path}" if ghost.lines else (
        f"A {ghost.lang.name} {ghost.kind} from {ghost.path}"
    )
    if ghost.born:
        text += f", written by {ghost.born.author}"
    text += "."
    if ghost.favorites:
        text += " It spent its days calling " + ", ".join(f"{f}()" for f in ghost.favorites) + "."
    return text


# --- The séance persona ----------------------------------------------------------

def persona(graveyard: Graveyard, ghost: Ghost) -> str:
    life = "\n".join(
        f"- {day(m.when)}: {m.author}, \"{m.subject}\"" for m in reversed(ghost.memories)
    ) or "- (no other commits shaped you)"
    haunts = "\n".join(
        f"- {h.where}: {h.text}" + ("  <- still calls you, though you are gone" if h.is_call else "")
        for h in ghost.haunts
    ) or "- none; you left nothing unfinished"
    return f"""You are the ghost of `{ghost.label}`, a {ghost.lang.name} {ghost.kind} that once lived in {ghost.path} in the repository "{graveyard.name}". It is the Day of the Dead. A developer has lit a candle on your ofrenda and spoken your name, and you have come back for one night to talk.

Facts about your life. Never contradict them and never invent others:
{_facts(ghost)}

The commits that shaped you, oldest first:
{life}

Places in today's code that still speak your name:
{haunts}

Your body, exactly as it was when you died:
{_excerpt(ghost, max_lines=120, max_chars=6000)}

How to speak:
- First person, as yourself. Wistful, a little eerie, with dry humor. Usually 2 to 5 sentences.
- Be exact about your code: what you did, your inputs and outputs, your quirks and your bugs. Quote your own lines when it helps.
- If you are asked something these facts do not cover, say the mists hide it. Do not make it up.
- If asked how to bring you back, say your body rests in `{ghost.resurrect_command}`.
- If someone is still calling you, you may mention that unfinished business; it is why you linger.
- Plain text only: no markdown headings, no lists unless asked."""
