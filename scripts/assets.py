#!/usr/bin/env python3
"""Recoge las imágenes que usa el diseño, las copia a assets/img (WebP) y
escribe asset-map.json (origen -> destino, dimensiones, proporción).

Uso: assets.py --entry /ruta/index.html --out ./handoff
"""
import argparse
import json
import re
import sys
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

    (args.out / "asset-map.json").write_text(json.dumps(
        {"assets": mapping, "missing": missing}, indent=1, ensure_ascii=False))
    print(f"OK · {len(mapping)} imágenes · {len(missing)} no encontradas")
    if missing:
        print("No encontradas:", ", ".join(missing[:10]), file=sys.stderr)


if __name__ == "__main__":
    main()
