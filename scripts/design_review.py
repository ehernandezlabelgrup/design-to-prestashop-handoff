#!/usr/bin/env python3
"""Revisión de diseño de la prueba final: compara con el diseño las páginas que no son de compra.

Recorre design/steps.json y, para cada paso de página con URL en vivo, lanza compare.py (1440 y 390 px). Agrupa el resultado en
estáticas (contenido y políticas), home, listado, ficha, búsqueda, 404 y acceso, y escribe validation/revision-diseno.md con una
fila por página (✅ / ⚠️ / ❌ y qué falla). Las páginas que dependen de sesión (cesta, pago, confirmación, cuenta, favoritos)
solo se revisan si existe HANDOFF_STORAGE_STATE; el resto las cubre e2e_checkout.py. La 404 se revisa contra el diseño si este
trae una ruta «404»; si no, se hace una auditoría mínima (hoja custom.css, un H1, cabecera y pie, sin estilos en línea) y se avisa.

Uso: design_review.py --url https://tienda.test --handoff ./handoff-tienda
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
GROUPS = [("Home", ("inicio",)), ("Listado", ("tienda",)), ("Ficha", ("producto",)), ("Búsqueda", ("buscar", "busqueda")),
          ("Acceso", ("login", "registro", "recuperar")), ("Compra", ("carrito", "checkout", "confirmacion")), ("Cuenta", ("cuenta",)),
          ("Estáticas", ("sobre", "envios", "faq", "contacto", "politicas", "legal", "terms", "privacidad", "cookies"))]
SESSION_ROUTES = ("carrito", "checkout", "confirmacion", "cuenta", "tienda/fav", "recuperar/nueva")


def group_of(route: str) -> str:
    for name, keys in GROUPS:
        if any(route == k or route.startswith(k + "/") or route.startswith(k) for k in keys):
            return name
    return "Otras"


def live_url(step: dict, base: str) -> str:
    parsed = urlparse(step.get("url", ""))
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    return base.rstrip("/") + (path or "/")


def run_page(handoff: Path, route: str, url: str) -> tuple:
    code = subprocess.run([sys.executable, str(HERE / "compare.py"), "--handoff", str(handoff), "--route", route, "--url", url],
                          capture_output=True, text=True).returncode
    report = handoff / "validation" / f"{route.replace('/', '_')}-informe.md"
    fails = []
    if report.is_file():
        fails = [re.sub(r"\s*\|\s*", " · ", line.strip("| ")) for line in report.read_text(encoding="utf-8").splitlines() if "❌" in line]
    return code, sorted(set(fails))


def fetch_text(url: str) -> str:
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310 - URL de la tienda que se revisa
            return response.read().decode("utf-8", "replace")
    except Exception as error:  # urllib lanza HTTPError también con 404, que sí trae cuerpo
        return error.read().decode("utf-8", "replace") if hasattr(error, "read") else ""


def footer_titles(html: str) -> list:
    """Títulos de columna del pie de página, en orden (el último <footer>; el pie debe ser igual en todas las páginas)."""
    blocks = re.findall(r"<footer\b.*?</footer>", html, re.S)
    if not blocks:
        return []
    titles = []
    for nav in re.findall(r"<nav\b.*?</nav>", blocks[-1], re.S):   # cada columna del pie es un <nav> con su título
        found = re.findall(r'class="[^"]*(?:title|heading)[^"]*"[^>]*>\s*([^<]+?)\s*<', nav) or re.findall(r"<h[2-6][^>]*>\s*([^<]+?)\s*</h[2-6]>", nav)
        titles.append(re.sub(r"\s+", " ", found[0]) if found else "")
    return titles


def audit_404(base: str) -> tuple:
    url = base.rstrip("/") + "/esta-pagina-no-existe-revision"
    try:
        with urlopen(url, timeout=30) as response:  # noqa: S310 - URL de la tienda que se revisa
            html, status = response.read().decode("utf-8", "replace"), response.status
    except Exception as error:  # urllib lanza HTTPError con el cuerpo de la 404
        html, status = (error.read().decode("utf-8", "replace") if hasattr(error, "read") else ""), getattr(error, "code", 0)
    problems = []
    if status != 404:
        problems.append(f"responde {status} y no 404")
    if not any("--custom-css-loaded" in fetch_text(urljoin(url, href)) for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)):
        problems.append("no carga custom.css (marcador --custom-css-loaded)")
    if len(re.findall(r"<h1\b", html)) != 1:
        problems.append("no tiene exactamente un H1")
    if re.search(r'<body[^>]*>.*?\sstyle="', html, re.S) and re.search(r'<(?!html|body)[a-z0-9]+\s[^>]*\sstyle="', html):
        problems.append("hay estilos en línea")
    return url, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="base de la tienda, sin barra final")
    ap.add_argument("--handoff", required=True, type=Path)
    args = ap.parse_args()
    steps = json.loads((args.handoff / "design" / "steps.json").read_text(encoding="utf-8"))["steps"]
    has_session = bool(os.environ.get("HANDOFF_STORAGE_STATE"))
    rows, worst = [], 0
    for step in steps:
        route = step.get("route") or ""
        if step["kind"] != "page" or not route or not step.get("url"):
            continue
        if any(route == r or route.startswith(r) for r in SESSION_ROUTES) and not has_session:
            rows.append((group_of(route), route, "⏭️", "depende de sesión (HANDOFF_STORAGE_STATE); lo cubre la prueba de compras"))
            continue
        code, fails = run_page(args.handoff, route, live_url(step, args.url))
        rows.append((group_of(route), route, "✅" if code == 0 else "❌", "; ".join(fails) if fails else ("" if code == 0 else "ver validation/")))
        worst = max(worst, 0 if code == 0 else 1)
    public = [live_url(st, args.url) for st in steps if st["kind"] == "page" and st.get("route") and st.get("url")
              and not any(st["route"] == r or st["route"].startswith(r) for r in SESSION_ROUTES)]
    reference = footer_titles(fetch_text(args.url.rstrip("/") + "/"))
    odd = [u for u in public if footer_titles(fetch_text(u)) != reference]
    rows.append(("Pie de página", "todas las públicas", "❌" if odd else "✅",
                 ("el pie difiere del de la home (columnas en otro orden o distintas) en: " + ", ".join(odd)) if odd else f"mismas columnas: {', '.join(reference)}"))
    worst = max(worst, 1 if odd else 0)
    url404, problems = audit_404(args.url)
    note = "el diseño no trae 404: confirmar con quien diseñó"
    rows.append(("404", "404", "❌" if problems else "⚠️", ("; ".join(problems) + " · " + note) if problems else note))
    worst = max(worst, 1 if problems else 0)
    order = [g for g, _ in GROUPS] + ["404", "Pie de página", "Otras"]
    rows.sort(key=lambda r: order.index(r[0]) if r[0] in order else 99)
    out = args.handoff / "validation" / "revision-diseno.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Revisión de diseño · páginas que no son de compra", "", f"Tienda: {args.url}", "",
             "| Grupo | Página | Resultado | Detalle |", "|---|---|---|---|"] + [f"| {g} | {r} | {s} | {d} |" for g, r, s, d in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nInforme: {out}")
    sys.exit(worst)


if __name__ == "__main__":
    main()
