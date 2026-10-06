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
         "summary": "Etiqueta de producto, chip de filtro, corazón de favoritos (solo el aspecto: la lógica se conecta en la tarjeta con el módulo nativo blockwishlist, ver reference/prestashop-mapping.md), aviso/CTA y acordeón.",
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
         "summary": "Cabecera: logo, navegación, cuenta, favoritos y cesta con contador, y el BUSCADOR COMPLETO (capa a pantalla completa, filtro en vivo, estados vacíos, teclado) y el menú móvil. Todo lo que vive en el header se hace en este paso.",
         "acceptance": ["Escritorio y móvil como el diseño", "Menú, buscador y mini-cesta funcionan",
                        "Logo desde el Back Office", "Buscador completo: abre, filtra en vivo, muestra resultados y estados vacíos, y se maneja con teclado", "Textos con traducciones"]},
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

def native_states_step() -> dict:
    """Antes del favicon: estados y avisos nativos de PrestaShop que el diseño no dibuja."""
    return {"id": "estados-nativos", "title": "Estados y avisos nativos que el diseño no trae", "kind": "final", "route": "inicio", "dependsOn": [], "url": "/",
            "summary": "SOLO cuando el resto de páginas está maquetado. Los diseños casi nunca incluyen los avisos y estados que PrestaShop genera solo "
                       "(p. ej. «Tu carrito contiene 1 de este producto» al recargarse la ficha tras añadir a la cesta, producto añadido, cantidad mínima, "
                       "stock bajo, errores de formulario, sesión caducada, código de descuento aplicado, 404, mantenimiento). El maquetador los provoca "
                       "uno a uno en el navegador, comprueba que ninguno sale con el azul/verde/rojo por defecto de Bootstrap y los adapta al diseño "
                       "(notifications.tpl y CSS), usando los mismos tokens que las cajas del diseño. Cualquier estado sin referencia se anota en "
                       "validation/decisiones.md para que el diseñador lo confirme.",
            "acceptance": ["Añadir un producto a la cesta y recargarse la ficha enseña el aviso con el estilo del diseño, no el azul de Bootstrap",
                           "Un error de formulario, un aviso de éxito y uno de información se ven con los colores de la marca",
                           "Cada aviso se puede cerrar y su texto sale del sistema de traducciones",
                           "Los estados que el diseño no dibuja quedan listados en validation/decisiones.md"]}


def identity_step() -> dict:
    """Penúltimo paso: favicon y captura del tema (preview.png)."""
    return {"id": "tema-identidad", "title": "Favicon y captura del tema", "kind": "final", "route": "inicio", "dependsOn": [], "url": "/",
            "summary": "SOLO cuando todo el resto del plan está maquetado y aprobado (el orden del plan lo impone). Con tema y home terminados, scripts/theme_assets.py genera el favicon (monograma de la marca con sus colores y tipografía, "
                       "o el favicon del diseño si lo trae) y themes/<tema>/preview.png (500×746, un recorte vertical de la home real). "
                       "scripts/ps_set_favicon.php aplica el favicon (img/favicon.ico, PS_FAVICON y PS_FAVICON_UPDATE_TIME).",
            "acceptance": ["La pestaña del navegador muestra el favicon (también a 16 px) y no el de PrestaShop",
                           "Diseño > Tema y logotipo enseña la captura nueva del tema, no la de Hummingbird",
                           "Existen apple-touch-icon.png (180), icon-192.png y icon-512.png en el handoff",
                           "El favicon usa los colores y la tipografía del diseño (o el favicon del propio diseño)"]}


def final_steps() -> list:
    """Último paso del plan: compras de extremo a extremo con un navegador real, comparando con el diseño."""
    return [{
        "id": "prueba-final", "title": "Prueba final · compras de extremo a extremo", "kind": "final", "route": "checkout",
        "dependsOn": [], "url": "/", "checkProfile": "e2e",
        "e2e": {"productPath": "<ruta-de-un-producto-con-stock>", "expectHeadings": [], "expectConfirmation": "",
                "designCheckout": "checkout", "designConfirmation": "confirmacion"},
        "summary": "SOLO cuando todo el resto del plan está maquetado y aprobado (es el último paso). Con un navegador real (scripts/e2e_checkout.py), tres compras: 1) como invitado, solo si la tienda tiene el modo invitado "
                   "activo (si no, se anota y se salta); 2) como usuario registrado: primero se registra y después compra; 3) como usuario "
                   "registrado creando una dirección nueva en el pago. En cada pantalla se compara con el diseño y se INFORMA de todo lo "
                   "que no cuadre (altura, títulos, textos sin traducir, azul de Bootstrap, scroll horizontal).",
        "acceptance": ["Las tres compras terminan en la confirmación de pedido (la de invitado, solo si el modo invitado está activo)",
                       "En el pago salen envíos y métodos de pago tras rellenar la dirección",
                       "La compra con dirección nueva muestra esa dirección en la confirmación",
                       "El informe validation/prueba-final.md se ha revisado: cada ⚠️ «no cuadra con el diseño» se corrige o se acepta por escrito",
                       "Sin errores de JavaScript en consola en ninguno de los tres flujos"]}]


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
    steps = prep_steps(args.demo_data == "yes") + base_steps(guide) + global_steps(routes[0]) + page_steps(routes) + [native_states_step(), identity_step()] + final_steps()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"steps": steps}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"OK · esqueleto con {len(steps)} pasos → {args.out}")


if __name__ == "__main__":
    main()
