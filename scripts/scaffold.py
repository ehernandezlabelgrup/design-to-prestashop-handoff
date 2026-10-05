#!/usr/bin/env python3
"""Crea el paquete de handoff desde templates/ y copia los fuentes y renders.

Uso:
  scaffold.py --work ./work --entry /ruta/index.html --out ./handoff-tienda \
              --store "Mi Tienda" --theme-slug mitienda [--ps-version 9] [--base-theme Hummingbird]

Rellena los placeholders conocidos. Los que dependen del diseño ({{SOURCE_PRIORITY}},
{{HOW_TO_READ_SOURCE}}, {{PROJECT_DESCRIPTION}}, {{DEMO_CONTENT_NOTE}}) y los huecos
`<!-- MODEL: ... -->` los rellena el modelo después; validate.py avisa si quedan.
"""
import argparse
import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PS_VERSION = "9"
DEFAULT_BASE_THEME = "Hummingbird"
TEMPLATE_SUFFIX = ".tmpl"
IGNORED = {".DS_Store"}


def render(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def copy_templates(out: Path, values: dict):
    templates = SKILL_ROOT / "templates"
    for src in templates.rglob("*" + TEMPLATE_SUFFIX):
        dest = out / src.relative_to(templates).with_suffix("")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(src.read_text(encoding="utf-8"), values), encoding="utf-8")


def copy_work_files(work: Path, entry: Path, out: Path):
    source_dir = out / "design" / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry, source_dir / entry.name)
    uploads = entry.parent / "uploads"
    if uploads.is_dir():
        shutil.copytree(uploads, source_dir / "uploads", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(*IGNORED))
    for name in ("raw-tokens.json", "structure.json", "texts.json", "asset-map.json", "inline-styles.json",
                 "prestashop-install.json"):
        if (work / name).is_file():
            shutil.copy2(work / name, out / "design" / name)
    if (work / "renders").is_dir():
        shutil.copytree(work / "renders", out / "renders", dirs_exist_ok=True)
    if (work / "assets").is_dir():
        shutil.copytree(work / "assets", out / "assets", dirs_exist_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--entry", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--store", required=True)
    ap.add_argument("--theme-slug", required=True)
    ap.add_argument("--ps-version", default=DEFAULT_PS_VERSION)
    ap.add_argument("--base-theme", default=DEFAULT_BASE_THEME)
    args = ap.parse_args()
    if not args.entry.is_file():
        sys.exit(f"No existe el HTML de entrada: {args.entry}")

    values = {
        "STORE": args.store, "THEME_SLUG": args.theme_slug, "PS_VERSION": args.ps_version,
        "BASE_THEME": args.base_theme, "HANDOFF_DIR": args.out.name,
        "MAIN_ENTRY": f"{args.out.name}/design/source/{args.entry.name}",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    copy_templates(args.out, values)
    copy_work_files(args.work, args.entry.resolve(), args.out)
    print(f"OK · paquete creado en {args.out}. Faltan los huecos del modelo (ver validate.py).")


if __name__ == "__main__":
    main()
