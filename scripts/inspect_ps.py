#!/usr/bin/env python3
"""Lee (solo lectura) una instalación de PrestaShop y escribe prestashop-install.json:
versión, temas disponibles con su tema padre y módulos presentes. No usa la base de datos,
así que el tema activo hay que confirmarlo a mano.

Uso: inspect_ps.py --ps-root /ruta/prestashop --out ./work
"""
import argparse
import json
import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r"const\s+VERSION\s*=\s*['\"]([\d.]+)['\"]")
PARENT_RE = re.compile(r"^parent:\s*(\S+)", re.M)


def read_version(root: Path) -> str:
    # PS 1.7/8 declara la versión en AppKernel; PS 9 la mueve a src/Core/Version.php.
    for rel in ("src/Core/Version.php", "app/AppKernel.php"):
        path = root / rel
        if path.is_file():
            match = VERSION_RE.search(path.read_text(errors="replace"))
            if match:
                return match.group(1)
    return "desconocida"


def read_themes(root: Path) -> list:
    themes = []
    for conf in sorted((root / "themes").glob("*/config/theme.yml")):
        parent = PARENT_RE.search(conf.read_text(errors="replace"))
        themes.append({"name": conf.parent.parent.name, "parent": parent.group(1) if parent else None,
                       "hasCustomCss": (conf.parent.parent / "assets" / "css" / "custom.css").is_file()})
    return themes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ps-root", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    if not (args.ps_root / "themes").is_dir():
        sys.exit(f"No parece una instalación de PrestaShop: {args.ps_root}")
    info = {"version": read_version(args.ps_root), "themes": read_themes(args.ps_root),
            "modules": sorted(p.name for p in (args.ps_root / "modules").iterdir() if p.is_dir()),
            "note": "Tema activo no leído (requiere BD). Confirmar en el Back Office."}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "prestashop-install.json").write_text(json.dumps(info, indent=1, ensure_ascii=False))
    print(f"OK · PrestaShop {info['version']} · {len(info['themes'])} temas · {len(info['modules'])} módulos")


if __name__ == "__main__":
    main()
