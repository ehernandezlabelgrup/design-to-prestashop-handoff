#!/usr/bin/env python3
"""Genera un esqueleto de design/steps.json (plan de maquetación paso a paso).

Crea: pasos de preparación (fase 0), las bases de CSS (tokens, botones, formularios…), los elementos globales (pre-header, header, footer) y un
paso por página. NO sabe dividir las páginas en secciones ni conoce los selectores finales:
eso lo hace el modelo mirando las capturas, editando el JSON (ver reference/steps-schema.md).
Los pasos con "confirm": true hay que confirmarlos o borrarlos; el validador no deja pasar
ninguno sin resolver.

Uso: propose_steps.py --work ./work --out ./handoff/design/steps.json [--demo-data yes] [--force]
"""
import argparse
import json
import re
import sys
from pathlib import Path


def slug(route: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", route.lower()).strip("-") or "index"


def prep_steps(with_demo: bool) -> list:
    steps = [
        {"id": "prep-imagenes", "title": "Tipos de imagen", "kind": "prep", "dependsOn": [],
         "summary": "Crear los tipos de imagen de PrestaShop según docs/07-ajustes-imagenes.md.",
         "docs": ["docs/07-ajustes-imagenes.md"],
         "acceptance": ["Los tipos existen en Diseño > Ajustes de imágenes con el tamaño de docs/07",
                        "Declarados en config/theme.yml del tema"]},
        {"id": "prep-logo-cms", "title": "Logo y páginas CMS", "kind": "prep", "dependsOn": [],
         "summary": "Subir el logo de assets/logo/ y crear las páginas CMS con el texto de design/content/.",
         "docs": ["docs/04-plan-prestashop.md", "docs/00-reglas-equipo.md"],
         "acceptance": ["Logo visible en Diseño > Tema y logo", "Una página CMS por cada archivo de design/content/"]},
    ]
    if with_demo:
        steps += [
            {"id": "prep-categorias", "title": "Categorías demo", "kind": "prep", "dependsOn": [],
             "summary": "Crear las categorías demo de design/demo-data.json (docs/08-datos-demo.md).",
             "docs": ["docs/08-datos-demo.md"], "acceptance": ["El árbol de categorías coincide con demo-data.json"]},
            {"id": "prep-productos", "title": "Productos demo", "kind": "prep", "dependsOn": ["prep-categorias"],
             "summary": "Crear los productos demo con sus imágenes (referencia DEMO-…).",
             "docs": ["docs/08-datos-demo.md"],
             "acceptance": ["Todos los productos de demo-data.json existen con imágenes y miniaturas generadas"]},
        ]
    return steps


def base_steps(guide_route: str) -> list:
    """Bases de CSS y elementos pequeños, antes de header, footer y páginas (plan inicial)."""
    base = {"kind": "base", "route": guide_route, "dependsOn": [], "url": "<url-de-la-superficie-de-prueba>"}
    return [
        {**base, "id": "base-tokens", "title": "Base · tokens, fuentes y tipografía", "checkProfile": "tokens",
         "summary": "Tokens de tokens.css en :root de custom.css, fuentes autoalojadas (woff2, swap) y tipografía base (body, títulos, enlaces).",
         "docs": ["tokens.css", "docs/02-sistema-visual.md"],
         "acceptance": ["Los tokens están en :root al principio de custom.css con el marcador --custom-css-loaded",
                        "Las fuentes salen del tema (woff2 autoalojado, font-display: swap), no de un CDN",
                        "Cuerpo y títulos con la escala y el interlineado del diseño"]},
        {**base, "id": "base-botones", "title": "Base · botones y enlaces",
         "summary": "Botón (variantes y estados), enlace con flecha, botón de icono y badge.",
         "docs": ["docs/02-sistema-visual.md"],
         "acceptance": ["Todas las variantes y estados (hover, foco, desactivado) como el diseño", "Sin estilo en línea"]},
        {**base, "id": "base-formularios", "title": "Base · campos de formulario",
         "summary": "Inputs, selects, textarea, casillas, listas de opciones, selector de cantidad y estados de error.",
         "docs": ["docs/02-sistema-visual.md"],
         "acceptance": ["Campos, casillas y radios como el diseño en reposo, foco, error y desactivado", "Objetivos táctiles de 44 px o más"]},
        {**base, "id": "base-etiquetas", "title": "Base · etiquetas, chips y avisos",
         "summary": "Etiqueta de producto, chip de filtro, corazón de favoritos, aviso/CTA y acordeón.",
         "docs": ["docs/02-sistema-visual.md"],
         "acceptance": ["Cada elemento y sus estados como el diseño", "El acordeón funciona con teclado"]},
        {**base, "id": "base-layout", "title": "Base · contenedor, retícula y paneles",
         "summary": "Contenedor, gutters, puntos de corte, rejilla y panel de resumen sobre Hummingbird.",
         "docs": ["docs/02-sistema-visual.md"],
         "acceptance": ["Anchos y gutters como el diseño en escritorio y móvil", "Los puntos de corte coinciden con los del diseño"]},
    ]


def global_steps(first_route: str) -> list:
    base = {"kind": "global", "route": first_route, "dependsOn": [], "url": "/"}
    return [
        {**base, "id": "preheader", "title": "Pre-header (barra superior)", "confirm": True, "designSelector": "",
         "summary": "Barra superior encima del header, si el diseño la tiene. Si no existe, borra este paso.",
         "acceptance": ["Texto y estilo como el diseño en escritorio y móvil", "Textos con traducciones"]},
        {**base, "id": "header", "title": "Header", "confirm": True, "designSelector": "header",
         "summary": "Cabecera: logo, navegación, buscador, cuenta, favoritos y cesta.",
         "acceptance": ["Escritorio y móvil como el diseño", "Menú, buscador y mini-cesta funcionan",
                        "Logo desde el Back Office", "Textos con traducciones"]},
        {**base, "id": "footer", "title": "Footer", "confirm": True, "designSelector": "footer",
         "summary": "Pie de página: enlaces, legal, redes y copyright.",
         "acceptance": ["Escritorio y móvil como el diseño", "Enlaces legales a las páginas CMS", "Textos con traducciones"]},
    ]


def page_steps(routes: list) -> list:
    steps = []
    for route in routes:
        steps.append({"id": f"pagina-{slug(route)}", "title": f"Página · {route}", "kind": "page", "route": route,
                      "dependsOn": ["header", "footer"], "url": "<url-en-PrestaShop>",
                      "summary": f"Maquetar la página «{route}». El modelo la divide en secciones si conviene.",
                      "acceptance": ["Escritorio y móvil como el diseño", "Textos con traducciones", "Sin estilo en línea"]})
    return steps


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--demo-data", choices=["yes", "no"], default="no")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-routes", default="", help="rutas que no se maquetan, separadas por coma (p. ej. indice,guia)")
    args = ap.parse_args()
    if args.out.is_file() and not args.force:
        sys.exit(f"{args.out} ya existe (puede tener trabajo del modelo). Usa --force para sobrescribir.")
    structure = json.loads((args.work / "structure.json").read_text())
    skip = {r for r in args.skip_routes.split(",") if r}
    routes = [r for r in structure["routes"] if r not in skip]
    guide = next((r for r in structure["routes"] if r in ("guia", "guide", "styleguide")), routes[0])
    steps = prep_steps(args.demo_data == "yes") + base_steps(guide) + global_steps(routes[0]) + page_steps(routes)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"steps": steps}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"OK · esqueleto con {len(steps)} pasos → {args.out}")


if __name__ == "__main__":
    main()
