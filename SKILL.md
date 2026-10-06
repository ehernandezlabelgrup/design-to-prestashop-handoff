---
name: design-to-prestashop-handoff
description: Convierte uno o varios HTML de diseño (maqueta estática, SPA con rutas hash o prototipo de herramienta de diseño) en un paquete de handoff para que el equipo PrestaShop lo maquete en PrestaShop 9 (Hummingbird). Genera CLAUDE.md, prompt inicial, tokens.css, docs de sistema visual, interacciones, textos y plan PrestaShop, con las reglas del equipo (todo el CSS en custom.css, sin estilo en línea, todos los textos con el sistema de traducciones). Usar cuando se pida "handoff", "especificaciones para maquetar en PrestaShop", "pasar este HTML a PrestaShop" o "preparar el diseño para el equipo".
---

# design-to-prestashop-handoff

Entrada: uno o más HTML de diseño (+ su carpeta de imágenes). Salida: una carpeta `handoff-<tienda>/` (sin zip) que el equipo PrestaShop copia a su instalación y arranca con el `PROMPT-INICIAL.md`.

## Reglas que el handoff siempre impone

- **Nunca se modifica el código de un módulo de terceros (nativo de PrestaShop o de otro autor).** Todo cambio va como override en el tema hijo (`themes/<tema>/modules/<módulo>/…`), con plugins de Smarty del tema, con hooks, con CSS/JS del tema o con la configuración del propio módulo en el Back Office. Solo se edita el código de los módulos que se crean para el proyecto (`jc_*`).
- **Ficha agotada: «Avísame»**: el paso de la ficha agotada (`producto-agotado`) lleva SIEMPRE el aviso de reposición nativo (`ps_emailalerts`: email para invitados y botón «Avísame cuando esté disponible»), **aunque el diseño no lo dibuje**. Si el diseño lo trae, se maqueta como lo trae; si no, se monta con el lenguaje de cajas del diseño y se anota en `validation/decisiones.md`. Detalles y trampas en reference/prestashop-mapping.md, «Avísame en la ficha agotada». `validate.py` falla si ese paso no lo menciona en sus criterios.
- **Favoritos**: si el diseño tiene corazón, hay que mirar el módulo nativo `blockwishlist` (reference/prestashop-mapping.md, «Favoritos con blockwishlist»). Se conecta en la tarjeta de producto, en la vista rápida si el diseño la tiene y en la ficha, y la página de favoritos va en un paso aparte. Nunca se deja un corazón decorativo sin lógica.
Además de las dos de abajo: **los módulos los instala y configura Claude** (no el maquetador) y **los textos van exactamente como en el diseño**, con su traducción registrada (`tools/ps_set_translations.php`).

Están en `templates/docs/00-reglas-equipo.md.tmpl`. Las dos que más se rompen:
1. **Todo el CSS en `custom.css`**, nunca estilo en línea ni `<style>` en plantillas.
2. **Todo texto visible por el sistema de traducciones de PrestaShop** (`{l s='…' d='Shop.Theme.X'}`, `$this->trans()`, y en JS solo cadenas pasadas por `data-*` o `Media::addJsDef`).

Base por defecto: **PrestaShop 9 + Hummingbird**. Para 8.x se pasa `--ps-version 8 --base-theme classic`.

## Entradas que hay que tener (pregunta lo que falte)
- Ruta del HTML principal y su carpeta de assets.
- Nombre de la tienda y `theme-slug` (minúsculas, sin espacios).
- Versión de PrestaShop (9 por defecto).
- Brief o concepto, si existe. Si no existe, no lo inventes.
- **Pregunta siempre al usuario:** «¿Quieres que el handoff incluya la creación de datos demo (las categorías y los productos de ejemplo del HTML, y si los hay clientes y pedidos)?». Si dice que sí, se pasa `--demo-data yes`. Si no, no se generan.

## Flujo
1. **Analizar** (scripts, sin juicio):
   ```
   python3 scripts/analyze.py --entry <index.html> --out <work>
   python3 scripts/assets.py  --entry <index.html> --out <work>
   ```
   Requiere Python con `playwright` (Chromium) y `Pillow`. Detecta las rutas hash, renderiza cada página en 1440 y 390 px y escribe `raw-tokens.json`, `structure.json`, `texts.json`, `inline-styles.json`, `renders/` y `asset-map.json`. Además: el **logo** del diseño (descargado a `assets/logo/` aunque sea una URL remota o un SVG en línea) y el **texto de las páginas legales y de contenido** en `content/*.html` (para sembrar las páginas CMS). Si el aviso dice que no hay logo o falla la descarga, resuélvelo con el usuario antes de seguir. Revisa que no haya `consoleErrors` y mira las capturas.
   **La detección automática de rutas solo ve los enlaces `href="#/…"` literales.** En un SPA, lee la función del router del HTML (busca `location.hash`) y vuelve a lanzar con `--routes ruta1,ruta2/sub,…` para incluir las rutas dinámicas (ficha de producto, pasos de cuenta, checkout, confirmación…). Comprueba que el número de capturas coincide con las páginas del diseño.
   Si quien ejecuta la skill tiene PrestaShop instalado (lo normal), léelo también para fundamentar `docs/04` en datos reales y no en hipótesis:
   ```
   python3 scripts/inspect_ps.py --ps-root <ruta-prestashop> --out <work>
   ```
   Escribe `prestashop-install.json` (versión, temas con su padre, módulos). El tema activo no se lee (haría falta la BD): confírmalo en el Back Office. Si no hay instalación, `docs/04` queda como hipótesis.
   **Ajustes de imágenes:** `python3 scripts/image_types.py --work <work>` propone los tipos de imagen de PrestaShop a partir del tamaño real de cada imagen en el diseño (`image-types.json` y `.md`).
   **Datos demo (solo si el usuario dijo que sí):** `python3 scripts/find_demo_data.py --entry <index.html> --out <work>` vuelca las variables globales con datos (`demo-candidates.json`). Si el diseño no las expone (const/let), lee el fuente.
