# Piezas típicas de diseño → solución en PrestaShop 9

Catálogo de partida para `docs/04-plan-prestashop.md`. Son hipótesis: se validan en la instalación real y en la documentación oficial.

| Pieza del diseño | Solución habitual |
|---|---|
| Header, buscador, mini-cesta, menú | Plantillas del tema + módulos nativos (`ps_mainmenu`, `ps_searchbar`, `ps_shoppingcart`). Mega menú propio: módulo del equipo |
| Hero y bloques editoriales | Módulo propio con contenido editable en Back Office, multiidioma |
| Tarjeta de producto | Un solo parcial del tema (`catalog/_partials/miniatures/product.tpl`) |
| Listados y filtros | Categoría + `ps_facetedsearch` |
| Ficha de producto | `catalog/product.tpl` + hooks de producto |
| Reseñas | Módulo de opiniones del core o propio. No un módulo de terceros solo por estética |
| Favoritos | Módulo wishlist |
| Newsletter | `ps_emailsubscription` |
| Cuenta, login, registro, recuperar contraseña | Plantillas de `customer/` del tema |
| Carrito y checkout | Plantillas de `checkout/` del tema. Pasarelas: módulos de pago |
| Páginas legales, envíos, FAQ y sobre nosotros | Páginas CMS sembradas con el texto de `design/content/*.html` |
| Contacto | `contactform` |
| Logo | Back Office > Diseño > Tema y logo; `$shop.logo_details` en el header |
| Banners de envío gratis o avisos | Contenido editable en Back Office |
| Textos de interfaz | Siempre traducciones: `{l s='…' d='Shop.Theme.X'}` o `trans()` |
| Estilos | Siempre `assets/css/custom.css`, sin estilo en línea |

Base: Hummingbird (PS 9). Para 8.x, tema `classic` y sus plantillas equivalentes.

## `custom.css` en PrestaShop 9.2
Verificado en una instalación 9.2.0 (solo lectura): **lo carga el core**, no Hummingbird. `FrontController::setMedia()` lo registra con prioridad 1000 (`theme.css` va con 50), buscándolo primero en el tema hijo y luego en el padre, y solo si el fichero existe. Hummingbird no trae ninguno, así que basta con crear `themes/<tema>/assets/css/custom.css`. No hace falta tocar `theme.yml` ni registrarlo otra vez. Revísalo igualmente en la instalación del proyecto, porque puede cambiar entre versiones.

Hummingbird desactiva `blockwishlist` en su `theme.yml`: si el diseño tiene favoritos, hay que decidir cómo se resuelven.

## Crear un tema hijo en PrestaShop 9.2 (verificado en 9.2.0)
- El validador de temas (`ThemeValidator`) exige en el `theme.yml` del hijo: `name`, `display_name`, `version`, `author.name`, `meta.compatibility.from`, `meta.available_layouts`, `theme_settings.default_layout` y los tipos base de imagen bajo **`global_settings.image_types`** (no `global:`). Además, `preview.png`.
- Receta que funciona: copiar el `theme.yml` del padre, poner `parent: <padre>`, cambiar `name`/`display_name`/`version`/`author` y añadir los tipos propios (con `image_fitment: crop|fit|bound`) al final de `global_settings.image_types`.
- Activarlo: `php bin/console prestashop:theme:enable <tema>` (como el usuario del servidor web). Crea los tipos de imagen en la base de datos. Se revierte activando el tema anterior.

## Problemas conocidos de PrestaShop 9.2 (verificados en 9.2.0)
- La traducción es-ES de «Subcategories for %s» (`ShopThemeCatalog`) trae un `%` sobrante (`Subcategorías de %s%`) y rompe con 500 todas las páginas de categoría (la plantilla de `ps_categorytree` hace `sprintf`). Se corrige con una traducción personalizada (tabla `translation` o Internacional > Traducciones), sin tocar el core.
- `bin/console cache:clear` con 512 MB de memoria se queda sin ella: `php -d memory_limit=-1 bin/console cache:clear`.
- El CMS elimina `<details>` y `<summary>` al guardar.
- Si el dominio de la tienda no coincide con el de la URL que abres, PrestaShop redirige a la home y pierde la ruta.

## Módulos propios en PrestaShop 9.2 (verificado)
- **Instalar con la consola**: `php -d memory_limit=-1 bin/console prestashop:module install <módulo>` (como el usuario del servidor web). Llamar a `$module->install()` desde un script PHP suelto falla porque `Language::updateModulesTranslations()` necesita el contenedor de Symfony y no está arrancado.
- Si una instalación falla a medias, el módulo queda registrado sin hooks ni configuración y `install` ya no hace nada: `prestashop:module uninstall <módulo>` y volver a instalar.
- `_clearCache()` es protegido: dentro del módulo se usa; desde fuera, `Tools::clearAllCache()` o `Tools::clearSmartyCache()`.
- Los mensajes editables de un módulo (multiidioma) se guardan con `Configuration::updateValue($key, [id_lang => texto])` y se leen con `Configuration::get($key, $idLang)`.
- Un módulo de contenido simple en `displayBanner` (barra superior): `registerHook('displayBanner')` + plantilla en `views/templates/hook/` + formulario `HelperForm` con campos `lang => true`.

## Cabecera y traducciones en PrestaShop 9.2 (verificado)
- **Sticky**: el `<header id="header" class="header">` del layout envuelve todo el header (banner incluido). Para que la cabecera se quede fija sin arrastrar la barra superior, `.header { display: contents; }` y `position: sticky` en el bloque propio.
- **`{hook h='displayTop' mod='ps_mainmenu'}`** pinta solo ese módulo en ese hook: sirve para colocar menú, buscador, cesta y cuenta en una cabecera propia. En el override de `ps_mainmenu.tpl` los elementos de primer nivel están en `$menu.children` (cada uno con `label`, `url`, `type` —`cms-page`, `category`…— y `current`). Los elementos del menú se fijan en `MOD_BLOCKTOPMENU_ITEMS` (p. ej. `CAT3,CAT4,CAT5,CMS6`).
- **Cesta**: se conservan `.blockcart` y `data-refresh-url` en `ps_shoppingcart.tpl`; el JS del módulo sustituye ese bloque al actualizar y el contador se actualiza sin recargar.
- **Traducciones personalizadas** (`tools/ps_set_translations.php`): en la tabla `translation` el dominio va **sin puntos** (`Shop.Theme.Global` → `ShopThemeGlobal`), la clave es el texto fuente y `theme` es NULL. Si el dominio lleva puntos, la traducción no se aplica.
- **El índice de búsqueda no se rellena solo** con productos creados por script: hay que llamar a `Search::indexation(true)`; si no, el buscador devuelve 0 resultados.
- Los `.html` bajo `themes/` están bloqueados por `.htaccess`; el JS propio va en `assets/js/custom.js` (el core lo carga solo, como `custom.css`).
