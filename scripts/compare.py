#!/usr/bin/env python3
"""Valida UNA página maquetada en PrestaShop contra el diseño del handoff.

Uso (página completa):
  compare.py --handoff ./handoff-tienda --route inicio --url https://local.test/ [--viewports 1440x900,390x844]

Uso (un elemento o componente suelto, para ir elemento por elemento):
  compare.py --handoff ./handoff-tienda --route tienda --url https://local.test/tienda \
             --element tarjeta-producto --design-selector ".ix" --live-selector ".product-miniature"
  Renderiza el diseño de origen en vivo, captura ese elemento en los dos lados y los compara.

Hace capturas de la página real, las compara con renders/<ruta>-<ancho>.png (lado a lado
y diferencia) y comprueba reglas automáticas. Escribe validation/<ruta>-informe.md y
la revisión visual final sigue siendo humana.
"""
import argparse
import os
import re
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright

def new_page(browser, width, height, live=True, session=True):
    """Página de comprobación. La del sitio en vivo usa HANDOFF_STORAGE_STATE si existe (sesión con cesta o cliente identificado,
    para páginas de cesta, pago y cuenta); la del diseño estático, nunca."""
    state = os.environ.get("HANDOFF_STORAGE_STATE")
    if live and session and state and Path(state).is_file():
        return browser.new_context(storage_state=state, viewport={"width": width, "height": height}).new_page()
    return browser.new_page(viewport={"width": width, "height": height})

DEFAULT_VIEWPORTS = "1440x900,390x844"
SETTLE_MS = 800
DIFF_WARN_PCT = 8.0

CHECKS_JS = r"""
() => {
  // <html> y <body> reciben estilos en línea de scripts del tema base (p. ej. --scroll-padding-top): no son de nuestras plantillas
  const styled = [...document.querySelectorAll('[style]')].filter(e => e !== document.documentElement && e !== document.body && (e.getAttribute('style') || '').trim() !== '').map(e => e.tagName.toLowerCase() + ':' + (e.getAttribute('style') || '').slice(0, 80));
  // el header y el footer son los mismos en todo el sitio: no se cuentan aquí (design_review.py comprueba que sean iguales en todas las páginas)
  const small = [...document.querySelectorAll('a,button,input,select')].filter(e => {
    if (e.closest('header, footer, #header, #footer')) return false;
    // no son objetivos táctiles: los enlaces «saltar al contenido / volver arriba» (invisibles, solo teclado) y los enlaces dentro de texto (migas, «Ver todo»…; excepción de WCAG 2.5.8)
    if (e.matches('.visually-hidden-focusable, .visually-hidden, .skip-link, .back-to-top-link') || (e.tagName === 'A' && getComputedStyle(e).display === 'inline')) return false;
    const r = e.getBoundingClientRect(); return r.width && r.height && (r.width < 44 || r.height < 44); }).length;
  const noDims = [...document.querySelectorAll('img')].filter(i => !i.getAttribute('width') && !i.getAttribute('height')
    && !getComputedStyle(i).aspectRatio.includes('/')).length;
  const noAlt = [...document.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).length;
  return { inlineStyles: styled.length, inlineSamples: styled.slice(0, 8),
    styleBlocks: document.querySelectorAll('body style').length,
    h1: document.querySelectorAll('h1').length, smallTargets: small, imgNoDims: noDims, imgNoAlt: noAlt,
    customCss: getComputedStyle(document.documentElement).getPropertyValue('--custom-css-loaded').trim() === '1'
      || [...document.querySelectorAll('link[rel=stylesheet]')].map(l => l.href).some(h => /custom\.css/.test(h)),
    lastCss: ([...document.querySelectorAll('link[rel=stylesheet]')].pop() || {}).href || '' };
}
"""


def diff_percent(design: Image.Image, live: Image.Image) -> tuple:
    width = design.width
    live = live.resize((width, round(live.height * width / live.width)))
    height = min(design.height, live.height)
    a, b = design.convert("RGB").crop((0, 0, width, height)), live.convert("RGB").crop((0, 0, width, height))
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 40 else 0)
    pct = 100 * sum(1 for v in diff.getdata() if v) / (width * height)
    return pct, a, b, diff


