# git-ofrenda

**A Día de los Muertos altar for the code your repository deleted.**

`git ofrenda` walks your git history, finds every function and class that once lived in the repo and doesn't anymore, and builds them an ofrenda: a candle-lit HTML altar with a sugar-skull portrait, a lifespan, a cause of death, a *calavera literaria* and the code's last words. You can also light a candle and talk with any of them, or ask which lines in today's code still call something that died.

The writing is done by an open-weight model (qwen3:8b by default) running on your own machine through [Ollama](https://ollama.com). No source code, commit message or author name leaves your computer.

![The ofrenda for a demo repository](assets/altar.png)

## Install

Requires Python 3.10+ and git. There are no Python dependencies.

```bash
git clone https://github.com/Big0boy/git-ofrenda && cd git-ofrenda
uv tool install .          # or: pipx install .
```

That puts `git-ofrenda` on your PATH, and git picks it up as a subcommand: `git ofrenda`.

For the AI parts, install [Ollama](https://ollama.com) and pull a model:

```bash
ollama pull qwen3:8b       # the default; any chat model works
```

Without Ollama everything still runs. The verses come from offline templates instead.

## Use

```bash
cd your-repo
git ofrenda                    # build the altar (12 most recent spirits)
git ofrenda --all --open       # honor every one, then open the page
git ofrenda list               # just list the departed (instant, no model)
git ofrenda summon parse_legacy_config   # hold a séance
git ofrenda haunts --strict    # lines that still call dead code; exit 1 if any (CI-friendly)
```

The altar is written to `.git/ofrenda/ofrenda.html`, so it never shows up in your working tree. Use `-o` to put it elsewhere. Calaveras are cached in `.git/ofrenda/spirits.json`, so a rebuild is instant. `--fresh` writes new ones.

Useful flags: `--model gemma3:12b` (any Ollama model), `--no-ai`, `--since "2 years ago"`, `--sort recent|lifespan|size|haunting`, `--tests` (include deleted tests), `--json`.

> `git ofrenda --help` makes git look for a man page. Use `git ofrenda -h`.

### The séance

```text
$ git ofrenda summon retry_forever --ask "What happened at 3am?"
retry_forever() › … At 3am, the accountant's server was down, and I tried to upload the batch.
I kept trying, again and again, without giving up. My loop ran endlessly, and the system
crashed under the weight of my persistence. … I was meant to be a safety, but I became a storm.
```

In interactive mode, `/code` prints its body, `/life` lists the commits that shaped it (via `git log -L`), `/haunts` shows where it is still named, `/resurrect` prints the command that brings its body back, and `/leave` blows out the candle.

### Unfinished business

```text
$ git ofrenda haunts
still called  bakery/cron.py:13  legacy_ftp_upload(orders)
              ↳ legacy_ftp_upload() died 18 Nov 2024 in 56864e79: Remove FTP sync, nobody has used it since 2021
mentioned     README.md:7  At 2am, cron runs `legacy_ftp_upload()` to send the day's orders to our accountant.
```

A call to a function that no longer exists is a bug waiting for its night. A mention is usually a stale comment or doc.

## Try it on the demo repository

`scripts/make_haunted_repo.py` builds a fictional bakery's repository with seven years of history (2019–2026), four authors, and a fax machine, a dot-matrix printer and an FTP server buried in it:

```bash
python scripts/make_haunted_repo.py /tmp/panaderia
git ofrenda -C /tmp/panaderia --open
```

`assets/demo-ofrenda.html` is the altar it produces.

## How it works

1. **One pass over history.** `git log -p --unified=0 --reverse` streams every diff. A small set of per-language patterns (Python, JS/TS, Go, Rust, Ruby, Java, C#, Kotlin, Swift, C/C++, PHP, Lua, shell) spots lines that define something. An added definition is a birth and a removed one is a death.
2. **Who is really gone.** Anything still defined at `HEAD` is alive, which covers moves, renames, signature changes and code that came back. A method that died with its class is folded into the class.
3. **Exhuming.** The body is cut from the file as it stood just before the fatal commit (`<sha>^:<path>`). Indentation, brace and `end` matching handle strings, comments and template literals. `git log -L` recovers every commit that shaped it.
4. **Kin and haunts.** Definitions born in the commit that killed a function are its survivors. `git grep` finds lines in today's code that still name it, filtered so a namesake in another language or `strings.Contains(` doesn't count against a dead `Contains`.
5. **The scribe.** The local model reads the facts and the source and returns JSON: a one-line remembrance, plus the details of a calavera (what it was doing when Death found it, its lovable flaw, what it begged for). Python owns the rhyme scheme, and git, not the model, decides who replaced it. 8B models don't rhyme reliably on request; they're very good at reading code.
6. **The altar.** One self-contained HTML file with no external requests: papel picado cut with SVG masks, CSS candles, a deterministic sugar skull per name, tiers by lifespan, and the traditional offerings. Motion respects `prefers-reduced-motion`.

## Tests

```bash
uv run --with pytest pytest
```

The suite builds the demo repository and checks detection, attribution, body extraction across languages, haunts, the scribe (with a fake model), the HTML and the CLI.

## Limits

- Definitions are found with patterns, not parsers. Unusual styles (K&R C, Java methods without modifiers, Go types grouped with non-struct members inside a diff) can be missed.
- Common names like `run` or `render` collect stale *mentions* in docs. Calls are filtered much more strictly.
- An 8B model sometimes embellishes: a remembrance or a séance answer can claim a loop that wasn't there. The facts block (dates, authors, commits, survivors) always comes from git. A larger model (`--model qwen3:14b`, `gemma3:12b`) speaks more accurately.

MIT licensed.
