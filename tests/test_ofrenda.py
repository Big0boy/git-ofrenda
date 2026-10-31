import importlib.util
import json
from pathlib import Path

import pytest

from ofrenda import cli
from ofrenda.altar import render
from ofrenda.history import cause_of_death, choose, find_ghosts
from ofrenda.langs import block_span, lang_for
from ofrenda.spirits import Medium, Scribe, compose, persona, usable
from ofrenda.words import span

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("make_haunted_repo", ROOT / "scripts" / "make_haunted_repo.py")
haunted = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(haunted)

DEPARTED = {
    "getDiscountV2", "XmlInvoiceBuilder", "quick_hack_for_demo", "legacy_ftp_upload", "preheatLegacy",
    "print_receipt_dot_matrix", "calcCartTotalOld", "retry_forever", "fax_order_to_kitchen", "send_fax",
}


@pytest.fixture(scope="session")
def repo(tmp_path_factory):
    return haunted.build(tmp_path_factory.mktemp("yard") / "panaderia")


@pytest.fixture(scope="session")
def yard(repo):
    return find_ghosts(repo)


def ghost(yard, name):
    found = yard.find(name)
    assert found is not None, name
    return found


def test_finds_exactly_the_departed(yard):
    assert {g.name for g in yard.ghosts} == DEPARTED
    assert yard.commits == len(haunted.TIMELINE)


def test_moved_renamed_and_edited_code_is_still_alive(yard):
    names = {g.name for g in yard.ghosts}
    # moved to money.py, signature changed, `function` became `export function`
    assert not {"round_to_peso", "order_total", "renderCart", "create_order"} & names
    # a method that died with its class rests inside the class's portrait
    assert "build" not in names


def test_birth_death_and_kin(yard):
    g = ghost(yard, "legacy_ftp_upload")
    assert g.born.author == "Rosa Delgado"
    assert g.died.author == "Tomás Reyes"
    assert g.died.subject.startswith("Remove FTP sync")
    assert g.cause == "Died of loneliness: no one called anymore"
    assert g.survived_by == ["push_orders_to_sheet"]
    assert not g.by_own_hand
    assert 2100 < g.lifespan_days < 2120
    assert ghost(yard, "XmlInvoiceBuilder").survived_by == ["build_invoice_json"]
    assert ghost(yard, "quick_hack_for_demo").by_own_hand


def test_unfinished_business(yard):
    g = ghost(yard, "legacy_ftp_upload")
    assert g.call_count == 1 and g.haunt_count == 3
    call = g.haunts[0]
    assert call.is_call and call.path == "bakery/cron.py" and "legacy_ftp_upload(orders)" in call.text
    assert {h.path for h in g.haunts if not h.is_call} == {"README.md", "bakery/cron.py"}
    assert [h.path for h in ghost(yard, "XmlInvoiceBuilder").haunts] == ["docs/invoices.md"]
    assert ghost(yard, "retry_forever").haunts == []


def test_bodies_are_exhumed_whole(yard):
    ftp = ghost(yard, "legacy_ftp_upload")
    assert ftp.source.startswith("def legacy_ftp_upload(")
    assert ftp.source.rstrip().endswith("return len(orders)")
    assert "json.dumps" in ftp.favorites[0] or "json.dumps" in ftp.favorites

    xml = ghost(yard, "XmlInvoiceBuilder")
    assert xml.kind == "class" and "def build(self):" in xml.source
    assert xml.source.rstrip().endswith('return ET.tostring(root, encoding="unicode")')

    js = ghost(yard, "calcCartTotalOld")
    assert js.lang.name == "JavaScript" and js.lines == 7 and js.source.endswith("}")

    go = ghost(yard, "preheatLegacy")
    assert go.lang.name == "Go" and go.lines == 6

    discount = ghost(yard, "getDiscountV2")
    assert discount.source.startswith("// Buy 3 conchas")  # the comment resting on it comes along
    assert discount.resurrect_command.startswith(f"git show {discount.died.short}^:web/cart.js | sed -n '")