2. **Montar el paquete**:
   ```
   python3 scripts/scaffold.py --work <work> --entry <index.html> --out <handoff-tienda> --store "<Tienda>" --theme-slug <slug> [--demo-data yes]
   ```
3. **Redactar** (aquí va el juicio del modelo). Rellena todos los huecos `{{…}}` y `<!-- MODEL: … -->`:
   - `tokens.css`: nombres semánticos; cada hex y cada px tiene que salir de `raw-tokens.json`. Si el diseño usa estilos en línea o no tiene variables, deduce los tokens de los valores más frecuentes y avisa. Anota las discrepancias entre el código y lo que describan los docs.
   - `docs/01`: páginas y orden de secciones, a partir de `structure.json` y las capturas.
   - `docs/02`: color, tipografía, retícula, componentes repetidos y sus estados.
   - `docs/03`: valores literales de `transitions`, `keyframes`, `:hover` y `:focus`.
   - `docs/04`: tabla pieza → solución usando `reference/prestashop-mapping.md`. Siempre como hipótesis.
   - `docs/04` incluye también la sección «Páginas CMS y logo».
   - **Cada elemento va completo en su paso.** El buscador es parte del header y se hace entero dentro del paso del header (capa, «Novedades», filtro en vivo, estados vacíos, teclado), igual que el menú móvil y el contador de la cesta. No crees un paso aparte para una parte de un elemento ya cubierto; funde sus criterios en el paso del elemento. Solo se separa lo que depende de otra página o de datos que aún no existen (p. ej. la página de resultados).
   - **Cobertura de interacciones (obligatoria):** antes de dar por bueno `steps.json`, recorre `docs/03-interacciones.md` y rellena en `docs/09` la tabla «Cobertura de interacciones» con **todas** las interacciones (buscador en vivo, slider, filtros, galería, acordeones, toast, menú móvil…) y el paso que las implementa. Una interacción sin paso es un hueco del plan: añade el paso. Un paso que solo describe el aspecto de un elemento no cubre su comportamiento. `validate.py` lo comprueba.
   - `docs/07-ajustes-imagenes.md`: tipos de imagen a partir de `image-types.md`, con nombre, tamaño, entidades y avisos.
   - Si hay datos demo: transforma `demo-candidates.json` en `design/demo-data.json` (formato en `reference/demo-data-schema.md`, categorías y productos, con referencia `DEMO-…`), rellena `docs/08-datos-demo.md` y genera los CSV con `python3 scripts/demo_data_csv.py --demo <handoff>/design/demo-data.json --out <handoff>/design/demo-csv --image-base-url <url>`.
   - `design/steps.json` y `docs/09-plan-por-pasos.md`: el scaffold deja un esqueleto (fase 0, pre-header, header, footer y una página por ruta, con `confirm: true` donde hay duda). Complétalo mirando las renders: confirma o borra el pre-header, divide las páginas complejas en secciones (cada una con su `designSelector`, que debe existir: `python3 <handoff>/tools/steps.py verify`), pon `liveSelector`, `url` y criterios de revisión comprobables. Formato en `reference/steps-schema.md`.
   - `docs/05-textos.md`: textos de `texts.json` agrupados, con dominio de traducción propuesto.
   - `CLAUDE.md`: `SOURCE_PRIORITY` (vista de escritorio > móvil > estados > docs), `HOW_TO_READ_SOURCE` (según el formato del HTML), `PROJECT_DESCRIPTION` y `DEMO_CONTENT_NOTE`.
   - Estilos en línea del diseño (`inline-styles.json`): no se copian; se describen como clases en `docs/02`.
4. **Validar**: `python3 scripts/validate.py <handoff-tienda>`. Corrige hasta que diga OK.
5. **Entregar**: el handoff queda como **carpeta** (sin zip) dentro del proyecto donde el equipo va a maquetar. Resumen breve al usuario y su visto bueno. Si la carpeta se copia entre equipos, que no lleve `.DS_Store`.

