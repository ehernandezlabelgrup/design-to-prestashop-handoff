#!/usr/bin/env python3
"""Analiza un HTML de diseño (estático o SPA con rutas hash) y escribe los JSON
intermedios que la skill usa para redactar el handoff.

Uso:
  analyze.py --entry /ruta/index.html --out ./work [--routes inicio,tienda]
             [--viewports 1440x900,390x844]

Salida en --out:
  raw-tokens.json   colores, tipografías, espaciados, radios, sombras, movimiento
  structure.json    rutas, secciones, landmarks, componentes repetidos, estados
  content/<ruta>.html  texto de las páginas de contenido/legales (limpio, para sembrar el CMS)
  image-usage.json  uso real de cada imagen (tamaño renderizado, natural, contexto) por ruta y ancho
  texts.json        textos visibles y atributos (alt, placeholder, aria-label, title) por ruta
  inline-styles.json  estilos en línea del fuente (hay que convertirlos a clases)
  renders/          capturas de página completa por ruta y viewport
"""
import argparse
import json
import re
import sys
import threading
from collections import Counter
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_VIEWPORTS = "1440x900,390x844"
SETTLE_MS = 600
ROUTE_LINK_RE = re.compile(r'href=["\']#/?([A-Za-z0-9_\-/]+)["\']')

