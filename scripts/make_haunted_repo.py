"""Build a small, fictional repository with seven years of births and deaths.

    python scripts/make_haunted_repo.py /tmp/panaderia

La Panadería del Barrio is a made-up neighbourhood bakery. Its code has buried a fax
machine, a dot-matrix printer and an FTP server, and it still calls one of them.
The people and addresses are invented; every email is @panaderia.example.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PEOPLE = {
    "rosa": ("Rosa Delgado", "rosa@panaderia.example"),
    "tomas": ("Tomás Reyes", "tomas@panaderia.example"),
    "mina": ("Mina Park", "mina@panaderia.example"),
    "dev": ("Dev Anand", "dev@panaderia.example"),
}

ORDERS_HEAD = '''"""Orders for La Panadería del Barrio."""

from datetime import date

PRICES = {"concha": 12, "pan de muerto": 45, "bolillo": 4, "cuerno": 15}'''

CREATE_ORDER = '''def create_order(customer, items):
    return {"customer": customer, "items": list(items), "day": date.today().isoformat()}'''

ORDER_TOTAL_V1 = '''def order_total(order):
    return sum(PRICES[item] for item in order["items"])'''

ORDER_TOTAL_V2 = '''def order_total(order, tax=0.16):
    subtotal = sum(PRICES[item] for item in order["items"])
    return round(subtotal * (1 + tax), 2)'''

DOT_MATRIX = '''def print_receipt_dot_matrix(order, port="/dev/lp0"):
    """Our Epson LX-300 needs CR+LF and a form feed, or it eats the paper."""
    lines = [f"PANADERIA DEL BARRIO  {order['day']}", "-" * 32]
    for item in order["items"]:
        lines.append(f"{item:<24}{PRICES[item]:>6}")
    lines.append(f"{'TOTAL':<24}{order_total(order):>6}")
    with open(port, "w") as printer:
        printer.write("\\r\\n".join(lines) + "\\r\\n\\f")'''

SEASON = '''def pan_de_muerto_season(today=None):
    """Pan de muerto is baked from mid October until the 2nd of November."""
    today = today or date.today()
    return (today.month == 10 and today.day >= 15) or (today.month == 11 and today.day <= 2)'''

LOAD_TODAY = '''def load_today(path="orders/today.jsonl"):
    import json

    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]'''

DEMO_HACK = '''def quick_hack_for_demo():
    # TODO remove after the farmers market
    return [create_order("demo", ["concha"] * 3) for _ in range(5)]'''

SYNC_HEAD = '''"""Send the day's orders to the accountant."""

import ftplib
import json'''

FTP = '''def legacy_ftp_upload(orders, host="ftp.contador.example", user="panaderia"):
    """Upload orders as JSON to the accountant's FTP server. The password lives in ~/.netrc."""
    payload = json.dumps(orders).encode()
    with ftplib.FTP(host) as ftp:
        ftp.login(user)
        ftp.cwd("/incoming")
        ftp.storbinary("STOR orders.json", io.BytesIO(payload))
    return len(orders)'''

RETRY = '''def retry_forever(fn, *args):
    """If the accountant's server is down, just keep trying. It always comes back."""
    while True:
        try:
            return fn(*args)
        except Exception:
            time.sleep(1)'''

BACKOFF = '''def upload_with_backoff(fn, *args, attempts=5):
    """Try a few times, waiting longer each time, then give up and tell someone."""
    for attempt in range(attempts):
        try:
            return fn(*args)
        except OSError:
            time.sleep(2**attempt)
    raise RuntimeError(f"upload failed after {attempts} attempts")'''

SHEETS = '''def push_orders_to_sheet(orders, sheet_id="panaderia-2024"):
    """The accountant reads a shared spreadsheet now."""
    rows = [[o["day"], o["customer"], len(o["items"])] for o in orders]
    return {"sheet": sheet_id, "rows": rows}'''

FAX = '''def fax_order_to_kitchen(order, number="+52-55-5555-0100"):
    """The kitchen has a fax machine. Yes, in 2020."""
    sheet = [f"ORDER FOR {order['customer'].upper()}"]
    sheet += [f"  [ ] {item}" for item in order["items"]]
    sheet.append(f"TOTAL ${order_total(order)}")
    return send_fax(number, "\\n".join(sheet))


