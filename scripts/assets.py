#!/usr/bin/env python3
"""Recoge las imágenes que usa el diseño, las copia a assets/img (WebP) y
escribe asset-map.json (origen -> destino, dimensiones, proporción).

Si analyze.py ya dejó structure.json en --out, también guarda el logo del diseño
(descargándolo si es una URL remota, o copiándolo si es local o SVG en línea) en
assets/logo/ y lo registra en asset-map.json bajo la clave "logo".

Uso: assets.py --entry /ruta/index.html --out ./handoff
"""
import argparse
import json
import re
import sys
import urllib.request
from urllib.parse import urlparse
from math import gcd
from pathlib import Path

from PIL import Image

WEBP_QUALITY = 88
# Cualquier cadena entre comillas o url() que acabe en extensión de imagen
# (cubre también rutas escritas dentro de datos JS, no solo atributos src).
SRC_RE = re.compile(r'''["'(]([^"'()\s<>]+\.(?:png|jpe?g|webp|gif|svg|avif))["')]''', re.I)


def collect_refs(text: str) -> list:
    refs = [m for m in SRC_RE.findall(text) if not m.startswith(("http", "data:"))]
    return sorted(set(r.lstrip("/") for r in refs))


def ratio(width: int, height: int) -> str:
    divisor = gcd(width, height) or 1
    return f"{width // divisor}:{height // divisor}"


def convert(src: Path, dest_dir: Path) -> dict:
    dest = dest_dir / (src.stem + ".webp")
    if src.suffix.lower() == ".svg":
        dest = dest_dir / src.name
        dest.write_bytes(src.read_bytes())
        return {"dest": f"assets/img/{dest.name}", "format": "svg"}
    with Image.open(src) as img:
        width, height = img.size
        img.save(dest, "WEBP", quality=WEBP_QUALITY)
    return {"dest": f"assets/img/{dest.name}", "width": width, "height": height,
            "ratio": ratio(width, height), "format": "webp"}


DOWNLOAD_TIMEOUT = 20
USER_AGENT = "Mozilla/5.0 (design-to-prestashop-handoff)"


def save_logo(logo: dict, root: Path, out: Path) -> dict:
    """Guarda el logo en assets/logo/. Devuelve su registro para asset-map.json."""
    dest_dir = out / "assets" / "logo"
    dest_dir.mkdir(parents=True, exist_ok=True)
    record = {"width": logo.get("width"), "height": logo.get("height"), "alt": logo.get("alt")}
    if logo["kind"] == "svg":
        (dest_dir / "logo.svg").write_text(logo["markup"], encoding="utf-8")
        return {**record, "dest": "assets/logo/logo.svg", "source": "inline-svg"}
    src = logo["src"]
    suffix = Path(urlparse(src).path).suffix or ".png"
    dest = dest_dir / f"logo{suffix}"
    if src.startswith(("http://", "https://")):
        request = urllib.request.Request(src, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
            dest.write_bytes(response.read())
    else:
        dest.write_bytes((root / src.lstrip("/")).read_bytes())
    return {**record, "dest": f"assets/logo/{dest.name}", "source": src}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entry", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    root = args.entry.parent
    dest_dir = args.out / "assets" / "img"
    dest_dir.mkdir(parents=True, exist_ok=True)

    mapping, missing = {}, []
    for ref in collect_refs(args.entry.read_text(encoding="utf-8", errors="replace")):
        src = root / ref
        if not src.is_file():
            missing.append(ref)
            continue
        mapping[ref] = convert(src, dest_dir)

    logo_record = None
    structure = args.out / "structure.json"
    if structure.is_file():
        logo = json.loads(structure.read_text()).get("logo")
        if logo:
            try:
                logo_record = save_logo(logo, root, args.out)
            except Exception as err:  # red caída, 404… el handoff debe avisar, no fallar en silencio
                print(f"AVISO: no se pudo guardar el logo ({err})", file=sys.stderr)
        else:
            print("AVISO: no se detectó logo en el diseño", file=sys.stderr)

    (args.out / "asset-map.json").write_text(json.dumps(
        {"assets": mapping, "missing": missing, "logo": logo_record}, indent=1, ensure_ascii=False))
    print(f"OK · {len(mapping)} imágenes · {len(missing)} no encontradas")
    if missing:
        print("No encontradas:", ", ".join(missing[:10]), file=sys.stderr)


if __name__ == "__main__":
    main()
