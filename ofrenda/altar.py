"""Render the ofrenda: one self-contained HTML file that works with the internet off."""

from __future__ import annotations

import hashlib
import html
import random
from datetime import datetime

from .history import Ghost, Graveyard
from .skulls import marigold, portrait
from .words import day, span, year

CROWNED = frozenset({"class", "type"})
CARD, GAP = 300, 26  # portrait width and gutter, in px; the CSS below uses the same numbers

# (title, subtitle, test on lifespan in days, cloth colour). None means born before the history we read.
TIERS = (
    ("Los Ancestros", "they lived more than a year", lambda d: d is None or d >= 365, "#a3135a"),
    ("Una temporada", "they lived a season", lambda d: d is not None and 30 <= d < 365, "#53279a"),
    ("Velas breves", "brief candles, gone within a month", lambda d: d is not None and d < 30, "#127a75"),
)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def code_name(value: object) -> str:
    """Escape an identifier and let it wrap after underscores, dots and slashes."""
    out = esc(value)
    for mark in ("_", ".", "/"):
        out = out.replace(mark, f"{mark}<wbr>")
    return out


def _rnd(seed: str) -> random.Random:
    return random.Random(hashlib.sha256(seed.encode()).digest())


def _stars(rnd: random.Random, n: int = 110) -> str:
    return ", ".join(
        f"{rnd.uniform(0, 100):.1f}vw {rnd.uniform(0, 100):.1f}vh 0 {rnd.choice((0, 0, 0, 0.5))}px "
        f"rgba(255, {rnd.randint(225, 255)}, {rnd.randint(200, 255)}, {rnd.uniform(0.35, 0.95):.2f})"
        for _ in range(n)
    )


_FLAG_COLORS = ("#e6197e", "#ff8c1a", "#1fb5ac", "#8a4fff", "#ffc93c", "#8cc63f", "#3fa9f5")


def _flag_motif(kind: int) -> str:
    """Cut-outs for one papel picado flag, drawn into its mask (black is cut away)."""
    if kind == 0:  # skull
        return (
            '<circle cx="50" cy="52" r="20" fill="#000"/><rect x="38" y="60" width="24" height="17" rx="5" fill="#000"/>'
            '<circle cx="42.5" cy="52" r="5.5" fill="#fff"/><circle cx="57.5" cy="52" r="5.5" fill="#fff"/>'
            '<path d="M50 58 l-3 5 h6 z" fill="#fff"/>'
            '<rect x="42" y="68" width="2.4" height="7" fill="#fff"/><rect x="48.8" y="68" width="2.4" height="7" fill="#fff"/>'
            '<rect x="55.6" y="68" width="2.4" height="7" fill="#fff"/>'
        )
    if kind == 1:  # flower
        petals = "".join(
            f'<ellipse cx="50" cy="40" rx="6" ry="11" fill="#000" transform="rotate({k * 45} 50 55)"/>' for k in range(8)
        )
        return petals + '<circle cx="50" cy="55" r="7" fill="#fff"/><circle cx="50" cy="55" r="3" fill="#000"/>'
    if kind == 2:  # heart and rays
        rays = "".join(
            f'<rect x="49" y="26" width="2" height="8" fill="#000" transform="rotate({k * 30} 50 55)"/>' for k in range(12)
        )
        return rays + '<path d="M50 70 C30 56 34 42 43 43 C47 43 50 47 50 49 C50 47 53 43 57 43 C66 42 70 56 50 70 Z" fill="#000"/>'
    if kind == 3:  # diamond lattice
        cells = "".join(
            f'<path d="M{x} {y - 8} l7 8 l-7 8 l-7 -8 z" fill="#000"/>'
            for x in (32, 50, 68)
            for y in (40, 58, 76)
            if (x, y) != (50, 58)
        )
        return cells + '<circle cx="50" cy="58" r="6" fill="#000"/>'
    rays = "".join(  # marigold sun
        f'<path d="M48 32 L50 22 L52 32 Z" fill="#000" transform="rotate({k * 22.5} 50 55)"/>' for k in range(16)
    )
    return rays + '<circle cx="50" cy="55" r="13" fill="#000"/><circle cx="50" cy="55" r="6" fill="#fff"/>'


