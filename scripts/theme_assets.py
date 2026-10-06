#!/usr/bin/env python3
"""Genera el favicon y la captura del tema (preview.png) del proyecto.

 - Favicon: un monograma cuadrado con las iniciales de la marca (colores y tipografía del diseño). Se escribe un `favicon.ico`
   (16, 32 y 48 px) y PNG de 16, 32, 180 (apple-touch), 192 y 512 px. Si el diseño ya trae un favicon (<link rel="icon">), se
   usa ese en lugar de generar uno.
 - Captura del tema (`themes/<tema>/preview.png`, 500×746, la que ve el Back Office en Diseño > Tema y logotipo): un recorte
   vertical de la home real del tema, a 1440 px de ancho y reducido.

Uso:
  theme_assets.py --url http://tienda:8100/ --theme-dir /ruta/themes/mitema --name "Marca" \\
      [--initials MC] [--bg "#FAF7F2"] [--fg "#E8505B"] [--border "#141414"] [--font "Archivo Black"] \\
      [--font-file /ruta/fuente.woff2] [--design-index design/source/index.html] [--out assets-out]
Para aplicar el favicon en PrestaShop: ps_set_favicon.php --ps-root=/ruta/tienda --ico=<out>/favicon.ico (como usuario del servidor web).
"""
import argparse
import re
import sys
from pathlib import Path

from PIL import Image

PREVIEW_SIZE = (500, 746)
ICO_SIZES = [(16, 16), (32, 32), (48, 48)]
PNG_SIZES = {"favicon-16.png": 16, "favicon-32.png": 32, "apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}


def monogram_html(args) -> str:
    initials = args.initials or "".join(w[0] for w in args.name.split()[:2]).upper()
    font_face = f"@font-face{{font-family:'Brand';src:url('file://{args.font_file}')}}" if args.font_file else ""
    family = "'Brand'," if args.font_file else f"'{args.font}',"
    return f"""<!doctype html><meta charset="utf-8"><style>{font_face}
html,body{{margin:0;background:transparent}}
.i{{box-sizing:border-box;width:512px;height:512px;display:flex;align-items:center;justify-content:center;background:{args.bg};
border:28px solid {args.border};color:{args.fg};font:900 250px/1 {family}'Archivo',Arial Black,sans-serif;letter-spacing:-.04em;
text-shadow:14px 14px 0 {args.border};padding-bottom:10px}}</style><div class="i">{initials}</div>"""


def existing_favicon(index: Path):
    if not index or not index.is_file():
        return None
    match = re.search(r'<link[^>]*rel="(?:shortcut )?icon"[^>]*href="([^"]+)"', index.read_text(encoding="utf-8", errors="replace"))
    if not match or match.group(1).startswith(("data:", "http")):
        return None
    candidate = index.parent / match.group(1).lstrip("/")
    return candidate if candidate.is_file() else None


def build_favicon(playwright, args, out: Path) -> Path:
    source = out / "favicon-source.png"
    found = existing_favicon(args.design_index)
    if found:
        Image.open(found).convert("RGBA").resize((512, 512), Image.LANCZOS).save(source)
        print(f"favicon: se usa el del diseño ({found})")
    else:
        browser = playwright.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 512, "height": 512})
        page.set_content(monogram_html(args))
        page.wait_for_timeout(600)
        page.locator(".i").screenshot(path=str(source), omit_background=True)
        browser.close()
        print("favicon: monograma generado con los colores del diseño")
    base = Image.open(source).convert("RGBA")
    for name, size in PNG_SIZES.items():
        base.resize((size, size), Image.LANCZOS).save(out / name)
    ico = out / "favicon.ico"
    base.save(ico, format="ICO", sizes=ICO_SIZES)
    return ico


def build_preview(playwright, args) -> Path:
    browser = playwright.chromium.launch(args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(args.url, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(1200)
    page.add_style_tag(content="[data-jc-search], .modal-backdrop, .jc-toast{display:none!important}")
    shot = args.theme_dir / ".preview-full.png"
    page.screenshot(path=str(shot), full_page=True)
    browser.close()
    full = Image.open(shot).convert("RGB")
    crop_h = round(full.size[0] * PREVIEW_SIZE[1] / PREVIEW_SIZE[0])
    full.crop((0, 0, full.size[0], min(crop_h, full.size[1]))).resize(PREVIEW_SIZE, Image.LANCZOS).save(args.theme_dir / "preview.png", optimize=True)
    shot.unlink()
    return args.theme_dir / "preview.png"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="home de la tienda con el tema activo")
    ap.add_argument("--theme-dir", required=True, type=Path)
    ap.add_argument("--name", required=True, help="nombre de la marca (para las iniciales)")
    ap.add_argument("--initials", default="")
    ap.add_argument("--bg", default="#FAF7F2")
    ap.add_argument("--fg", default="#E8505B")
    ap.add_argument("--border", default="#141414")
    ap.add_argument("--font", default="Archivo Black")
    ap.add_argument("--font-file", default="", help="ruta a la fuente de la marca (woff2/ttf) para el monograma")
    ap.add_argument("--design-index", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("assets-out"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        ico = build_favicon(pw, args, args.out)
        preview = build_preview(pw, args)
    print(f"OK · favicon {ico} · captura del tema {preview} ({PREVIEW_SIZE[0]}×{PREVIEW_SIZE[1]})")


if __name__ == "__main__":
    sys.exit(main())