# JS que se ejecuta dentro de la página: agrega estilos calculados y estructura.
COLLECT_JS = r"""
() => {
  const bump = (m, k) => { if (k) m[k] = (m[k] || 0) + 1; };
  const out = { colors:{}, backgrounds:{}, fontFamilies:{}, fontSizes:{}, fontWeights:{},
    lineHeights:{}, letterSpacings:{}, paddings:{}, gaps:{}, radii:{}, shadows:{},
    transitions:{}, borders:{}, inlineStyleCount:0, h1Count:0, imgNoDims:0, smallTargets:[] };
  const skip = new Set(['SCRIPT','STYLE','LINK','META','HEAD','NOSCRIPT','TITLE']);
  const all = [...document.body.querySelectorAll('*')].filter(e => !skip.has(e.tagName));
  const norm = v => (v || '').trim();
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (el.getAttribute('style')) out.inlineStyleCount++;
    if (el.textContent && el.children.length === 0 && el.textContent.trim()) {
      bump(out.colors, cs.color);
      bump(out.fontFamilies, cs.fontFamily);
      bump(out.fontSizes, cs.fontSize);
      bump(out.fontWeights, cs.fontWeight);
      bump(out.lineHeights, cs.lineHeight);
      if (cs.letterSpacing !== 'normal') bump(out.letterSpacings, cs.letterSpacing);
    }
    const bg = cs.backgroundColor;
    if (bg && bg !== 'rgba(0, 0, 0, 0)') bump(out.backgrounds, bg);
    for (const p of ['paddingTop','paddingRight','paddingBottom','paddingLeft'])
      if (cs[p] !== '0px') bump(out.paddings, cs[p]);
    if (cs.gap && cs.gap !== 'normal' && cs.gap !== '0px') bump(out.gaps, cs.gap);
    if (cs.borderTopLeftRadius !== '0px') bump(out.radii, cs.borderTopLeftRadius);
    if (cs.boxShadow !== 'none') bump(out.shadows, cs.boxShadow);
    if (cs.borderTopWidth !== '0px' && cs.borderTopStyle !== 'none')
      bump(out.borders, cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor);
    if (cs.transitionDuration && cs.transitionDuration !== '0s')
      bump(out.transitions, cs.transitionProperty + ' ' + cs.transitionDuration + ' ' + cs.transitionTimingFunction);
    if (el.tagName === 'IMG' && (!el.getAttribute('width') || !el.getAttribute('height'))
        && !cs.aspectRatio.includes('/') ) out.imgNoDims++;
    if (['A','BUTTON','INPUT','SELECT'].includes(el.tagName)) {
      const r = el.getBoundingClientRect();
      if (r.width && r.height && (r.width < 44 || r.height < 44) && out.smallTargets.length < 25)
        out.smallTargets.push({ tag: el.tagName, cls: el.className && String(el.className).slice(0,60),
          w: Math.round(r.width), h: Math.round(r.height) });
    }
  }
  out.h1Count = document.querySelectorAll('h1').length;

  const sig = el => el.tagName.toLowerCase() + '.' + [...el.classList].sort().join('.');
  const groups = {};
  for (const el of all) {
    if (el.children.length === 0) continue;
    const s = sig(el);
    (groups[s] = groups[s] || []).push(el);
  }
  const components = Object.entries(groups)
    .filter(([s, els]) => els.length >= 3 && els[0].classList.length > 0 && els[0].querySelectorAll('*').length >= 2)
    .map(([s, els]) => ({ signature: s, count: els.length, sampleHtml: els[0].outerHTML.slice(0, 400) }))
    .sort((a, b) => b.count - a.count).slice(0, 25);

  const landmarks = [...document.querySelectorAll('header,nav,main,footer,aside,section,[role]')]
    .map(e => ({ tag: e.tagName.toLowerCase(), id: e.id || null, role: e.getAttribute('role'),
      label: e.getAttribute('aria-label') || e.getAttribute('aria-labelledby'),
      cls: e.className && String(e.className).slice(0, 60),
      heading: (e.querySelector('h1,h2,h3') || {}).textContent?.trim().slice(0, 80) || null }));

  const images = [...document.querySelectorAll('img')].map(i => i.getAttribute('src')).filter(Boolean);
  const actions = [...document.querySelectorAll('[data-a]')].map(e => e.getAttribute('data-a'));
  // Uso real de cada imagen (img y background-image): tamaño renderizado y natural.
  const urlOf = v => { const m = /url\(["']?([^"')]+)["']?\)/.exec(v || ''); return m ? m[1] : null; };
  const ctxOf = e => { const p = e.parentElement; if (!p) return ''; const c = (p.className && typeof p.className === 'string') ? '.' + p.className.trim().split(/\s+/).join('.') : ''; return (p.tagName.toLowerCase() + c).slice(0, 80); };
  const imageUsage = [];
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (el.tagName === 'IMG' && el.getAttribute('src'))
      imageUsage.push({ kind: 'img', src: el.getAttribute('src'), w: Math.round(r.width), h: Math.round(r.height),
        nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, ctx: ctxOf(el), alt: el.getAttribute('alt') });
    const bg = urlOf(cs.backgroundImage);
    if (bg && !bg.startsWith('data:')) imageUsage.push({ kind: 'bg', src: bg, w: Math.round(r.width), h: Math.round(r.height),
        nw: 0, nh: 0, fit: cs.backgroundSize, ctx: ctxOf(el), alt: null });
  }
  // Textos visibles y atributos con texto: todos deben pasar por el sistema de traducciones.
  const texts = new Set();
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none') continue;
    if (el.children.length === 0 && /\p{L}/u.test(el.textContent)) texts.add('text|' + el.textContent.trim().replace(/\s+/g, ' ').slice(0, 1000));
    for (const a of ['placeholder','alt','title','aria-label'])
      if (el.getAttribute(a)) texts.add(a + '|' + el.getAttribute(a).trim().slice(0, 200));
  }
  return { stats: out, components, landmarks, images: [...new Set(images)], texts: [...texts], imageUsage,
           actions: [...new Set(actions)], title: document.title,
           docHeight: document.documentElement.scrollHeight };
}
"""