## Modo guiado: maquetar paso a paso
El handoff trae `tools/steps.py` y `tools/compare.py`, así que el equipo no necesita la skill para maquetar. El protocolo está en el `CLAUDE.md` del handoff: Claude anuncia cada paso («empezamos por el pre-header»), lo maqueta, lanza la comprobación, dice al maquetador qué revisar y **espera su OK** antes de aprobarlo y pasar al siguiente (header, footer, páginas y secciones…). Nunca se avanza ni se aprueba sin el OK explícito.

## Orden de trabajo del equipo
**Fase 0, antes de maquetar nada:** tipos de imagen, páginas CMS y logo, y datos demo si se pidieron. Solo entonces empieza la validación página a página.

## Después del handoff: validación página a página
El equipo maqueta y valida una página cada vez. El handoff trae `docs/06-validacion-por-pagina.md` y `validation/progreso.md` (una fila por ruta). Para cada página maquetada:
```
python3 scripts/compare.py --handoff <handoff-tienda> --route <ruta> --url <url-de-la-página-en-local>
```
Compara con el render del diseño en 1440 y 390 px, comprueba las reglas automáticas (sin estilo en línea, `custom.css` el último, un H1, alt, objetivos táctiles) y escribe el informe y el estado. Se puede validar también **elemento por elemento** (un componente suelto antes de montar la página): añade `--element <nombre> --design-selector "<css>" --live-selector "<css>"`. La revisión humana (textos traducidos, interacciones, fidelidad) sigue siendo obligatoria.

## Cosas que no hay que hacer
- No inventar concepto, marca ni funcionalidades que el diseño no muestre.
- No incluir material de clientes ni credenciales en la skill. Esta skill es pública; los handoffs generados se guardan fuera del repositorio.
- No redondear valores del diseño.
- No dar el handoff por bueno sin haber pasado `validate.py`.

## Prueba final: compras y revisión de diseño

El último paso (`prueba-final`) hace dos cosas, y las dos al final de todo: 1) las tres compras con navegador real (`scripts/e2e_checkout.py`) y 2) `scripts/design_review.py`, que repasa si **siguen el diseño** las páginas estáticas (sobre, envíos, FAQ, contacto, políticas), la home, el listado, la ficha, la búsqueda, el acceso y la 404, y escribe `validation/revision-diseno.md`. `steps.py check prueba-final` lanza ambas; las páginas de sesión (cesta, pago, cuenta) usan `HANDOFF_STORAGE_STATE`. Si el diseño no trae 404, se audita lo mínimo (custom.css, un H1, sin estilos en línea ni Bootstrap por defecto) y se avisa para que lo confirme quien diseñó.

## Estados nativos que el diseño no trae

Un diseño nunca dibuja todo lo que PrestaShop genera. Antes del favicon hay un paso `estados-nativos`: se provocan en el navegador los avisos y estados nativos (aviso «Tu carrito contiene N de este producto» al recargarse la ficha, producto añadido, cantidad mínima, stock bajo, errores de formulario, descuento aplicado, 404…) y se adaptan con el mismo lenguaje de cajas del diseño (override de `_partials/notifications.tpl`). Lo que el diseño no trae se anota en `validation/decisiones.md` para que lo confirme quien diseñó. Mejor aún: pedir al diseñador que los incluya en el HTML.

## Antes de la prueba final: favicon y captura del tema
> Los dos últimos pasos del plan (`tema-identidad` y `prueba-final`) se hacen **cuando todo lo demás está maquetado y aprobado**, no pieza a pieza: `steps.py` no deja empezarlos mientras haya pasos anteriores sin aprobar. Se puede usar `e2e_checkout.py` suelto como red de seguridad mientras se maqueta el pago, pero el paso se da por hecho solo al final.
El paso `tema-identidad` genera el favicon (`scripts/theme_assets.py`: monograma con los colores y la tipografía de la marca, o el favicon del diseño si lo trae; además `apple-touch-icon.png`, `icon-192.png` e `icon-512.png`) y la captura `themes/<tema>/preview.png` (500×746, recorte vertical de la home real). `scripts/ps_set_favicon.php` lo aplica en PrestaShop (`img/favicon.ico`, `PS_FAVICON` y `PS_FAVICON_UPDATE_TIME`). Se hace con el tema ya terminado, porque la captura sale de la home real.

## Último paso del plan: prueba final de compras
El plan termina con el paso `prueba-final`, que se ejecuta con `steps.py check prueba-final --url <tienda>` (usa `scripts/e2e_checkout.py`).
Con un navegador real hace **tres compras** y compara cada pantalla con el diseño:
1. **Invitado**, solo si la tienda tiene el modo invitado activo (si no, se anota y se salta).
2. **Usuario registrado**: se registra primero y después compra.
3. **Usuario registrado con una dirección nueva** creada en el pago.
El informe `validation/prueba-final.md` separa los ❌ (algo falla) de los ⚠️ **«no cuadra con el diseño»** (altura de página frente a la captura, títulos que faltan, textos sin traducir, botones con el azul de Bootstrap, scroll horizontal). **Todo ⚠️ se informa al maquetador** y se corrige o se acepta por escrito antes de dar el proyecto por terminado. Solo se ejecuta contra una tienda de pruebas: crea clientes y pedidos.
