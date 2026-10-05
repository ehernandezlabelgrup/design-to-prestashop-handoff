---
name: design-to-prestashop-handoff
description: Convierte uno o varios HTML de diseño (maqueta estática, SPA con rutas hash o prototipo de herramienta de diseño) en un paquete de handoff para que el equipo PrestaShop lo maquete en PrestaShop 9 (Hummingbird). Genera CLAUDE.md, prompt inicial, tokens.css, docs de sistema visual, interacciones, textos y plan PrestaShop, con las reglas del equipo (todo el CSS en custom.css, sin estilo en línea, todos los textos con el sistema de traducciones). Usar cuando se pida "handoff", "especificaciones para maquetar en PrestaShop", "pasar este HTML a PrestaShop" o "preparar el diseño para el equipo".
---

# design-to-prestashop-handoff

Entrada: uno o más HTML de diseño (+ su carpeta de imágenes). Salida: una carpeta `handoff-<tienda>/` (y su zip) que el equipo PrestaShop copia a su instalación y arranca con el `PROMPT-INICIAL.md`.

## Reglas que el handoff siempre impone
Están en `templates/docs/00-reglas-equipo.md.tmpl`. Las dos que más se rompen:
1. **Todo el CSS en `custom.css`**, nunca estilo en línea ni `<style>` en plantillas.
2. **Todo texto visible por el sistema de traducciones de PrestaShop** (`{l s='…' d='Shop.Theme.X'}`, `$this->trans()`, y en JS solo cadenas pasadas por `data-*` o `Media::addJsDef`).

Base por defecto: **PrestaShop 9 + Hummingbird**. Para 8.x se pasa `--ps-version 8 --base-theme classic`.

## Entradas que hay que tener (pregunta lo que falte)
- Ruta del HTML principal y su carpeta de assets.
- Nombre de la tienda y `theme-slug` (minúsculas, sin espacios).
- Versión de PrestaShop (9 por defecto).
- Brief o concepto, si existe. Si no existe, no lo inventes.

## Flujo
1. **Analizar** (scripts, sin juicio):
   ```
   python3 scripts/analyze.py --entry <index.html> --out <work>
   python3 scripts/assets.py  --entry <index.html> --out <work>
   ```
   Requiere Python con `playwright` (Chromium) y `Pillow`. Detecta las rutas hash, renderiza cada página en 1440 y 390 px y escribe `raw-tokens.json`, `structure.json`, `texts.json`, `inline-styles.json`, `renders/` y `asset-map.json`. Revisa que no haya `consoleErrors` y mira las capturas.
2. **Montar el paquete**:
   ```
   python3 scripts/scaffold.py --work <work> --entry <index.html> --out <handoff-tienda> --store "<Tienda>" --theme-slug <slug>
   ```
3. **Redactar** (aquí va el juicio del modelo). Rellena todos los huecos `{{…}}` y `<!-- MODEL: … -->`:
   - `tokens.css`: nombres semánticos; cada hex y cada px tiene que salir de `raw-tokens.json`. Si el diseño usa estilos en línea o no tiene variables, deduce los tokens de los valores más frecuentes y avisa. Anota las discrepancias entre el código y lo que describan los docs.
   - `docs/01`: páginas y orden de secciones, a partir de `structure.json` y las capturas.
   - `docs/02`: color, tipografía, retícula, componentes repetidos y sus estados.
   - `docs/03`: valores literales de `transitions`, `keyframes`, `:hover` y `:focus`.
   - `docs/04`: tabla pieza → solución usando `reference/prestashop-mapping.md`. Siempre como hipótesis.
   - `docs/05-textos.md`: textos de `texts.json` agrupados, con dominio de traducción propuesto.
   - `CLAUDE.md`: `SOURCE_PRIORITY` (vista de escritorio > móvil > estados > docs), `HOW_TO_READ_SOURCE` (según el formato del HTML), `PROJECT_DESCRIPTION` y `DEMO_CONTENT_NOTE`.
   - Estilos en línea del diseño (`inline-styles.json`): no se copian; se describen como clases en `docs/02`.
4. **Validar**: `python3 scripts/validate.py <handoff-tienda>`. Corrige hasta que diga OK.
5. **Entregar**: resumen breve al usuario y, tras su visto bueno, zip sin `.DS_Store`.

## Cosas que no hay que hacer
- No inventar concepto, marca ni funcionalidades que el diseño no muestre.
- No incluir material de clientes ni credenciales en la skill. Esta skill es pública; los handoffs generados se guardan fuera del repositorio.
- No redondear valores del diseño.
- No dar el handoff por bueno sin haber pasado `validate.py`.
