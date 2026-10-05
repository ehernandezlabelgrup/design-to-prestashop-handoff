#!/usr/bin/env python3
"""Busca en el HTML de diseño los datos de demostración (productos, categorías, filtros,
pedidos de ejemplo…) que viven como variables globales de JavaScript y los vuelca a
demo-candidates.json. El modelo los revisa y los transforma en demo-data.json (ver
reference/demo-data-schema.md).

Solo ve variables globales (`var` y funciones); si el diseño usa const/let dentro de un
módulo o closure, hay que leer el fuente. Úsalo SOLO si el usuario ha pedido datos demo.

Uso: find_demo_data.py --entry /ruta/index.html --out ./work
"""
import argparse
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

SETTLE_MS = 800
MAX_ITEMS = 200
MAX_JSON_CHARS = 60000

FIND_JS = r"""
(maxItems) => {
  const frame = document.createElement('iframe');
  document.body.appendChild(frame);
  const builtin = new Set(Object.getOwnPropertyNames(frame.contentWindow));
  frame.remove();
  const safe = v => { try { return JSON.parse(JSON.stringify(v)); } catch (e) { return null; } };
  const out = {};
  for (const name of Object.getOwnPropertyNames(window)) {
    if (builtin.has(name)) continue;
    let v; try { v = window[name]; } catch (e) { continue; }
    if (typeof v === 'function' || v instanceof Node || v === window || v === null) continue;
    if (Array.isArray(v) && v.length) {
      out[name] = { kind: 'array', length: v.length, itemType: typeof v[0],
        keys: v[0] && typeof v[0] === 'object' ? Object.keys(v[0]) : null, data: safe(v.slice(0, maxItems)) };
    } else if (typeof v === 'object') {
      const keys = Object.keys(v);
      if (keys.length) out[name] = { kind: 'object', keys: keys.slice(0, 40), data: safe(v) };
    }
  }
  return out;
}
"""


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entry", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if not args.entry.is_file():
        sys.exit(f"No existe {args.entry}")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(args.entry.parent)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/{args.entry.name}", wait_until="domcontentloaded")
        page.wait_for_timeout(SETTLE_MS)
        found = page.evaluate(FIND_JS, MAX_ITEMS)
        browser.close()
    server.shutdown()

    for name, info in found.items():
        text = json.dumps(info.get("data"), ensure_ascii=False)
        if len(text) > MAX_JSON_CHARS:
            info["data"] = f"(recortado: {len(text)} caracteres; leer el fuente)"
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "demo-candidates.json").write_text(json.dumps(found, indent=1, ensure_ascii=False))
    size = lambda info: info["length"] if info["kind"] == "array" else len(info["keys"])
    summary = ", ".join(f"{n}[{size(i)}]" for n, i in found.items()) or "ninguna"
    print(f"OK · variables globales con datos: {summary}")


if __name__ == "__main__":
    main()
