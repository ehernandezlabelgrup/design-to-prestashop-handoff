# steps.json — plan de maquetación paso a paso

`propose_steps.py` genera un esqueleto; el modelo lo completa mirando las capturas. Ruta: `design/steps.json`. El orden del array es el orden de maquetación.

```json
{"steps": [
  {"id": "header", "title": "Header", "kind": "global",
   "route": "inicio", "designSelector": "header", "liveSelector": "header#header",
   "url": "/", "dependsOn": ["prep-logo-cms"],
   "summary": "Cabecera: logo, navegación, buscador, cuenta, favoritos y cesta.",
   "docs": ["docs/02-sistema-visual.md"], "files": ["themes/<tema>/templates/_partials/header.tpl"],
   "acceptance": ["Escritorio y móvil como el diseño", "Menú y buscador funcionan"]}
]}
```

- `kind`: `prep` (fase 0, sin comprobación automática), `base` (bases de CSS y elementos pequeños antes de header, footer y páginas: tokens, botones, formularios…), `global` (pre-header, header, footer), `section` (parte de una página) o `page` (página entera).
- `designSelector`: selector CSS del elemento en el diseño de origen, que **tiene que existir** (`tools/steps.py verify` lo comprueba). `liveSelector`: el equivalente en PrestaShop; si falta, el paso se comprueba como página entera.
- `url`: ruta de PrestaShop a abrir para comprobarlo (se pasa completa en `check --url`).
- `dependsOn`: ids que deben estar aprobados. Además, **cada paso exige todos los anteriores aprobados**.
- `confirm: true`: lo pone el esqueleto en pasos inciertos (p. ej. pre-header). El modelo lo confirma (quita la marca) o borra el paso.
- Un paso de sección va **después** de los de las secciones anteriores de su misma página y hereda su `route`; la página entera se comprueba con un paso `page` al final (o se omite si las secciones la cubren).
- `propose_steps.py --skip-routes indice,guia` excluye rutas que no se maquetan. Los `url` del esqueleto son un marcador `<url-en-PrestaShop>`: hay que sustituirlos.
- Los criterios (`acceptance`) deben ser comprobables por una persona mirando el navegador.

- `checkProfile`: comprobación automática específica del paso en lugar de la comparación de página. Hoy existe `tokens` (tokens en `:root`, marcador de `custom.css`, fuentes autoalojadas con swap, sin Google Fonts, `body` con Archivo).
- `checkProfile: "styles"` + `assertions`: el paso se comprueba contrastando estilos calculados con valores **sacados del diseño** (mide los elementos del diseño de origen con Playwright). Cada aserción: `{"name": "...", "selector": "<css de la superficie de prueba>", "state": "hover|focus" (opcional), "props": {"background-color": "rgb(20, 20, 20)", ...}}`. Es lo que comprueba los pasos de base.
- En las aserciones de `styles`, `"before": [{"press": "/"}, {"click": "<css>"}, {"fill": ["<css>", "texto"]}, {"wait": 900}]` recarga la página y ejecuta esas acciones antes de medir; sirve para estados que no están a la vista (buscador abierto, resultados, acordeón desplegado).
- **Cobertura:** cada interacción de `docs/03` debe estar en la tabla «Cobertura de interacciones» de `docs/09` con su paso; si no tiene, falta un paso.

## Paso final (`kind: "final"`)
`prueba-final` no pertenece a una página ni lleva `route` propia obligatoria. Su `checkProfile` es `"e2e"` y su bloque `e2e` configura
`scripts/e2e_checkout.py`: `productPath` (producto con stock, sin combinaciones obligatorias), `expectHeadings` (títulos que el diseño
tiene en el pago), `expectConfirmation` (texto de la confirmación) y los nombres de las capturas de diseño (`designCheckout`,
`designConfirmation`, en `renders/`). `steps.py check prueba-final --url <tienda>` lo ejecuta y escribe `validation/prueba-final.md`.


## Pasos de la ficha que se añaden aunque el diseño no los dibuje

El diseño casi nunca incluye los estados nativos de la ficha. El paso de **producto agotado** (`producto-agotado`) debe llevar, en sus criterios de revisión (`acceptance`), el aviso de reposición:

- «Con el producto agotado sale el aviso nativo de reposición (ps_emailalerts): email para invitados, botón «Avísame cuando esté disponible» y el mensaje de confirmación con el estilo del diseño»
- «El aviso se pinta solo con el gancho de ps_emailalerts (sin botones de compartir) y no rompe el JS del módulo»

Si el diseño trae su propio bloque «Avísame», se maqueta tal cual; si no, se monta con los tokens del diseño y se anota en `validation/decisiones.md`.