def _papel_picado(count: int = 16) -> str:
    teeth = " ".join(f"L{x - 5} 116 L{x - 10} 106" for x in range(100, 0, -10))
    shape = f"M0 6 H100 V106 {teeth} Z"
    flags = []
    for i in range(count):
        holes = "".join(f'<circle cx="{x}" cy="15" r="2.2" fill="#000"/>' for x in range(12, 90, 11))
        holes += "".join(f'<path d="M{x} 92 l4 6 l-4 6 l-4 -6 z" fill="#000"/>' for x in range(14, 90, 12))
        mask = f'<mask id="pp{i}"><rect width="100" height="120" fill="#fff"/>{holes}{_flag_motif(i % 5)}</mask>'
        color = _FLAG_COLORS[i % len(_FLAG_COLORS)]
        flags.append(
            f'<svg class="flag" viewBox="0 0 100 120" style="--t:{3.2 + (i * 7 % 5) * 0.45:.2f}s;--d:-{i * 0.37:.2f}s" aria-hidden="true">'
            f'<defs>{mask}</defs><path d="{shape}" fill="{color}" mask="url(#pp{i})"/>'
            f'<rect x="0" y="0" width="100" height="7" fill="{color}" opacity=".7"/></svg>'
        )
    return f'<div class="banner">{"".join(flags)}</div>'


def _ledge(seed: str, count: int) -> str:
    rnd = _rnd(seed)
    items = []
    for i in range(count):
        if i % 3 == 1:
            items.append(f'<svg class="bloom" viewBox="-12 -12 24 24" aria-hidden="true">{marigold(0, 0, 1.15)}</svg>')
        else:
            drip = " drip" if rnd.random() < 0.4 else ""
            items.append(
                f'<span class="candle{drip}" style="--h:{rnd.randint(34, 64)}px;--f:{rnd.uniform(1.1, 2.2):.2f}s" aria-hidden="true"><i></i></span>'
            )
    return f'<div class="ledge">{"".join(items)}</div>'


def _dates(g: Ghost) -> str:
    born = f"<time>{esc(day(g.born.when))}</time>" if g.born else "<time>before memory</time>"
    return f'{born} <span aria-hidden="true">&ndash;</span> <time>{esc(day(g.died.when))}</time>'


def _card(g: Ghost) -> str:
    age = f"lived {span(g.lifespan_days)}" if g.lifespan_days is not None else "older than the history we read"
    if g.returns:
        age += f" &middot; came back {g.returns}&times;"
    verse = "".join(f"<p>{esc(line)}</p>" for line in g.calavera)
    voice = "offline verse" if g.voice == "offline" else f"calavera by {g.voice}"
    facts = []
    if g.born:
        facts.append(("Written by", esc(g.born.author)))
    killer = esc(g.died.author) + (" (its own author)" if g.by_own_hand else "")
    facts.append(("Laid to rest by", f'{killer}<br><q>{esc(g.died.subject)}</q> <code>{esc(g.died.short)}</code>'))
    cause = esc(g.cause) + ("; its whole file went with it" if g.file_deleted else "")
    facts.append(("Cause", cause))
    if g.survived_by:
        facts.append(("Survived by", ", ".join(f"<code>{code_name(n)}</code>" for n in g.survived_by)))
    if g.favorites:
        facts.append(("Loved", ", ".join(f"<code>{code_name(f)}()</code>" for f in g.favorites)))
    if len(g.homes) > 1:
        facts.append(("Lived in", ", ".join(f"<code>{code_name(h)}</code>" for h in g.homes)))
    facts_html = "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in facts)

    haunt = ""
    if g.calls_left:
        first = next(h for h in g.haunts if h.is_call)
        more = f" and {g.calls_left - 1} more" if g.calls_left > 1 else ""
        haunt = f'<p class="haunt call"><b>Unfinished business:</b> still called at <code>{esc(first.where)}</code>{more}.</p>'
    elif g.haunts:
        haunt = (
            f'<p class="haunt"><b>Still spoken of</b> in <code>{esc(g.haunts[0].where)}</code>'
            + (f" and {g.haunt_count - 1} more place{'s' if g.haunt_count > 2 else ''}" if g.haunt_count > 1 else "")
            + ".</p>"
        )

    life = ""
    if g.memories:
        rows = "".join(
            f"<li><time>{esc(day(m.when))}</time> &middot; {esc(m.author)}<br><q>{esc(m.subject)}</q></li>"
            for m in g.memories
        )
        life = f'<p class="sub">Its life, in commits</p><ol class="life">{rows}</ol>'
    body = (
        f'<pre><code>{esc(g.source)}</code></pre>'
        if g.source
        else '<p class="sub">Its body could not be recovered.</p>'
    )
    summon = f"git ofrenda summon {g.name}"
    size = ' class="long"' if len(g.label) > 26 else ""
    return f"""<article class="retrato" id="{esc(g.key)}">
  {portrait(g.key, crowned=g.kind in CROWNED, title=esc(f"Sugar skull portrait of {g.label}"))}
  <h3{size}>{code_name(g.label)}</h3>
  <p class="kind">{esc(g.lang.name)} {esc(g.kind)} &middot; {esc(g.path)}</p>
  <p class="dates">{_dates(g)}</p>
  <p class="age">{age}</p>
  <p class="remembrance">{esc(g.remembrance)}</p>
  <blockquote class="calavera">{verse}<cite>{esc(voice)}</cite></blockquote>
  <dl class="facts">{facts_html}</dl>
  {haunt}
  <details>
    <summary>Last words &middot; {g.lines} line{'s' if g.lines != 1 else ''}</summary>
    {body}
    {life}
    <p class="raise">Bring it back<code>{esc(g.resurrect_command)}</code></p>
  </details>
  <button class="summon" type="button" data-summon="{esc(summon)}" data-label="Summon this spirit">Summon this spirit</button>
</article>"""


