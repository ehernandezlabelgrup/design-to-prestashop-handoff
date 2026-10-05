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
import json
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PS_VERSION = "9"
DEFAULT_BASE_THEME = "Hummingbird"
TEMPLATE_SUFFIX = ".tmpl"
IGNORED = {".DS_Store"}


DEMO_NOTES = {
    "yes": "Se incluyen **datos demo** (categorías y productos del diseño) en `design/demo-data.json`; léelo con `docs/08-datos-demo.md`. Se crean con referencia `DEMO-` y se borran antes de producción.",
    "no": "No se incluyen datos demo: el catálogo lo carga el cliente.",
}


def render(text: str, values: dict) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


DEMO_ONLY_TEMPLATES = {"08-datos-demo.md"}


def copy_templates(out: Path, values: dict, with_demo: bool):
    templates = SKILL_ROOT / "templates"
    for src in templates.rglob("*" + TEMPLATE_SUFFIX):
        if not with_demo and src.with_suffix("").name in DEMO_ONLY_TEMPLATES:
            continue
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
                 "prestashop-install.json", "image-usage.json", "image-types.json", "image-types.md",
                 "demo-candidates.json", "demo-data.json"):
        if (work / name).is_file():
            shutil.copy2(work / name, out / "design" / name)
    if (work / "content").is_dir():
        shutil.copytree(work / "content", out / "design" / "content", dirs_exist_ok=True)
    if (work / "renders").is_dir():
        shutil.copytree(work / "renders", out / "renders", dirs_exist_ok=True)
    if (work / "assets").is_dir():
        shutil.copytree(work / "assets", out / "assets", dirs_exist_ok=True)


def install_tools(out: Path):
    tools = out / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("steps.py", "compare.py", "ps_seed_demo.php", "ps_set_translations.php"):
        shutil.copy2(SKILL_ROOT / "scripts" / name, tools / name)


def build_steps(work: Path, out: Path, demo: str):
    subprocess.run([sys.executable, str(SKILL_ROOT / "scripts" / "propose_steps.py"), "--work", str(work),
                    "--out", str(out / "design" / "steps.json"), "--demo-data", demo], check=True)
    subprocess.run([sys.executable, str(out / "tools" / "steps.py"), "status"], check=True, stdout=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--entry", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--store", required=True)
    ap.add_argument("--theme-slug", required=True)
    ap.add_argument("--ps-version", default=DEFAULT_PS_VERSION)
    ap.add_argument("--base-theme", default=DEFAULT_BASE_THEME)
    ap.add_argument("--demo-data", choices=["yes", "no"], default="no",
                    help="incluir la creación de datos demo (categorías, productos…). Pregúntalo al usuario.")
    args = ap.parse_args()
    if not args.entry.is_file():
        sys.exit(f"No existe el HTML de entrada: {args.entry}")

    values = {
        "STORE": args.store, "THEME_SLUG": args.theme_slug, "PS_VERSION": args.ps_version,
        "BASE_THEME": args.base_theme, "HANDOFF_DIR": args.out.name,
        "MAIN_ENTRY": f"{args.out.name}/design/source/{args.entry.name}",
        "DEMO_DATA_NOTE": DEMO_NOTES[args.demo_data],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    copy_templates(args.out, values, args.demo_data == "yes")
    copy_work_files(args.work, args.entry.resolve(), args.out)
    install_tools(args.out)
    build_steps(args.work, args.out, args.demo_data)
    print(f"OK · paquete creado en {args.out}. Faltan los huecos del modelo (ver validate.py).")


if __name__ == "__main__":
    main()
