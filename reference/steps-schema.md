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

- `kind`: `prep` (fase 0, sin comprobación automática), `global` (pre-header, header, footer), `section` (parte de una página) o `page` (página entera).
- `designSelector`: selector CSS del elemento en el diseño de origen, que **tiene que existir** (`tools/steps.py verify` lo comprueba). `liveSelector`: el equivalente en PrestaShop; si falta, el paso se comprueba como página entera.
- `url`: ruta de PrestaShop a abrir para comprobarlo (se pasa completa en `check --url`).
- `dependsOn`: ids que deben estar aprobados. Además, **cada paso exige todos los anteriores aprobados**.
- `confirm: true`: lo pone el esqueleto en pasos inciertos (p. ej. pre-header). El modelo lo confirma (quita la marca) o borra el paso.
- Los pasos de sección ponen delante el de su página y heredan `route`.
- Los criterios (`acceptance`) deben ser comprobables por una persona mirando el navegador.