def side_by_side(a: Image.Image, b: Image.Image, diff: Image.Image) -> Image.Image:
    canvas = Image.new("RGB", (a.width * 3 + 40, a.height), "white")
    for index, img in enumerate((a, b, diff.convert("RGB"))):
        canvas.paste(img, (index * (a.width + 20), 0))
    return canvas


def run_checks(data: dict, console_errors: list) -> list:
    rows = [
        ("Sin estilo en línea", data["inlineStyles"] == 0, f"{data['inlineStyles']} elementos con style"),
        ("Sin <style> en el body", data["styleBlocks"] == 0, f"{data['styleBlocks']} bloques"),
                ("custom.css cargado (marcador --custom-css-loaded)", data["customCss"],
         "añade `:root { --custom-css-loaded: 1; }` al principio de custom.css; con CCC el archivo va dentro del bundle y no se ve como enlace"),
        ("Un solo H1", data["h1"] == 1, f"{data['h1']} H1"),
        ("Imágenes con dimensiones o aspect-ratio", data["imgNoDims"] == 0, f"{data['imgNoDims']} sin"),
        ("Imágenes con alt", data["imgNoAlt"] == 0, f"{data['imgNoAlt']} sin alt"),
        ("Objetivos táctiles ≥ 44 px", data["smallTargets"] == 0, f"{data['smallTargets']} más pequeños"),
        ("Sin errores de consola", not console_errors, "; ".join(console_errors[:3])),
    ]
    return rows


def write_report(handoff: Path, route: str, url: str, sections: list):
    out = handoff / "validation"
    out.mkdir(exist_ok=True)
    lines = [f"# Validación · {route}", "", f"URL: {url}", ""]
    for title, rows, extra in sections:
        lines += [f"## {title}", "", "| Comprobación | Resultado | Detalle |", "|---|---|---|"]
        lines += [f"| {n} | {'✅' if ok else '❌'} | {'' if ok else d} |" for n, ok, d in rows]
        lines += ["", extra, ""]
    lines += ["## Revisión humana pendiente", "",
              "- [ ] Se parece al diseño (mira la imagen lado a lado)", "- [ ] Todos los textos vienen de traducciones (cambia de idioma y comprueba)",
              "- [ ] Interacciones y estados según `docs/03`", "- [ ] Sin regresiones en otras páginas", ""]
    (out / f"{route.replace('/', '_')}-informe.md").write_text("\n".join(lines), encoding="utf-8")


ELEMENT_CHECKS_JS = r"""
(el) => {
  const styled = [el, ...el.querySelectorAll('[style]')].filter(e => e.getAttribute && e.getAttribute('style'));
  const small = [...el.querySelectorAll('a,button,input,select')].filter(e => {
    const r = e.getBoundingClientRect(); return r.width && r.height && (r.width < 44 || r.height < 44); }).length;
  const noAlt = [...el.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).length;
  return { inlineStyles: styled.length, inlineSamples: styled.slice(0, 5).map(e => e.tagName.toLowerCase()),
           smallTargets: small, imgNoAlt: noAlt, h1: el.querySelectorAll('h1').length };
}
"""


def serve_design(handoff: Path):
    root = handoff / "design" / "source"
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def find_design_entry(handoff: Path) -> str:
    htmls = sorted((handoff / "design" / "source").glob("*.html"))
    return htmls[0].name if htmls else "index.html"


def element_rows(data: dict) -> list:
    return [
        ("Sin estilo en línea", data["inlineStyles"] == 0, f"{data['inlineStyles']} elementos con style"),
        ("Imágenes con alt", data["imgNoAlt"] == 0, f"{data['imgNoAlt']} sin alt"),
        ("Objetivos táctiles ≥ 44 px", data["smallTargets"] == 0, f"{data['smallTargets']} más pequeños"),
    ]