@pytest.mark.parametrize(
    "path, text, start, expected",
    [
        ("a.py", "def f(\n    a,\n    b,\n):\n    return a\n\n\nx = 1\n", 0, (0, 4)),
        ("a.py", "@cache\ndef f():\n    s = '''\nnot indented\n'''\n    return s\ndef g(): pass\n", 1, (0, 5)),
        ("a.py", "def f(): return 1\ndef g():\n    pass\n", 0, (0, 0)),
        ("a.js", 'function f() {\n  const s = "}";\n  return `${s}{`;\n}\nfunction g() {}\n', 0, (0, 3)),
        ("a.js", "const f = (x) => x * 2\nconst g = () => {\n}\n", 0, (0, 0)),
        ("a.js", "const f = (x) =>\n  x * 2;\nconst g = 1\n", 0, (0, 1)),
        ("a.rs", "fn f<'a>(x: &'a str) -> char {\n    let c = '{';\n    c\n}\nfn g() {}\n", 0, (0, 3)),
        ("a.go", "// Add adds.\nfunc Add(a, b int) int {\n\treturn a + b\n}\n", 1, (0, 3)),
        ("a.rb", "def f\n  if x\n    y\n  end\nend\ndef g; end\n", 0, (0, 4)),
        ("a.c", "static int\nf(void);\nint main(void)\n{\n  return 0;\n}\n", 2, (2, 5)),
        ("a.go", "type ID int\n\nfunc (i ID) String() string {\n\treturn \"\"\n}\n", 0, (0, 0)),
        ("a.go", "type (\n\tdoneMsg struct {\n\t\terr error\n\t}\n)\n", 1, (1, 3)),
    ],
)
def test_block_span(path, text, start, expected):
    lang = lang_for(path)
    assert lang.match(text.splitlines()[start])
    assert block_span(text.splitlines(), start, lang) == expected


def test_definitions_are_recognised():
    cases = {
        "a.py": ["async def go(x):", "class Thing(Base):"],
        "a.ts": ["export default async function load<T>(x) {", "export const pick = async (a: A): B => {", "interface Shape {"],
        "a.go": ["func (s *Server) Serve(ctx context.Context) error {", "type Store struct {"],
        "a.rs": ["pub(crate) async fn fetch(&self) -> Result<()> {", "pub enum Mode {"],
        "a.java": ["    public static List<String> names(int n) {"],
        "a.sh": ["deploy() {", "function cleanup {"],
    }
    for path, lines in cases.items():
        for line in lines:
            assert lang_for(path).match(line), (path, line)
    assert lang_for("a.py").match("    def close(self):") == ("method", "close")
    assert lang_for("a.py").match("def close(self):") == ("function", "close")
    assert lang_for("a.go").match("func (s *Store) Close() error {") == ("method", "Close")
    assert lang_for("a.go").match("type Handler func(w Writer)") == ("type", "Handler")
    assert lang_for("a.go").match("\tdoneMsg struct{}") == ("type", "doneMsg")
    assert lang_for("a.rs").match("    pub fn new() -> Self {") == ("method", "new")
    assert lang_for("a.rs").match("pub(crate) fn run() {") == ("function", "run")
    assert lang_for("a.js").match("  setInterval(function () {") is None
    assert lang_for("a.js").match("  describe('x', () => {") is None
    assert lang_for("a.js").match("  if (ready) {") is None
    assert lang_for("a.c").match("  return helper(x);") is None


def test_causes_of_death():
    assert cause_of_death("Revert discount v2").startswith("Reverted")
    assert cause_of_death("fix: retry_forever caused the outage") == "Fell in the line of a bugfix"
    assert cause_of_death("Migrate invoices to JSON") == "Replaced by a younger function"
    assert cause_of_death("remove dead code") == "Died of loneliness: no one called anymore"
    assert cause_of_death("Refactor the parser") == "Refactored out of existence"
    assert cause_of_death("wip") == "Passed quietly, without explanation"


def test_spans():
    assert span(0.5) == "12 hours"
    assert span(19) == "19 days"
    assert span(400) == "1 year, 1 month"
    assert span(3 * 365.25) == "3 years"


def test_choose_orders(yard):
    assert choose(yard.ghosts, "recent", 1)[0].name == "getDiscountV2"
    assert choose(yard.ghosts, "haunting", 1)[0].name == "legacy_ftp_upload"
    assert len(choose(yard.ghosts, "size", None)) == len(yard.ghosts)


def test_compose_uses_git_for_the_successor(yard):
    g = ghost(yard, "retry_forever")
    details = {
        "remembrance": "Retried forever.", "habit": "Still retrying uploads every second",
        "quirk": "while True loop", "plea": "one more retry", "successor": "a JSON exporter",
    }
    assert usable(details)
    verse = compose(g, details)
    text = "\n".join(verse)
    assert len(verse) == 4
    assert "retrying uploads every second" in text and "still still" not in text
    assert "upload_with_backoff()" in text and "JSON exporter" not in text
    for turn in range(4):  # every template, so the plea slot gets used somewhere
        text = "\n".join(compose(g, details, turn))
        assert "one more one more" not in text and "final one more" not in text
        assert text.count("retry_forever()") == 1