_OFFERINGS = (
    (
        "Agua", "for the long journey home",
        '<svg viewBox="0 0 60 80"><path d="M12 8 L48 8 L44 74 Q30 78 16 74 Z" fill="rgba(180,220,255,.14)" stroke="#cfe6ff" stroke-width="2"/>'
        '<path d="M14.6 30 L45.4 30 L43.6 72 Q30 75.6 16.4 72 Z" fill="rgba(80,170,255,.38)"/>'
        '<ellipse cx="30" cy="30" rx="15.4" ry="2.4" fill="rgba(170,215,255,.7)"/>'
        '<path d="M19 14 L18 62" stroke="#fff" stroke-opacity=".45" stroke-width="2" stroke-linecap="round"/></svg>',
    ),
    (
        "Sal", "to keep the spirit whole",
        '<svg viewBox="0 0 80 60"><path d="M8 34 Q10 54 40 54 Q70 54 72 34 Z" fill="#7e3bd0" stroke="#2a1745" stroke-width="1.5"/>'
        '<path d="M15 34 Q40 6 65 34 Z" fill="#fbf7f0"/>'
        '<ellipse cx="40" cy="34" rx="32" ry="5.5" fill="none" stroke="#c9a7ff" stroke-width="2"/>'
        '<circle cx="33" cy="24" r="1" fill="#d9d2c4"/><circle cx="45" cy="20" r="1" fill="#d9d2c4"/><circle cx="50" cy="28" r="1" fill="#d9d2c4"/></svg>',
    ),
    (
        "Pan de muerto", "sweet bread with its little bones",
        '<svg viewBox="0 0 100 70"><ellipse cx="50" cy="60" rx="43" ry="7" fill="#6e3a12"/>'
        '<path d="M8 59 Q8 22 50 20 Q92 22 92 59 Z" fill="url(#bread)"/>'
        '<path d="M20 50 Q44 18 72 30" fill="none" stroke="#a65a1d" stroke-width="7" stroke-linecap="round" stroke-dasharray="7 3"/>'
        '<path d="M80 50 Q56 18 28 30" fill="none" stroke="#a65a1d" stroke-width="7" stroke-linecap="round" stroke-dasharray="7 3"/>'
        '<circle cx="50" cy="20" r="7" fill="#b8692a"/>'
        + "".join(
            f'<circle cx="{x}" cy="{y}" r="1.1" fill="#fff6dd" opacity=".85"/>'
            for x, y in ((24, 44), (34, 34), (42, 42), (58, 40), (66, 33), (74, 46), (30, 52), (62, 52), (50, 31), (82, 54), (17, 54))
        )
        + "</svg>",
    ),
    (
        "Café de olla", "they always worked late",
        '<svg viewBox="0 0 80 70"><path d="M58 32 q16 0 14 12 q-2 10 -16 8" fill="none" stroke="#9c4518" stroke-width="5"/>'
        '<path d="M14 24 H60 V46 Q60 62 37 62 Q14 62 14 46 Z" fill="#b5521f" stroke="#7a3412" stroke-width="1.5"/>'
        '<ellipse cx="37" cy="24" rx="23" ry="5" fill="#3b2216" stroke="#7a3412" stroke-width="1.5"/>'
        '<path d="M18 38 Q37 46 56 38" fill="none" stroke="#f3c08a" stroke-width="2" stroke-dasharray="3 4"/>'
        '<g class="smoke"><path d="M30 16 q-5 -6 0 -10 q5 -4 0 -10" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M42 16 q5 -6 0 -10 q-5 -4 0 -10" fill="none" stroke="#fff" stroke-opacity=".25" stroke-width="2" stroke-linecap="round"/></g></svg>',
    ),
    (
        "Copal", "its smoke guides them to the altar",
        '<svg viewBox="0 0 80 90"><g class="smoke"><path d="M40 44 q-8 -10 0 -18 q8 -8 0 -18 q-6 -6 0 -10" fill="none" stroke="#e8e0f5" stroke-opacity=".4" stroke-width="3" stroke-linecap="round"/>'
        '<path d="M46 44 q8 -8 2 -16 q-6 -8 3 -15" fill="none" stroke="#e8e0f5" stroke-opacity=".25" stroke-width="2.5" stroke-linecap="round"/></g>'
        '<path d="M12 48 Q40 76 68 48 Z" fill="#8d3b14" stroke="#5a230a" stroke-width="1.5"/>'
        '<ellipse cx="40" cy="48" rx="28" ry="5" fill="#3a1606"/>'
        '<circle cx="34" cy="47" r="2.6" fill="#ff8c1a"/><circle cx="42" cy="46" r="2.2" fill="#ffc93c"/><circle cx="47" cy="48" r="2" fill="#ff5a1f"/>'
        '<rect x="35" y="62" width="10" height="14" fill="#8d3b14"/><ellipse cx="40" cy="78" rx="16" ry="4.5" fill="#6e2c0e"/></svg>',
    ),
    (
        "Cempasúchil", "their colour and scent light the path",
        '<svg viewBox="-30 -26 60 50">'
        + "".join(marigold(x, y, s) for x, y, s in ((-14, 6, 1.25), (14, 6, 1.25), (0, -4, 1.45), (-4, 14, 1.1), (8, 15, 1.0)))
        + "</svg>",
    ),
)