def send_fax(number, text):
    raise NotImplementedError("plug in the modem")'''

TABLET = '''def post_order_to_tablet(order, url="http://cocina.local/orders"):
    """The kitchen tablet shows each new order as a card."""
    body = json.dumps({"customer": order["customer"], "items": order["items"]}).encode()
    return urllib.request.urlopen(urllib.request.Request(url, data=body, method="POST"))'''

CART_V1 = """// The little cart on panaderia.example

const PRICES = { concha: 12, "pan de muerto": 45, bolillo: 4, cuerno: 15 };

function calcCartTotalOld(cart) {
  var total = 0;
  for (var i = 0; i < cart.length; i++) {
    total = total + PRICES[cart[i].name] * cart[i].qty;
  }
  return total;
}

function renderCart(cart) {
  document.querySelector("#total").textContent = "$" + calcCartTotalOld(cart);
}
"""

CART_V2 = """// The little cart on panaderia.example

export const PRICES = { concha: 12, "pan de muerto": 45, bolillo: 4, cuerno: 15 };

export const calcCartTotal = (cart) =>
  cart.reduce((sum, line) => sum + PRICES[line.name] * line.qty, 0);

export function renderCart(cart) {
  document.querySelector("#total").textContent = `$${calcCartTotal(cart)}`;
}
"""

DISCOUNT_V2 = """
// Buy 3 conchas, get 1 free. Counter staff: see the laminated sign.
export function getDiscountV2(cart) {
  const conchas = cart.filter((line) => line.name === "concha");
  const count = conchas.reduce((n, line) => n + line.qty, 0);
  return Math.floor(count / 4) * PRICES.concha;
}
"""

INVOICE_XML = '''"""Invoices (facturas) for the cafés that buy wholesale."""

from xml.etree import ElementTree as ET


class XmlInvoiceBuilder:
    """Builds the XML the old invoicing portal wanted. Do not touch the namespace."""

    NS = "http://facturas.example/cfd/3"

    def __init__(self, order):
        self.order = order

    def build(self):
        root = ET.Element("Comprobante", xmlns=self.NS)
        for item in self.order["items"]:
            ET.SubElement(root, "Concepto", Descripcion=item)
        return ET.tostring(root, encoding="unicode")
'''

INVOICE_JSON = '''"""Invoices (facturas) for the cafés that buy wholesale."""

import json


def build_invoice_json(order, version="4.0"):
    concepts = [{"descripcion": item} for item in order["items"]]
    return json.dumps({"version": version, "conceptos": concepts}, ensure_ascii=False)
'''

OVEN_V1 = """package main

import (
\t"fmt"
\t"time"
)

func preheatLegacy(target int) {
\tfor temp := 20; temp < target; temp += 15 {
\t\tfmt.Printf("oven: %d°C\\n", temp)
\t\ttime.Sleep(time.Second)
\t}
}

func main() {
\tpreheatLegacy(220)
}
"""

OVEN_V2 = """package main

import "fmt"

func readThermometer() int {
\treturn 220 // the new oven reports its own temperature over serial
}

func main() {
\tfmt.Printf("oven: %d°C\\n", readThermometer())
}
"""

README_V1 = """# La Panadería del Barrio

Orders, receipts and the nightly sync for our neighbourhood bakery.

## Nightly sync

At 2am, cron runs `legacy_ftp_upload()` to send the day's orders to our accountant.
"""

INVOICE_DOC = """# Invoices

Wholesale invoices are built by `XmlInvoiceBuilder` in `bakery/invoices.py`.
Ask Dev before changing the namespace.
"""


def py(*parts: str) -> str:
    return "\n\n\n".join(parts) + "\n"


def cron(ftp_import: bool, retry: str, extra: str = "") -> str:
    names = ", ".join(n for n in (("legacy_ftp_upload" if ftp_import else ""), retry) if n)
    return f'''"""Run by cron at 2am."""

import os

from .orders import load_today
from .sync import {names}