# JS: reglas CSS accesibles (mismo origen): variables, media queries, keyframes, hover.
SHEETS_JS = r"""
() => {
  const res = { rootVars:{}, media:[], keyframes:[], hover:[], focus:[], fonts:[], blocked:0 };
  const walk = rules => { for (const r of rules) {
    if (r.type === CSSRule.STYLE_RULE) {
      if (r.selectorText === ':root') for (const p of r.style) if (p.startsWith('--')) res.rootVars[p] = r.style.getPropertyValue(p).trim();
      if (/:hover/.test(r.selectorText)) res.hover.push(r.cssText.slice(0, 220));
      if (/:focus/.test(r.selectorText)) res.focus.push(r.cssText.slice(0, 220));
    } else if (r.type === CSSRule.MEDIA_RULE) { res.media.push(r.conditionText); walk(r.cssRules); }
    else if (r.type === CSSRule.KEYFRAMES_RULE) res.keyframes.push(r.name);
    else if (r.type === CSSRule.FONT_FACE_RULE) res.fonts.push(r.style.getPropertyValue('font-family'));
  }};
  for (const sh of document.styleSheets) { try { walk(sh.cssRules); } catch (e) { res.blocked++; } }
  res.fontLinks = [...document.querySelectorAll('link[href*="fonts.g"]')].map(l => l.href);
  return res;
}
"""


# JS: localiza el logo (img de la cabecera o SVG en línea).
LOGO_JS = r"""
() => {
  const sels = ['header img[alt*="logo" i]', 'header a[href="#/inicio"] img', 'header [class*="logo" i] img',
                'img[src*="logo" i]', 'header img'];
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    return { kind: 'img', src: el.getAttribute('src'), alt: el.getAttribute('alt'),
             width: Math.round(r.width), height: Math.round(r.height) };
  }
  const svg = document.querySelector('header a svg, header [class*="logo" i] svg');
  if (svg) { const r = svg.getBoundingClientRect();
    return { kind: 'svg', markup: svg.outerHTML, width: Math.round(r.width), height: Math.round(r.height) }; }
  return null;
}
"""

# JS: extrae el texto de la página como HTML limpio (sin clases, estilos ni controles).
CONTENT_JS = r"""
() => {
  const KEEP = new Set(['H1','H2','H3','H4','H5','H6','P','UL','OL','LI','A','STRONG','EM','B','I','BR',
    'TABLE','THEAD','TBODY','TR','TH','TD','BLOCKQUOTE']);
  const DROP = new Set(['HEADER','FOOTER','NAV','SCRIPT','STYLE','SVG','BUTTON','FORM','INPUT','SELECT','TEXTAREA','IMG']);
  const walk = node => {
    if (node.nodeType === 3) return node.textContent.replace(/\s+/g, ' ');
    if (node.nodeType !== 1 || DROP.has(node.tagName)) return '';
    const inner = [...node.childNodes].map(walk).join('');
    if (!KEEP.has(node.tagName)) return inner;
    if (node.tagName === 'BR') return '<br>';
    const href = node.tagName === 'A' && node.getAttribute('href') ? ' href="' + node.getAttribute('href') + '"' : '';
    return '<' + node.tagName.toLowerCase() + href + '>' + inner.trim() + '</' + node.tagName.toLowerCase() + '>\n';
  };
  const root = document.querySelector('main') || document.getElementById('app') || document.body;
  return walk(root).replace(/\n{3,}/g, '\n\n').trim();
}
"""

CONTENT_ROUTE_RE = re.compile(r"legal|privacy|privacidad|cookie|terms|condicion|aviso|politic|envio|devoluc|shipping|returns|faq|sobre|about", re.I)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def start_server(root: Path):
    handler = partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def detect_routes(entry_text: str, explicit: list) -> list:
    if explicit:
        return explicit
    found = [m for m in ROUTE_LINK_RE.findall(entry_text) if m.strip("/") and not m.endswith("/")]
    return sorted(set(found)) or [""]


def find_inline_styles(entry_text: str) -> dict:
    # Estilos en línea del fuente (incluye los generados por plantillas JS).
    values = re.findall(r'style=\\?["\']([^"\']{3,300})', entry_text)
    props = Counter()
    for v in values:
        for decl in v.split(";"):
            if ":" in decl:
                props[decl.split(":")[0].strip()] += 1
    return {"count": len(values), "samples": values[:40], "propertyFrequency": props.most_common(40)}


def merge_counters(target: dict, source: dict):
    for key, counter in source.items():
        if isinstance(counter, dict):
            bucket = target.setdefault(key, {})
            for k, v in counter.items():
                bucket[k] = bucket.get(k, 0) + v