def _offerings(seed: str) -> str:
    figures = "".join(
        f'<figure class="offering">{svg}<figcaption><b>{esc(name)}</b>{esc(why)}</figcaption></figure>'
        for name, why, svg in _OFFERINGS
    )
    skulls = "".join(portrait(f"{seed}:{n}") for n in range(3))
    figures += (
        f'<figure class="offering sugar"><div class="trio">{skulls}</div>'
        "<figcaption><b>Calaveritas</b>sugar skulls, one for every name</figcaption></figure>"
    )
    return figures


def _haunt_list(ghosts: list[Ghost]) -> str:
    rows = []
    for g in ghosts:
        for h in g.haunts:
            rows.append((not h.is_call, h.where, h, g))
    if not rows:
        return ""
    rows.sort(key=lambda r: (r[0], r[1]))
    items = "".join(
        f'<li class="{"call" if h.is_call else "mention"}"><span class="tag">{"still called" if h.is_call else "mentioned"}</span>'
        f'<code class="where">{esc(h.where)}</code><code class="line">{esc(h.text)}</code>'
        f'<span class="who">names <a href="#{esc(g.key)}">{esc(g.label)}</a></span></li>'
        for _, _, h, g in rows[:60]
    )
    calls = sum(1 for r in rows if not r[0])
    lead = (
        f"<strong>{calls} line{'s still call' if calls != 1 else ' still calls'} code that no longer exists.</strong> "
        if calls
        else ""
    )
    return f"""<section class="unfinished">
  <h2>Unfinished business</h2>
  <p>They say a spirit lingers where it is still spoken of. Every line below, in today's code, names one of the departed. {lead}Mentions are usually stale comments and docs; calls are bugs waiting for their night.</p>
  <ul>{items}</ul>
</section>"""


def _petals(rnd: random.Random, n: int = 26) -> str:
    return "".join(
        f'<i style="--x:{rnd.uniform(0, 100):.1f}%;--s:{rnd.uniform(8, 15):.1f}px;--t:{rnd.uniform(11, 22):.1f}s;'
        f'--d:-{rnd.uniform(0, 22):.1f}s;--dx:{rnd.uniform(-90, 90):.0f}px;--r:{rnd.choice((-1, 1)) * rnd.randint(200, 720)}deg"></i>'
        for _ in range(n)
    )


