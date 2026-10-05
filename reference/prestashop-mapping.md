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

## Footer en PrestaShop 9.2 (verificado)
- Un footer propio se monta con `{hook h='displayFooter' mod='ps_linklist'}` (columnas) y `{hook h='displayFooterBefore' mod='ps_socialfollow'}` (redes, que Hummingbird engancha en `displayFooterBefore`). Se overridea `modules/ps_linklist/views/templates/hook/linkblock.tpl` (variable `$linkBlocks`, con `title` y `links`) y `modules/ps_socialfollow/ps_socialfollow.tpl` (`$social_links`).
- **Bloques de ps_linklist por script**: `PrestaShop\Module\LinkList\Model\LinkBlock` con `id_hook`, `position`, `name` (por idioma), `content` = `{"cms":[ids],"product":[],"static":["contact"],"category":[ids]}` y `custom_content` = JSON por idioma. Los enlaces salen en el orden cms, producto, estáticos, personalizados y categorías.
- El texto del enlace estático «Contacto» sale del título de la página `contact` de **Tráfico y SEO** (tabla `meta_lang`), no de las traducciones.
- Redes: `BLOCKSOCIAL_INSTAGRAM|TWITTER|TIKTOK…` en `Configuration`. El orden de salida lo fija la plantilla; la etiqueta «Twitter» se cambia por «X» con una traducción personalizada de `Modules.Socialfollow.Shop`.
- El año del copyright: `{$smarty.now|date_format:'%Y'}` dentro de una cadena traducible con `sprintf`.

## Módulo propio con slides editables (jc_homeslider) en PrestaShop 9.2
- Patrón: `ObjectModel` multiidioma (`'multilang' => true`, tablas `<prefijo>jc_..._slide` y `_lang` creadas en `install()`), listado con `HelperList` (`actions` edit/delete y `active => status`) y formulario con `HelperForm` (campos `lang => true`, `file` para imagen). Se instala con `bin/console prestashop:module install`.
- **Campos con HTML permitido (`<br>`)**: el tipo debe ser `self::TYPE_HTML`; con `TYPE_STRING` PrestaShop elimina las etiquetas al guardar. El purificador convierte `<br>` en `<br />`: en la plantilla se imprime con `nofilter` (el campo ya está purificado).
- **Imagen recortada** al subirla: `ImageManager::resize($origen, $destino, $ancho, $alto, 'jpg', false, $error, $w, $h, 5, $sw, $sh, 'crop')`. Devuelve `false` si el archivo no es legible por el usuario del servidor web (permisos de carpeta).
- **Estado del slider sin `element.style`**: la pista usa `data-slide="N"` y reglas `[data-slide="N"] { transform: translateX(-N00%) }` en custom.css; el JS solo cambia el atributo, `aria-hidden`/`inert` de los slides no visibles y la clase `is-active` de los puntos.
- **Autoplay accesible**: se pausa con el ratón encima y con la pestaña oculta, y no arranca con `prefers-reduced-motion: reduce` (en ese modo el CSS global de tokens pone `--dur-slide` casi a 0).
- Un título largo editado en el Back Office puede salirse de su columna: `overflow-wrap: break-word` en el título del slide lo evita.

## Tarjeta de producto en PrestaShop 9.2 (verificado)
- `catalog/_partials/miniatures/product.tpl` es el único parcial de la tarjeta (home, listado, relacionados…). En él están disponibles `$product.features` (para sacar el color de fondo de una característica «Fondo» → clase `.jc-bg--<valor>`), `$product.flags` (`new`, `out_of_stock`), `$product.cover.bySize.<tipo>.url` (para `srcset` con tipos de imagen propios), `$product.category_name` y `$product.description_short`.
- Precio sin decimales cuando son `,00`: `{$product.price|regex_replace:'/[.,]00(?=\D*$)/':''}` (el separador es un espacio duro).
- **Tarjeta toda clicable con un corazón dentro**: enlace del título con `::after { position:absolute; inset:0; z-index:1 }`, y la caja de imagen con `z-index:2` y su propio enlace (`tabindex="-1" aria-hidden="true"`). Si la caja no tiene `z-index` y se le aplica `transform` en hover, el `::after` queda por encima del corazón y un clic en él abre la ficha.
- Con `:focus-visible` en el enlace estirado, el anillo se dibuja en el `::after` para que rodee toda la tarjeta.

## Datos que la plantilla no tiene: plugin de Smarty en el tema (PS 9.2)
- El tema puede traer sus propios plugins de Smarty en `themes/<tema>/plugins/function.<nombre>.php` (el core añade esa carpeta; el tema hijo también). Sirven para lo que la plantilla no recibe, p. ej. el total de productos de una categoría para un «Ver todo (16)»: `{jc_shop_link assign='jcShop'}` → `$jcShop.url` y `$jcShop.total` (con `Category::getProducts(..., $getTotal = true)`).
- `ps_newproducts` enseña los **productos más nuevos por fecha de alta** (ventana `PS_NB_DAYS_NEW_PRODUCT`, 20 días): es lo coherente con la etiqueta «Nuevo». Si el diseño enseña otros productos (por ejemplo, los 4 primeros del catálogo), hay que decidir con el cliente si el bloque es «Novedades» real o una selección fija (`ps_featuredproducts` con categoría Home).
- Rejilla de tarjetas del diseño: `repeat(auto-fill, minmax(min(100%, 240px), 1fr))` con `gap: clamp(16px, 2vw, 28px)`; a 1440 px caben 5 columnas y 4 tarjetas ocupan 4 de ellas.

## Páginas CMS «a sangre» con estructura propia (PS 9.2, verificado)
- El editor/purificador del CMS **conserva** `div`, `p`, `h1`–`h6`, `ul/li`, `img`, `a` con `class` y `target="_blank"`; **elimina** `section`, `figure`, `header`, `details/summary`, `svg` y `rel`. Una página con estructura de diseño se escribe con `div` y clases BEM (`.jc-about__hero`…), y el contenido sigue siendo editable en el Back Office (la imagen se sube a `img/cms/`).
- Plantilla `templates/cms/page.tpl` del tema: se detecta la página por una marca común del contenido (`strpos($cms.content, 'jc-page')`, que llevan todas las páginas a sangre: Sobre, Envíos, FAQ, Contacto, Políticas) y, solo en ese caso, se quitan el contenedor (`{block name='container_class'}`), la miga (`{block name='breadcrumb'}`), el título (`{block name='page_header_container'}`) y las clases de texto enriquecido. El resto de páginas CMS siguen igual. Los bloques se redefinen con `{$smarty.block.parent}` para el caso normal.
- `<center-column>` lleva `padding-bottom: 32px`: `.center-column:has(.jc-about) { padding-bottom: 0 }` lo quita solo en esas páginas.
- Diferencias típicas con un prototipo hecho con `style` en línea: el prototipo no fija `line-height` en el cuerpo (usa `normal`) y el tema base sí (1.5); un reset genérico `p { margin: 0 }` pisa los márgenes de clases de un solo selector (usar `.contenedor .clase`).
- **Tablas en CMS**: `table`, `thead`, `tbody`, `tr`, `th` y `td` se conservan; `colgroup` no se puede asumir. Para repartir columnas se usa `table-layout: fixed` y `th:nth-child(n)` con anchos en %. Envolverla en un `div` con `overflow-x: auto` evita el desbordamiento en móvil.
- Componentes de ayuda reutilizables (héroe con miga, bloques, tabla, cajas y aviso amarillo `.jc-callout`) viven en custom.css y los comparten las páginas de ayuda.