def analyze(entry: Path, out: Path, routes: list, viewports: list, content_re=CONTENT_ROUTE_RE):
    out.mkdir(parents=True, exist_ok=True)
    (out / "renders").mkdir(exist_ok=True)
    (out / "content").mkdir(exist_ok=True)
    logo = None
    entry_text = entry.read_text(encoding="utf-8", errors="replace")
    route_list = detect_routes(entry_text, routes)
    server = start_server(entry.parent)
    base = f"http://127.0.0.1:{server.server_address[1]}/{entry.name}"
    tokens, structure, texts = {"viewports": {}}, {"routes": {}}, {}
    image_usage = {}
    console_errors = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        for vw in viewports:
            width, height = (int(x) for x in vw.split("x"))
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
            page.on("pageerror", lambda e: console_errors.append(str(e)[:200]))
            agg = {}
            for route in route_list:
                url = f"{base}#/{route}" if route else base
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(SETTLE_MS)
                label = route or "index"
                page.screenshot(path=str(out / "renders" / f"{label.replace('/', '_')}-{width}.png"),
                                full_page=True)
                data = page.evaluate(COLLECT_JS)
                if logo is None:
                    logo = page.evaluate(LOGO_JS)
                if content_re.search(route) and width == max(int(v.split("x")[0]) for v in viewports):
                    html = page.evaluate(CONTENT_JS)
                    (out / "content" / f"{label.replace('/', '_')}.html").write_text(html + "\n", encoding="utf-8")
                merge_counters(agg, data["stats"])
                image_usage.setdefault(label, {})[str(width)] = data["imageUsage"]
                for entry_text_item in data["texts"]:
                    kind, _, value = entry_text_item.partition("|")
                    texts.setdefault(label, {}).setdefault(value, set()).add(kind)
                structure["routes"].setdefault(label, {})[str(width)] = {
                    k: data[k] for k in ("title", "landmarks", "components", "images", "actions", "docHeight")}
                structure["routes"][label][str(width)]["audit"] = {
                    k: data["stats"][k] for k in ("h1Count", "imgNoDims", "smallTargets", "inlineStyleCount")}
            tokens["viewports"][str(width)] = agg
            if width == max(int(v.split("x")[0]) for v in viewports):
                tokens["stylesheets"] = page.evaluate(SHEETS_JS)
            context.close()
        browser.close()
    server.shutdown()

    structure["logo"] = logo
    tokens["consoleErrors"] = sorted(set(console_errors))
    (out / "raw-tokens.json").write_text(json.dumps(tokens, indent=1, ensure_ascii=False))
    (out / "structure.json").write_text(json.dumps(structure, indent=1, ensure_ascii=False))
    (out / "image-usage.json").write_text(json.dumps(image_usage, indent=1, ensure_ascii=False))
    (out / "texts.json").write_text(json.dumps(
        {route: [{"text": t, "kinds": sorted(k)} for t, k in items.items()] for route, items in texts.items()},
        indent=1, ensure_ascii=False))
    (out / "inline-styles.json").write_text(
        json.dumps(find_inline_styles(entry_text), indent=1, ensure_ascii=False))
    return route_list


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--entry", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--routes", default="", help="rutas hash separadas por coma (auto-detecta si se omite)")
    ap.add_argument("--viewports", default=DEFAULT_VIEWPORTS)
    ap.add_argument("--content-routes", default="", help="regex de rutas de contenido/legales a exportar (por defecto: legal, privacidad, cookies, condiciones, envíos, faq, sobre…)")
    args = ap.parse_args()
    if not args.entry.is_file():
        sys.exit(f"No existe el HTML de entrada: {args.entry}")
    routes = [r for r in args.routes.split(",") if r]
    content_re = re.compile(args.content_routes, re.I) if args.content_routes else CONTENT_ROUTE_RE
    done = analyze(args.entry.resolve(), args.out, routes, args.viewports.split(","), content_re)
    print(f"OK · rutas analizadas: {', '.join(r or 'index' for r in done)} · salida: {args.out}")


if __name__ == "__main__":
    main()