def render(graveyard: Graveyard, shown: list[Ghost], voice: str, when: datetime | None = None) -> str:
    when = when or datetime.now().astimezone()
    rnd = _rnd(graveyard.name)
    total = len(graveyard.ghosts)
    tiers = []
    width = 0
    for i, (title, subtitle, test, cloth) in enumerate(TIERS):
        members = [g for g in shown if test(g.lifespan_days)]
        if not members:
            continue
        rows = -(-len(members) // 4)
        cols = -(-len(members) // rows)
        row_width = cols * CARD + (cols - 1) * GAP
        width = max(row_width + 140, width + 150)
        cards = "\n".join(_card(g) for g in members)
        tiers.append(
            f'<section class="tier t{i}" style="--cloth:{cloth};--w:{width}px;--row:{row_width}px">'
            f'<h2 class="tier-name">{title}<small>{subtitle}</small></h2>'
            f'<div class="portraits">{cards}</div>{_ledge(f"{graveyard.name}:{i}", 7 + 2 * cols)}<div class="step"></div></section>'
        )
    if not tiers:
        width = 760
        tiers.append(
            f'<section class="tier t0" style="--cloth:#a3135a;--w:{width}px"><h2 class="tier-name">No one has departed<small>this history has lost nothing yet</small></h2>'
            f'{_ledge(graveyard.name, 9)}<div class="step"></div></section>'
        )
    tiers.append(
        f'<section class="tier offerings" style="--cloth:#b9480d;--w:{max(width + 150, 1100)}px"><h2 class="tier-name">Las ofrendas<small>what we leave for them</small></h2>'
        f'<div class="gifts">{_offerings(graveyard.name)}</div>{_ledge(f"{graveyard.name}:base", 17)}<div class="step"></div></section>'
    )

    lines = sum(g.lines for g in graveyard.ghosts)
    oldest = min((g.born.when for g in graveyard.ghosts if g.born), default=None)
    stats = [
        (f"{total}", "spirits found" if total != 1 else "spirit found"),
        (f"{lines:,}", "lines laid to rest"),
        (f"{graveyard.commits:,}", "commits remembered"),
    ]
    if oldest:
        stats.append((year(oldest), "oldest memory"))
    stats_html = "".join(f"<li><b>{esc(v)}</b><span>{esc(k)}</span></li>" for v, k in stats)
    showing = (
        f'<p class="showing">The altar holds {len(shown)} of them. Run <code>git ofrenda --all</code> to honor every one.</p>'
        if len(shown) < total
        else ""
    )
    by = (
        f"written by <b>{esc(voice)}</b>, an open-weight model running locally through Ollama"
        if voice != "offline verses"
        else "written from offline verses (no local model was awake)"
    )
    css = _CSS.replace("/*STARS*/", _stars(rnd))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ofrenda for {esc(graveyard.name)}</title>
<meta name="description" content="A Día de los Muertos altar for the code that once lived in {esc(graveyard.name)}.">
<style>{css}</style>
</head>
<body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>
  <linearGradient id="bread" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e09a4f"/><stop offset="1" stop-color="#a85a1c"/></linearGradient>
</defs></svg>
<div class="sky" aria-hidden="true"></div>
<div class="petals" aria-hidden="true">{_petals(rnd)}</div>
{_papel_picado()}
<header class="hero">
  <p class="eyebrow">Día de los Muertos &middot; {esc(when.year)}</p>
  <h1>Ofrenda</h1>
  <p class="for">for the departed code of <strong>{esc(graveyard.name)}</strong></p>
  <p class="intro">On the Day of the Dead, families build altars so the departed can find their way home for a night. It is said that no one is truly gone until they are forgotten. Git never forgets, but we do. These functions once lived in this repository and live there no longer. Tonight, we remember them.</p>
  <ul class="stats">{stats_html}</ul>
  {showing}
</header>
<main class="altar">
{"".join(tiers)}
</main>
{_haunt_list(shown)}
<footer>
  <p class="path" aria-hidden="true">{"".join(f'<svg viewBox="-12 -12 24 24">{marigold(0, 0, 1)}</svg>' for _ in range(5))}</p>
  <p>Built on this machine by <b>git-ofrenda</b> from {graveyard.commits:,} commits on <code>{esc(graveyard.rev)}</code>, {esc(day(when))}. The remembrances and calaveras were {by}. No source code, commit message or name left this computer.</p>
  <p>Speak with any of them: <code>git ofrenda summon &lt;name&gt;</code></p>
</footer>
<script>
document.querySelectorAll("[data-summon]").forEach(function (button) {{
  button.addEventListener("click", function () {{
    var cmd = button.dataset.summon;
    var done = function (text) {{
      button.textContent = text;
      setTimeout(function () {{ button.textContent = button.dataset.label; }}, 2600);
    }};
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(cmd).then(function () {{ done("Copied: " + cmd); }}, function () {{ done(cmd); }});
    }} else {{
      done(cmd);
    }}
  }});
}});
</script>
</body>
</html>
"""


_CSS = """
:root {
  --night: #0f0819; --plum: #2a1745; --bone: #f8efe2; --muted: #cdbcdd; --faint: #9a86b3;
  --marigold: #ff9f1c; --gold: #ffd166; --magenta: #e6197e; --teal: #1fb5ac; --red: #ff6b6f;
  --frame: #d9a441; --lace: #f1e0bd;
  color-scheme: dark;
}
* { box-sizing: border-box; }
html { background: var(--night); }
body {
  margin: 0; min-height: 100vh; overflow-x: hidden; color: var(--bone);
  font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background:
    radial-gradient(ellipse 70% 40% at 50% 104%, rgba(255, 140, 40, .22), transparent 70%),
    radial-gradient(ellipse 70% 45% at 50% -8%, rgba(138, 79, 255, .26), transparent 70%),
    linear-gradient(#0f0819, #1a0d2c 45%, #120a1f);
  background-attachment: fixed;
}
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
.serif, h1, h2, .for, .dates, .calavera { font-family: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif; }

.sky { position: fixed; inset: 0; pointer-events: none; z-index: 0; }
.sky::before {
  content: ""; position: absolute; top: 0; left: 0; width: 2px; height: 2px; border-radius: 50%;
  box-shadow: /*STARS*/; animation: twinkle 7s ease-in-out infinite alternate;
}
@keyframes twinkle { from { opacity: .55; } to { opacity: 1; } }

.petals { position: fixed; inset: 0; pointer-events: none; z-index: 5; overflow: hidden; }
.petals i {
  position: absolute; top: -24px; left: var(--x); width: var(--s); height: calc(var(--s) * .62);
  border-radius: 70% 0 70% 0; background: linear-gradient(135deg, #ffc23c, #f26b1d); opacity: .7;
  animation: fall var(--t) linear var(--d) infinite;
}
@keyframes fall { to { transform: translate3d(var(--dx), 110vh, 0) rotate(var(--r)); } }

.banner { position: relative; z-index: 2; display: flex; justify-content: center; gap: 4px; height: 128px; overflow: hidden; padding-top: 10px; }
.banner::before { content: ""; position: absolute; left: 0; right: 0; top: 12px; height: 2px; background: #e9d8b8; opacity: .55; }
.flag { flex: 0 0 auto; width: 80px; height: 96px; transform-origin: 50% 0; filter: drop-shadow(0 8px 10px rgba(0, 0, 0, .4)); animation: sway var(--t) ease-in-out var(--d) infinite alternate; }
@keyframes sway { from { transform: rotate(-3deg) skewX(1deg); } to { transform: rotate(3deg) skewX(-1deg); } }

.hero { position: relative; z-index: 2; text-align: center; padding: 8px 16px 0; }
.eyebrow { margin: 0; letter-spacing: .32em; text-transform: uppercase; font-size: .78rem; color: var(--marigold); }
h1 {
  margin: .08em 0 .02em; font-size: clamp(3.4rem, 12vw, 7.4rem); line-height: .95; font-weight: 700; letter-spacing: .02em;
  color: var(--gold); text-shadow: 0 0 18px rgba(255, 159, 28, .55), 0 0 70px rgba(230, 25, 126, .4);
}
.for { margin: 0; font-style: italic; font-size: clamp(1.15rem, 3.2vw, 1.55rem); color: var(--muted); }
.for strong { font-style: normal; color: var(--bone); }
.intro { max-width: 650px; margin: 20px auto 0; color: var(--muted); }
.stats { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px 34px; margin: 26px auto 0; padding: 0; list-style: none; }
.stats li { min-width: 92px; }
.stats b { display: block; font: 600 1.75rem/1.1 "Iowan Old Style", Palatino, Georgia, serif; color: var(--bone); }
.stats span { font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: var(--faint); }
.showing { margin: 18px 0 0; font-size: .88rem; color: var(--faint); }
.showing code { color: var(--gold); }

.altar { position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; margin: 56px auto 0; padding: 0 16px; }
.tier { width: 100%; max-width: var(--w, 1200px); display: flex; flex-direction: column; align-items: center; margin-bottom: 58px; }
.tier-name { margin: 0 0 22px; text-align: center; font-weight: 600; font-size: 1.75rem; color: var(--gold); }
.tier-name small { display: block; margin-top: 2px; font: 500 .74rem/1.4 ui-sans-serif, system-ui, sans-serif; letter-spacing: .16em; text-transform: uppercase; color: var(--faint); }
.portraits { display: flex; flex-wrap: wrap; justify-content: center; align-items: flex-start; gap: 34px 26px; width: 100%; max-width: var(--row, 100%); }
.ledge { display: flex; justify-content: space-evenly; align-items: flex-end; width: 100%; height: 92px; padding: 0 3%; margin-top: 18px; }
.step {
  position: relative; width: 100%; height: 36px; border-radius: 5px 5px 0 0;
  background: radial-gradient(rgba(255, 255, 255, .13) 1.4px, transparent 1.9px) 0 0 / 14px 14px, linear-gradient(var(--cloth), color-mix(in srgb, var(--cloth) 62%, #000));
  box-shadow: 0 22px 44px rgba(0, 0, 0, .5), inset 0 2px 0 rgba(255, 255, 255, .15);
}
.step::after {
  content: ""; position: absolute; left: 0; right: 0; top: 100%; height: 13px;
  background: radial-gradient(circle at 10px 0, var(--lace) 6.5px, transparent 7px) 0 0 / 20px 13px repeat-x;
}

.candle { position: relative; display: block; width: 15px; height: var(--h); border-radius: 4px 4px 2px 2px; background: linear-gradient(90deg, #e3d5ba, #fff8ea 45%, #d6c5a4); }
.candle::before { content: ""; position: absolute; left: 50%; top: -6px; width: 2px; height: 7px; margin-left: -1px; border-radius: 1px; background: #3a2a1a; }
.candle.drip::after { content: ""; position: absolute; top: 1px; left: 2px; width: 4px; height: 13px; border-radius: 2px 2px 3px 3px; background: #fffaf0; }
.candle i {
  position: absolute; left: 50%; bottom: calc(100% + 3px); width: 12px; height: 22px; margin-left: -6px;
  border-radius: 50% 50% 50% 50% / 62% 62% 38% 38%; transform-origin: 50% 90%;
  background: radial-gradient(ellipse at 50% 75%, #fff 0 16%, #ffe08a 34%, #ff9f1c 62%, rgba(242, 107, 29, 0) 72%);
  animation: flicker var(--f) ease-in-out infinite alternate;
}
.candle i::after { content: ""; position: absolute; left: 50%; top: 50%; width: 96px; height: 96px; margin: -54px 0 0 -48px; border-radius: 50%; background: radial-gradient(rgba(255, 170, 60, .33), rgba(255, 170, 60, 0) 66%); }
@keyframes flicker {
  0% { transform: scale(1, 1) rotate(-1deg); opacity: .93; }
  45% { transform: scale(.93, 1.07) rotate(2deg); }
  75% { transform: scale(1.05, .94) rotate(-2deg); opacity: 1; }
  100% { transform: scale(.97, 1.03) rotate(1deg); opacity: .9; }
}
.bloom { width: 38px; height: 38px; margin-bottom: -6px; }

.retrato {
  position: relative; width: 300px; padding: 20px 20px 18px; text-align: center; border-radius: 140px 140px 14px 14px;
  background: radial-gradient(ellipse 90% 40% at 50% 0%, rgba(255, 209, 102, .10), transparent 70%), linear-gradient(180deg, #2c1848, #1a0e2d);
  box-shadow: 0 0 0 2px #120a1f, 0 0 0 5px var(--frame), 0 0 0 7px #120a1f, 0 0 0 8px rgba(217, 164, 65, .45), 0 24px 46px rgba(0, 0, 0, .55), 0 0 70px rgba(255, 159, 28, .10);
}
.retrato .skull { display: block; width: 122px; height: auto; margin: 6px auto 4px; filter: drop-shadow(0 0 16px rgba(255, 209, 102, .22)); }
.retrato h3 { margin: 6px 0 2px; font: 650 1.03rem/1.3 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; overflow-wrap: anywhere; }
.retrato h3.long { font-size: .9rem; }
.kind { margin: 0; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); overflow-wrap: anywhere; }
.dates { margin: 10px 0 0; font-size: 1.04rem; color: var(--gold); }
.age { margin: 0; font-size: .82rem; color: var(--muted); }
.remembrance { margin: 14px 0 0; font-size: .9rem; text-align: left; color: var(--muted); }
.calavera {
  position: relative; margin: 18px -2px 6px; padding: 16px 16px 12px; text-align: left; border-radius: 3px; transform: rotate(-1.2deg);
  background: linear-gradient(#fcf5e7, #f0e0c2); color: #3a2350; font-style: italic; font-size: .9rem; line-height: 1.42;
  box-shadow: 0 10px 20px rgba(0, 0, 0, .38);
}
.retrato:nth-child(even) .calavera { transform: rotate(1.1deg); }
.calavera::before { content: ""; position: absolute; top: -8px; left: 50%; width: 52px; height: 15px; margin-left: -26px; background: rgba(255, 201, 60, .62); transform: rotate(2deg); }
.calavera p { margin: 0; padding-left: 1.1em; text-indent: -1.1em; }
.calavera cite { display: block; margin-top: 9px; font: 600 .66rem/1.3 ui-sans-serif, system-ui, sans-serif; letter-spacing: .1em; text-transform: uppercase; color: #8d6aa3; }
.facts { display: grid; gap: 7px; margin: 16px 0 0; text-align: left; font-size: .84rem; }
.facts div { display: grid; grid-template-columns: 104px 1fr; gap: 8px; }
.facts dt { padding-top: 2px; font-size: .66rem; letter-spacing: .1em; text-transform: uppercase; color: var(--faint); }
.facts dd { margin: 0; overflow-wrap: break-word; min-width: 0; }
.facts q, .life q { color: var(--muted); font-style: italic; }
.facts code, .haunt code { font-size: .8rem; color: var(--gold); }
.haunt { margin: 14px 0 0; padding: 8px 10px; border-radius: 8px; text-align: left; font-size: .8rem; color: #c4f4ef; background: rgba(31, 181, 172, .12); border: 1px solid rgba(31, 181, 172, .38); }
.haunt.call { color: #ffd6d7; background: rgba(255, 107, 111, .13); border-color: rgba(255, 107, 111, .5); }
details { margin-top: 14px; text-align: left; }
summary { cursor: pointer; list-style: none; font-size: .84rem; letter-spacing: .03em; color: var(--marigold); }
summary::-webkit-details-marker { display: none; }
summary::before { content: "\\25B8  "; }
details[open] summary::before { content: "\\25BE  "; }
pre { max-height: 340px; overflow: auto; margin: 10px 0 0; padding: 12px; border-radius: 8px; border: 1px solid #3a2556; background: #0c0614; color: #eadff7; font-size: .74rem; line-height: 1.5; }
.sub { margin: 14px 0 0; font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; color: var(--faint); }
.life { margin: 8px 0 0 4px; padding: 0; list-style: none; font-size: .78rem; color: var(--muted); }
.life li { position: relative; padding: 3px 0 7px 14px; border-left: 2px solid #3a2556; }
.life li::before { content: ""; position: absolute; left: -5px; top: 8px; width: 8px; height: 8px; border-radius: 50%; background: var(--marigold); }
.raise { margin: 14px 0 0; font-size: .7rem; letter-spacing: .12em; text-transform: uppercase; color: var(--faint); }
.raise code { display: block; margin-top: 6px; padding: 8px 10px; overflow-x: auto; white-space: nowrap; border-radius: 6px; background: #0c0614; color: var(--gold); font-size: .76rem; letter-spacing: 0; text-transform: none; }
.summon {
  display: block; width: 100%; margin-top: 16px; padding: 9px 12px; cursor: pointer; overflow-wrap: anywhere;
  font: 600 .8rem/1.3 ui-sans-serif, system-ui, sans-serif; letter-spacing: .06em; color: #1a0e2d;
  border: 0; border-radius: 999px; background: linear-gradient(90deg, var(--gold), var(--marigold));
  box-shadow: 0 0 22px rgba(255, 159, 28, .35);
}
.summon:hover { filter: brightness(1.08); }
.summon:focus-visible, summary:focus-visible, a:focus-visible { outline: 2px solid var(--gold); outline-offset: 3px; }

.gifts { display: flex; flex-wrap: wrap; justify-content: center; align-items: flex-end; gap: 22px 34px; }
.offering { width: 128px; margin: 0; text-align: center; }
.offering svg { display: block; width: 92px; height: 82px; margin: 0 auto; overflow: visible; }
.offering.sugar .trio { display: flex; justify-content: center; align-items: flex-end; height: 82px; }
.offering.sugar .skull { width: 40px; height: auto; margin: 0 -2px; }
.offering.sugar .skull:nth-child(2) { width: 50px; }
.offering figcaption { margin-top: 8px; font-size: .78rem; line-height: 1.35; color: var(--muted); }
.offering figcaption b { display: block; font: 600 1rem/1.3 "Iowan Old Style", Palatino, Georgia, serif; color: var(--gold); }
.smoke { animation: smoke 4.5s ease-in-out infinite; transform-origin: 50% 100%; }
@keyframes smoke { 0%, 100% { opacity: .5; transform: translateY(0) scaleX(1); } 50% { opacity: 1; transform: translateY(-3px) scaleX(-1); } }

.unfinished { position: relative; z-index: 2; max-width: 980px; margin: 0 auto 40px; padding: 0 16px; }
.unfinished h2 { margin: 0; font-size: 1.75rem; color: var(--gold); text-align: center; }
.unfinished > p { max-width: 680px; margin: 10px auto 20px; text-align: center; color: var(--muted); }
.unfinished strong { color: #ffd6d7; }
.unfinished ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.unfinished li { display: grid; grid-template-columns: auto auto 1fr auto; align-items: center; gap: 6px 14px; padding: 10px 14px; border-radius: 10px; background: rgba(31, 181, 172, .08); border: 1px solid rgba(31, 181, 172, .3); font-size: .84rem; }
.unfinished li.call { background: rgba(255, 107, 111, .1); border-color: rgba(255, 107, 111, .45); }
.unfinished .tag { font-size: .64rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--teal); }
.unfinished .call .tag { color: var(--red); }
.unfinished .where { color: var(--gold); }
.unfinished .line { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #eadff7; }
.unfinished .who { color: var(--faint); font-size: .78rem; }
.unfinished a { color: var(--marigold); }

footer { position: relative; z-index: 2; max-width: 720px; margin: 0 auto; padding: 10px 16px 64px; text-align: center; font-size: .86rem; color: var(--faint); }
footer code { color: var(--gold); }
footer b { color: var(--muted); }
footer .path { display: flex; justify-content: center; gap: 14px; }
footer .path svg { width: 26px; height: 26px; }

@media (max-width: 640px) {
  .banner { height: 96px; }
  .flag { width: 58px; height: 70px; }
  .retrato { width: 100%; max-width: 340px; }
  .ledge { height: 76px; }
  .unfinished li { grid-template-columns: auto 1fr; }
  .unfinished .line, .unfinished .who { grid-column: 1 / -1; }
}
@media (prefers-reduced-motion: reduce) {
  .petals { display: none; }
  .flag, .candle i, .smoke, .sky::before { animation: none; }
}
"""
