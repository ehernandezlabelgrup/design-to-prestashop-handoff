#!/usr/bin/env python3
"""Valida un handoff terminado. Sale con código 1 si hay errores.

Uso: validate.py ./handoff-tienda
"""
import json
import re
import sys
from pathlib import Path

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
REQUIRED_FILES = ["CLAUDE.md", "PROMPT-INICIAL.md", "tokens.css", "docs/00-reglas-equipo.md",
                  "docs/01-concepto-y-arquitectura.md", "docs/02-sistema-visual.md",
                  "docs/03-interacciones.md", "docs/04-plan-prestashop.md", "docs/05-textos.md", "docs/06-validacion-por-pagina.md", "validation/progreso.md"]
REQUIRED_PHRASES = {
    "CLAUDE.md": ["custom.css", "traducciones", "00-reglas-equipo"],
    "docs/00-reglas-equipo.md": ["custom.css", "{l s=", "trans("],
    "PROMPT-INICIAL.md": ["custom.css"],
}


def rgb_to_hex(rgb: str) -> str:
    nums = [int(n) for n in re.findall(r"\d+", rgb)[:3]]
    return "#{:02x}{:02x}{:02x}".format(*nums) if len(nums) == 3 else ""


def known_hexes(raw: dict) -> set:
    found = set()
    for viewport in raw.get("viewports", {}).values():
        for key in ("colors", "backgrounds", "borders"):
            for value in viewport.get(key, {}):
                found.update(rgb_to_hex(m) for m in re.findall(r"rgba?\([^)]*\)", value))
    found.update(v.lower() for v in raw.get("stylesheets", {}).get("rootVars", {}).values()
                 if v.startswith("#"))
    return found


def check_files(root: Path, errors: list):
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            errors.append(f"Falta {rel}")
    for rel, phrases in REQUIRED_PHRASES.items():
        path = root / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            errors.extend(f"{rel}: no menciona «{p}»" for p in phrases if p not in text)


def check_placeholders(root: Path, errors: list):
    for path in list(root.glob("*.md")) + list(root.glob("docs/*.md")) + [root / "tokens.css"]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in re.findall(r"\{\{[A-Z_]+\}\}|<!-- MODEL[^>]*", text):
            errors.append(f"{path.relative_to(root)}: queda un hueco sin rellenar → {marker[:50]}")
        if "MODEL:" in text:
            errors.append(f"{path.relative_to(root)}: queda un comentario MODEL:")


def check_tokens(root: Path, errors: list):
    raw_path, css_path = root / "design" / "raw-tokens.json", root / "tokens.css"
    if not (raw_path.is_file() and css_path.is_file()):
        return
    known = known_hexes(json.loads(raw_path.read_text()))
    for color in sorted(set(c.lower() for c in HEX_RE.findall(css_path.read_text()))):
        if len(color) == 7 and color not in known:
            errors.append(f"tokens.css: {color} no aparece en raw-tokens.json (¿inventado?)")


def check_assets(root: Path, errors: list):
    amap = root / "design" / "asset-map.json"
    if amap.is_file():
        for ref, info in json.loads(amap.read_text()).get("assets", {}).items():
            if not (root / info["dest"]).is_file():
                errors.append(f"asset-map: falta {info['dest']}")


def main():
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    errors = []
    for check in (check_files, check_placeholders, check_tokens, check_assets):
        check(root, errors)
    for err in errors:
        print("✗", err)
    print(f"{'FALLA' if errors else 'OK'} · {len(errors)} problemas")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