def run_element(args):
    out = args.handoff / "validation"
    out.mkdir(exist_ok=True)
    design_server = serve_design(args.handoff)
    design_url = f"http://127.0.0.1:{design_server.server_address[1]}/{find_design_entry(args.handoff)}#/{args.route}"
    sections, all_ok = [], True
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        for vw in args.viewports.split(","):
            width, height = (int(x) for x in vw.split("x"))
            shots = {}
            for side, url, selector in (("design", design_url, args.design_selector), ("live", args.url, args.live_selector)):
                page = new_page(browser, width, height, live=(side == "live"), session=not args.no_session)
                page.goto(url, wait_until="load")
                page.wait_for_timeout(SETTLE_MS)
                target = page.locator(selector).first
                if target.count() == 0:
                    sys.exit(f"No encuentro «{selector}» en {side} ({url})")
                path = out / f"{args.element}-{width}-{side}.png"
                target.screenshot(path=str(path))
                shots[side] = path
                if side == "live":
                    rows = element_rows(target.evaluate(ELEMENT_CHECKS_JS))
                page.close()
            pct, a, b, diff = diff_percent(Image.open(shots["design"]), Image.open(shots["live"]))
            side_by_side(a, b, diff).save(out / f"{args.element}-{width}-comparacion.png")
            rows.append(("Diferencia visual (informativa)" if not args.strict_visual else "Diferencia visual contenida", True if not args.strict_visual else pct <= DIFF_WARN_PCT, f"{pct:.1f}%"))
            extra = f"Diferencia: {pct:.1f}%. Imagen: `{args.element}-{width}-comparacion.png` (diseño | real | diferencia)."
            sections.append((f"{width} px", rows, extra))
            all_ok &= all(ok for _, ok, _ in rows)
        browser.close()
    design_server.shutdown()
    write_report(args.handoff, args.element, args.url, sections)
    print(f"{'OK' if all_ok else 'FALLOS'} · informe en {out / (args.element + '-informe.md')}")
    sys.exit(0 if all_ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--handoff", required=True, type=Path)
    ap.add_argument("--route", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--viewports", default=DEFAULT_VIEWPORTS)
    ap.add_argument("--strict-visual", action="store_true", help="la diferencia visual con el diseño falla la comprobación (por defecto es solo informativa: los datos de la demo nunca coinciden con los del diseño)")
    ap.add_argument("--no-session", action="store_true", help="ignora HANDOFF_STORAGE_STATE (páginas públicas: login y registro redirigen si hay sesión)")
    ap.add_argument("--element", help="nombre del elemento/componente a validar (modo elemento)")
    ap.add_argument("--design-selector", help="selector CSS del elemento en el diseño de origen")
    ap.add_argument("--live-selector", help="selector CSS del elemento en PrestaShop")
    args = ap.parse_args()
    if args.element:
        if not (args.design_selector and args.live_selector):
            sys.exit("--element exige --design-selector y --live-selector")
        run_element(args)
    out = args.handoff / "validation"
    out.mkdir(exist_ok=True)
    label = args.route.replace("/", "_")
    sections, errors_seen, all_ok = [], [], True

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        for vw in args.viewports.split(","):
            width, height = (int(x) for x in vw.split("x"))
            page = new_page(browser, width, height, session=not args.no_session)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)[:150]))
            page.goto(args.url, wait_until="load")
            page.wait_for_timeout(SETTLE_MS)
            live_path = out / f"{label}-{width}-live.png"
            page.screenshot(path=str(live_path), full_page=True)
            rows = run_checks(page.evaluate(CHECKS_JS), errors)
            design_path = args.handoff / "renders" / f"{label}-{width}.png"
            extra = f"No hay render de diseño en {design_path.name}."
            if design_path.is_file():
                pct, a, b, diff = diff_percent(Image.open(design_path), Image.open(live_path))
                side_by_side(a, b, diff).save(out / f"{label}-{width}-comparacion.png")
                extra = f"Diferencia de píxeles: {pct:.1f}% (aviso a partir de {DIFF_WARN_PCT}%). Imagen: `{label}-{width}-comparacion.png` (diseño | real | diferencia)."
                rows.append(("Diferencia visual (informativa)" if not args.strict_visual else "Diferencia visual contenida", True if not args.strict_visual else pct <= DIFF_WARN_PCT, f"{pct:.1f}%"))
            sections.append((f"{width} px", rows, extra))
            all_ok &= all(ok for _, ok, _ in rows)
            page.close()
        browser.close()

    write_report(args.handoff, args.route, args.url, sections)
    print(f"{'OK' if all_ok else 'FALLOS'} · informe en {out / (label + '-informe.md')}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
