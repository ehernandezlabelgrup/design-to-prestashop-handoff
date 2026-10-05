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