def test_compose_falls_back_slot_by_slot(yard):
    g = ghost(yard, "print_receipt_dot_matrix")
    verse = compose(g, {"remembrance": "x", "habit": "the loop", "quirk": "relied on ~/.netrc", "plea": 3, "successor": ""})
    text = "\n".join(verse)
    assert "relied on" not in text and "silence" in text
    assert not usable({"remembrance": "x", "habit": "the loop", "quirk": "relied on x", "plea": "run"})


class FakeMedium:
    ready = True
    model = "fake:1b"
    label = "fake:1b"

    def __init__(self):
        self.calls = 0

    def ask_json(self, system, prompt, temperature=0.75):
        self.calls += 1
        return {"remembrance": "It sent files.", "habit": "pushing bytes uphill", "quirk": "missing import", "plea": "upload", "successor": "silence"}


def test_scribe_writes_then_remembers(yard, tmp_path):
    g = ghost(yard, "legacy_ftp_upload")
    cache = tmp_path / "spirits.json"
    medium = FakeMedium()
    scribe = Scribe(medium, cache)
    assert scribe.remember(g) is True
    scribe.save()
    assert medium.calls == 1 and g.voice == "fake:1b" and len(g.calavera) == 4
    assert "pushing bytes uphill" in " ".join(g.calavera)

    again = FakeMedium()
    assert Scribe(again, cache).remember(g) is False
    assert again.calls == 0
    assert json.loads(cache.read_text())


def test_offline_scribe(yard):
    g = ghost(yard, "send_fax")
    medium = Medium(enabled=False)
    assert not medium.ready and medium.label == "offline verses"
    Scribe(medium, None).remember(g)
    assert g.voice == "offline" and len(g.calavera) == 4
    assert "Python function" in g.remembrance


def test_persona_carries_the_facts(yard):
    g = ghost(yard, "legacy_ftp_upload")
    text = persona(yard, g)
    assert "Tomás Reyes" in text and "ftplib.FTP(host)" in text
    assert "still calls you" in text and g.resurrect_command in text


def test_altar_is_escaped_and_complete(yard):
    for g in yard.ghosts:
        Scribe(Medium(enabled=False), None).remember(g)
    page = render(yard, yard.ghosts, "offline verses")
    assert page.startswith("<!doctype html>")
    assert "{item:&lt;24}" in page and "{item:<24}" not in page
    for g in yard.ghosts:
        assert f'id="{g.key}"' in page
    assert "Los Ancestros" in page and "Una temporada" in page and "Velas breves" in page
    assert "Unfinished business" in page and "still called" in page
    assert "http://" not in page.split("<body>")[0]  # no external assets in the head


def test_cli_build_offline(repo, tmp_path, capsys):
    out = tmp_path / "altar.html"
    assert cli.main(["-C", str(repo), "--no-ai", "-q", "-o", str(out)]) == 0
    assert out.read_text().count('class="retrato"') == 10
    assert capsys.readouterr().out.strip() == out.resolve().as_uri()


def test_cli_json(repo, capsys):
    assert cli.main(["build", "-C", str(repo), "--no-ai", "--json", "-n", "2"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["name"] for d in data["departed"]] == ["getDiscountV2", "XmlInvoiceBuilder"]


def test_cli_haunts_strict(repo, capsys):
    assert cli.main(["haunts", "-C", str(repo)]) == 0
    assert "bakery/cron.py:13" in capsys.readouterr().out
    assert cli.main(["haunts", "-C", str(repo), "--strict"]) == 1


def test_cli_summon_offline(repo, capsys):
    code = cli.main(["summon", "legacy_ftp_upload", "-C", str(repo), "--no-ai", "--ask", "Who deleted you, and why?"])
    out = capsys.readouterr().out
    assert code == 0 and "Tomás Reyes" in out and "nobody has used it" in out


def test_cli_summon_unknown(repo, capsys):
    assert cli.main(["summon", "legacy_ftp", "-C", str(repo), "--no-ai", "--ask", "hi"]) == 1
    assert "legacy_ftp_upload" in capsys.readouterr().err


def test_not_a_repository(tmp_path, capsys):
    assert cli.main(["list", "-C", str(tmp_path)]) == 2
    assert "not inside a git repository" in capsys.readouterr().err
