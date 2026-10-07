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
                  "docs/03-interacciones.md", "docs/04-plan-prestashop.md", "docs/05-textos.md", "docs/06-validacion-por-pagina.md", "docs/07-ajustes-imagenes.md", "docs/09-plan-por-pasos.md", "validation/progreso.md",
                  "tools/steps.py", "tools/compare.py", "design/steps.json"]
REQUIRED_PHRASES = {
    "CLAUDE.md": ["custom.css", "traducciones", "00-reglas-equipo"],
    "docs/00-reglas-equipo.md": ["custom.css", "{l s=", "trans("],
    "PROMPT-INICIAL.md": ["custom.css"],
}


def rgb_to_hex(rgb: str) -> str:
    nums = [int(n) for n in re.findall(r"\d+", rgb)[:3]]
    return "#{:02x}{:02x}{:02x}".format(*nums) if len(nums) == 3 else ""


def known_hexes(raw: dict, source_dir: Path = None) -> set:
    found = set()
    for viewport in raw.get("viewports", {}).values():
        for key in ("colors", "backgrounds", "borders"):
            for value in viewport.get(key, {}):
                found.update(rgb_to_hex(m) for m in re.findall(r"rgba?\([^)]*\)", value))
    found.update(v.lower() for v in raw.get("stylesheets", {}).get("rootVars", {}).values()
                 if v.startswith("#"))
    # estados que no salen en las capturas (hover, error, éxito…) solo están en el código del diseño
    if source_dir and source_dir.is_dir():
        for html in source_dir.rglob("*.html"):
            found.update(c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", html.read_text(encoding="utf-8", errors="replace")))
    # colores que solo aparecen en reglas :hover/:focus
    sheets = raw.get("stylesheets", {})
    for rule in sheets.get("hover", []) + sheets.get("focus", []):
        found.update(c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", rule))
        found.update(rgb_to_hex(m) for m in re.findall(r"rgba?\([^)]*\)", rule))
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
    known = known_hexes(json.loads(raw_path.read_text()), root / "design" / "source")
    for color in sorted(set(c.lower() for c in HEX_RE.findall(css_path.read_text()))):
        if len(color) == 7 and color not in known:
            errors.append(f"tokens.css: {color} no aparece en raw-tokens.json (¿inventado?)")


def check_assets(root: Path, errors: list):
    amap = root / "design" / "asset-map.json"
    if amap.is_file():
        for ref, info in json.loads(amap.read_text()).get("assets", {}).items():
            if not (root / info["dest"]).is_file():
                errors.append(f"asset-map: falta {info['dest']}")


def check_logo_and_content(root: Path, errors: list):
    amap = root / "design" / "asset-map.json"
    if amap.is_file():
        logo = json.loads(amap.read_text()).get("logo")
        if not logo:
            errors.append("asset-map: no hay logo (¿el diseño no lo trae o falló la descarga?)")
        elif not (root / logo["dest"]).is_file():
            errors.append(f"falta el logo {logo['dest']}")
    content = root / "design" / "content"
    plan = root / "docs" / "04-plan-prestashop.md"
    if content.is_dir() and any(content.glob("*.html")) and plan.is_file():
        if "CMS" not in plan.read_text(encoding="utf-8"):
            errors.append("docs/04: hay contenido legal en design/content pero el plan no menciona las páginas CMS")


def check_demo_data(root: Path, errors: list):
    demo = root / "design" / "demo-data.json"
    if not demo.is_file():
        return
    if not (root / "docs" / "08-datos-demo.md").is_file():
        errors.append("Hay demo-data.json pero falta docs/08-datos-demo.md")
    data = json.loads(demo.read_text(encoding="utf-8"))
    slugs = {c["slug"] for c in data.get("categories", [])}
    refs = [p["reference"] for p in data.get("products", [])]
    errors.extend(f"demo-data: referencia repetida {r}" for r in sorted({r for r in refs if refs.count(r) > 1}))
    for product in data.get("products", []):
        errors.extend(f"demo-data: {product['reference']} cita la categoría inexistente «{s}»"
                      for s in product.get("categories", []) if s not in slugs)
        if not product["reference"].startswith("DEMO-"):
            errors.append(f"demo-data: {product['reference']} no empieza por DEMO-")
        errors.extend(f"demo-data: falta la imagen {img}" for img in product.get("images", [])
                      if not (root / "design" / "source" / img).is_file())


def check_steps(root: Path, errors: list):
    path = root / "design" / "steps.json"
    if not path.is_file():
        return
    steps = json.loads(path.read_text(encoding="utf-8")).get("steps", [])
    ids = [s["id"] for s in steps]
    if not ids or ids[0] != "prep-git":
        errors.append("steps.json: el primer paso tiene que ser prep-git (repositorio git privado)")
    errors.extend(f"steps.json: id repetido {i}" for i in sorted({i for i in ids if ids.count(i) > 1}))
    for step in steps:
        label = f"steps.json[{step['id']}]"
        if step.get("confirm"):
            errors.append(f"{label}: tiene confirm:true sin resolver (confírmalo o bórralo)")
        errors.extend(f"{label}: depende de {d}, que no existe" for d in step.get("dependsOn", []) if d not in ids)
        if step["kind"] != "prep" and not step.get("acceptance"):
            errors.append(f"{label}: sin criterios de revisión")
        if "agotad" in (step["id"] + " " + step.get("title", "")).lower() and step["kind"] != "prep":
            text = " ".join(step.get("acceptance", [])).lower()
            if "avísame" not in text and "emailalerts" not in text:
                errors.append(f"{label}: el paso de producto agotado debe incluir el aviso de reposición «Avísame» (ps_emailalerts) entre sus criterios, aunque el diseño no lo dibuje")
        if step["kind"] in ("global", "section") and not step.get("designSelector"):
            errors.append(f"{label}: falta designSelector")
        if step["kind"] not in ("prep", "final") and not step.get("route"):
            errors.append(f"{label}: falta route")


def check_interaction_coverage(root: Path, errors: list):
    """Cada interacción de docs/03 (título en negrita al inicio de línea) debe figurar en la tabla de cobertura de docs/09."""
    docs3, docs9 = root / "docs" / "03-interacciones.md", root / "docs" / "09-plan-por-pasos.md"
    if not (docs3.is_file() and docs9.is_file()):
        return
    headings = [m.group(1).strip() for m in re.finditer(r"^\*\*([^*\n]+)\*\*", docs3.read_text(encoding="utf-8"), re.M)]
    plan = docs9.read_text(encoding="utf-8").lower()
    if "cobertura de interacciones" not in plan:
        errors.append("docs/09: falta la sección «Cobertura de interacciones (docs/03 → pasos)»")
        return
    steps_ids = {s["id"] for s in json.loads((root / "design" / "steps.json").read_text()).get("steps", [])} if (root / "design" / "steps.json").is_file() else set()
    covered_section = plan.split("cobertura de interacciones", 1)[1]
    for title in headings:
        if title.lower() not in covered_section:
            errors.append(f"docs/09: la interacción «{title}» de docs/03 no está en la tabla de cobertura (¿falta un paso?)")
    for ref in re.findall(r"`([a-z0-9][a-z0-9-]+)`", covered_section):
        if ref not in steps_ids and re.fullmatch(r"[a-z]+(-[a-z0-9]+)+", ref) and ref.split("-")[0] in {i.split("-")[0] for i in steps_ids}:
            errors.append(f"docs/09: la tabla de cobertura cita el paso `{ref}`, que no existe en steps.json")


def main():
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_dir():
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    errors = []
    for check in (check_files, check_placeholders, check_tokens, check_assets, check_logo_and_content, check_demo_data, check_steps, check_interaction_coverage):
        check(root, errors)
    for err in errors:
        print("✗", err)
    print(f"{'FALLA' if errors else 'OK'} · {len(errors)} problemas")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