def nightly():
    orders = load_today()
{extra}'''


# (date, author, message, {path: content or None to delete})
TIMELINE = [
    ("2019-02-11T09:12:00-06:00", "rosa", "Open the bakery: orders, receipts and the nightly FTP sync", {
        "README.md": README_V1,
        "bakery/__init__.py": "",
        "bakery/orders.py": py(ORDERS_HEAD, CREATE_ORDER, ORDER_TOTAL_V1, DOT_MATRIX),
        "bakery/sync.py": py(SYNC_HEAD, FTP),
    }),
    ("2019-06-03T18:40:00-06:00", "tomas", "Add pricing helpers", {
        "bakery/pricing.py": py('"""Prices and discounts."""', "def apply_discount(total, percent):\n    return total - total * percent / 100", "def round_to_peso(amount):\n    return int(amount + 0.5)"),
    }),
    ("2019-10-20T07:05:00-06:00", "rosa", "Pan de muerto season is here", {
        "bakery/orders.py": py(ORDERS_HEAD, CREATE_ORDER, ORDER_TOTAL_V1, DOT_MATRIX, SEASON),
    }),
    ("2020-04-02T11:30:00-06:00", "mina", "Send orders to the kitchen by fax", {
        "bakery/kitchen.py": py('"""Tell the kitchen what to bake."""\n\nfrom .orders import order_total', FAX),
    }),
    ("2020-08-01T16:20:00-06:00", "tomas", "Oven thermometer reader", {"tools/oven/main.go": OVEN_V1}),
    ("2020-11-10T10:00:00-06:00", "tomas", "order_total now includes IVA", {
        "bakery/orders.py": py(ORDERS_HEAD, CREATE_ORDER, ORDER_TOTAL_V2, DOT_MATRIX, SEASON),
    }),
    ("2021-03-15T08:45:00-06:00", "mina", "The kitchen got a tablet. Goodbye, fax machine", {
        "bakery/kitchen.py": py('"""Tell the kitchen what to bake."""\n\nimport json\nimport urllib.request', TABLET),
    }),
    ("2021-06-01T21:10:00-06:00", "dev", "Add a cart to the website", {"web/cart.js": CART_V1}),
    ("2021-07-19T02:55:00-06:00", "tomas", "Retry the upload until it works", {
        "bakery/sync.py": py(SYNC_HEAD + "\nimport time", FTP, RETRY),
        "bakery/orders.py": py(ORDERS_HEAD, CREATE_ORDER, ORDER_TOTAL_V2, DOT_MATRIX, SEASON, LOAD_TODAY),
        "bakery/cron.py": cron(True, "retry_forever", "    retry_forever(legacy_ftp_upload, orders)\n"),
    }),
    ("2022-01-08T04:12:00-06:00", "tomas", "fix: retry_forever caused the 3am outage (it never gave up)", {
        "bakery/sync.py": py(SYNC_HEAD + "\nimport time", FTP, BACKOFF),
        "bakery/cron.py": cron(True, "upload_with_backoff", "    upload_with_backoff(legacy_ftp_upload, orders)\n"),
    }),
    ("2022-05-30T19:00:00-06:00", "dev", "Rewrite the cart with ES modules", {"web/cart.js": CART_V2}),
    ("2022-09-12T12:00:00-06:00", "dev", "Invoices for wholesale customers", {
        "bakery/invoices.py": INVOICE_XML,
        "docs/invoices.md": INVOICE_DOC,
    }),
    ("2023-02-14T09:00:00-06:00", "rosa", "The dot-matrix printer finally died. We held a small ceremony", {
        "bakery/orders.py": py(ORDERS_HEAD, CREATE_ORDER, ORDER_TOTAL_V2, SEASON, LOAD_TODAY),
    }),
    ("2023-08-21T15:30:00-06:00", "tomas", "Move money helpers next to the prices", {
        "bakery/pricing.py": py('"""Prices and discounts."""', "def apply_discount(total, percent):\n    return total - total * percent / 100"),
        "bakery/money.py": py('"""Pesos and centavos."""', "def round_to_peso(amount):\n    return int(amount + 0.5)"),
    }),
    ("2024-02-29T13:00:00-06:00", "tomas", "The new oven reports its own temperature; drop the fake preheat loop", {
        "tools/oven/main.go": OVEN_V2,
    }),
    ("2024-11-18T10:20:00-06:00", "tomas", "Remove FTP sync, nobody has used it since 2021", {
        "bakery/sync.py": py('"""Send the day\'s orders to the accountant."""\n\nimport time', BACKOFF, SHEETS),
        "bakery/cron.py": cron(
            True, "upload_with_backoff",
            "    upload_with_backoff(push_orders_to_sheet, orders)\n"
            "    if os.environ.get(\"FTP_FALLBACK\"):\n"
            "        legacy_ftp_upload(orders)\n",
        ).replace("from .sync import legacy_ftp_upload, upload_with_backoff", "from .sync import legacy_ftp_upload, push_orders_to_sheet, upload_with_backoff"),
    }),
    ("2025-03-02T17:00:00-06:00", "mina", "Quick hack for the farmers market demo", {
        "bakery/orders.py": py(ORDERS_HEAD, CREATE_ORDER, ORDER_TOTAL_V2, SEASON, LOAD_TODAY, DEMO_HACK),
    }),
    ("2025-03-03T09:15:00-06:00", "mina", "Remove the demo hack", {
        "bakery/orders.py": py(ORDERS_HEAD, CREATE_ORDER, ORDER_TOTAL_V2, SEASON, LOAD_TODAY),
    }),
    ("2025-06-10T11:00:00-06:00", "dev", "Migrate invoices to JSON (CFDI 4.0)", {"bakery/invoices.py": INVOICE_JSON}),
    ("2026-10-01T08:00:00-06:00", "dev", "Discount v2: buy 3 conchas, get 1 free", {"web/cart.js": CART_V2 + DISCOUNT_V2}),
    ("2026-10-20T18:30:00-06:00", "dev", "Revert discount v2, it confused everyone at the counter", {"web/cart.js": CART_V2}),
]


def git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        check=True, capture_output=True, env=env,
    )


def build(dest: str | Path) -> Path:
    repo = Path(dest)
    if repo.exists() and any(repo.iterdir()):
        raise SystemExit(f"{repo} is not empty")
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    for when, who, message, files in TIMELINE:
        for path, content in files.items():
            target = repo / path
            if content is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        name, email = PEOPLE[who]
        env = os.environ | {
            "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": when,
        }
        git(repo, "add", "-A", env=env)
        git(repo, "commit", "-q", "-m", message, env=env)
    return repo


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(build(sys.argv[1]))
