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

Hummingbird desactiva `blockwishlist` en su `theme.yml`: si el diseño tiene favoritos, se resuelven con el módulo nativo (ver «Favoritos con blockwishlist» más abajo).

## Crear un tema hijo en PrestaShop 9.2 (verificado en 9.2.0)
- El validador de temas (`ThemeValidator`) exige en el `theme.yml` del hijo: `name`, `display_name`, `version`, `author.name`, `meta.compatibility.from`, `meta.available_layouts`, `theme_settings.default_layout` y los tipos base de imagen bajo **`global_settings.image_types`** (no `global:`). Además, `preview.png`.
- Receta que funciona: copiar el `theme.yml` del padre, poner `parent: <padre>`, cambiar `name`/`display_name`/`version`/`author` y añadir los tipos propios (con `image_fitment: crop|fit|bound`) al final de `global_settings.image_types`.
- Activarlo: `php bin/console prestashop:theme:enable <tema>` (como el usuario del servidor web). Crea los tipos de imagen en la base de datos. Se revierte activando el tema anterior.

## Problemas conocidos de PrestaShop 9.2 (verificados en 9.2.0)
- La traducción es-ES de «Subcategories for %s» (`ShopThemeCatalog`) trae un `%` sobrante (`Subcategorías de %s%`) y rompe con 500 todas las páginas de categoría (la plantilla de `ps_categorytree` hace `sprintf`). Se corrige con una traducción personalizada (tabla `translation` o Internacional > Traducciones), sin tocar el core.
- **`prestashop:theme:enable` falla con «Cannot build Language context as no languageId has been defined»** en algunas instalaciones 9.2.0 (`ThemeManager::enable()` construye el contexto de idioma antes de que se fije; `prestashop:module` sí lo fija). No se toca el core: se usa `tools/ps_console.php`, que ejecuta el `bin/console` real con el idioma ya fijado: `sudo -u www-data php /tmp/ps_console.php --ps-root=<ruta> prestashop:theme:enable <tema> --env=prod` (copiarlo antes a una ruta legible por ese usuario).
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
- **Contenido que el cliente quiere gestionar (FAQ, listas ordenables)**: se hace un módulo propio con ObjectModel multiidioma, listado arrastrable con Sortable y controlador de administración oculto (`Tab id_parent=-1`) para guardar el orden por AJAX. Si hay bloques (grupos) y elementos, se permite arrastrar un elemento de un bloque a otro. El módulo pinta en un hook propio (`displayJcFaq`) y la plantilla CMS lo coloca en una marca del contenido (`.jc-faq-slot`) con `{hook h=...}` y `replace`. El acordeón NO usa `<details>` (el purificador del CMS lo elimina): botones con `aria-expanded` y `hidden`, comportamiento en custom.js.
- **Override de plantillas de módulos en el tema hijo**: si Hummingbird ya trae un override (p. ej. `modules/psgdpr/views/templates/hook/displayGDPRConsent.tpl`), se copia al tema hijo y solo se cambia el marcado y las clases, **manteniendo los atributos `data-ps-*`** que usa el JS del tema padre (activar/desactivar el envío, registrar el consentimiento). Así no hace falta JavaScript propio. Hummingbird no carga jQuery: los scripts de módulos que lo necesiten no funcionan.
- **Layout de una página** (por ejemplo Contacto a ancho completo): `theme_settings.layouts.<página>` en `theme.yml` (`contact: layout-full-width`) y `bin/console prestashop:theme:enable <tema>` para que lo lea.
- **Texto editable por el cliente en un lateral** (emails, redes): módulo nativo `ps_customtext` con `{widget name='ps_customtext'}`; el texto es contenido por idioma.
- **Navegación entre páginas CMS de una categoría** (políticas): plugin de Smarty del tema que lista `CMS::getCMSPages()` de la categoría y lee la etiqueta corta del `h2` del contenido; la numeración de apartados se hace con contadores CSS.
- **Traducciones del Back Office de módulos propios**: las cadenas `Modules.<Modulo>.Admin` también se registran en español con `ps_set_translations.php`.
- **Hooks y `prestashop:theme:enable`**: reactivar el tema vuelve a aplicar los hooks de `theme.yml` (puede reinstalar módulos demo como `ps_banner`, `ps_imageslider`, `ps_featuredproducts` en `displayHome` y dejar los propios al final). Los hooks que el diseño necesita (`displayHome` con slider propio, novedades, bloques y newsletter) deben escribirse **también en `theme.yml`**, y tras reactivar el tema hay que comprobar las posiciones. Para que el navegador reciba el CSS nuevo, además de vaciar `assets/cache` se sube `PS_CCCCSS_VERSION`.
- **Probar el enlace de recuperar contraseña**: `Customer::stampResetPasswordToken()` genera el token pero **no lo guarda**: hay que llamar a `update()`. Enlace: `getPageLink('password', true, null, ['token'=>secure_key,'id_customer'=>id,'reset_token'=>token])`. Con el correo sin configurar el paso «Revisa tu email» no se alcanza (error de envío): para probarlo, `PS_MAIL_METHOD` a 3 durante la prueba y restaurarlo.
- **Textos de las casillas del registro** salen de la configuración de cada módulo: `PSGDPR_CREATION_FORM`, `CUSTPRIV_MSG_AUTH`, `NW_CONDITIONS` (el módulo escapa el HTML de esta última: el tema lo decodifica para el enlace al aviso legal).

## Favoritos con blockwishlist (si el diseño tiene corazón o página de favoritos)
Se usa SIEMPRE el módulo nativo, sin editar su código. Dónde mirarlo y qué hacer:
- **Activarlo**: `bin/console prestashop:module enable blockwishlist` (Hummingbird lo deja desactivado).
- **En la tarjeta de producto** (y en la **vista rápida** si el diseño la tiene, y en la ficha): el corazón se conecta al módulo. Cada pieza con corazón debe incluirlo y probarse: sin sesión lleva a iniciar sesión y vuelve a la página (`?back=`), con sesión añade o quita, el estado se mantiene al recargar y el contador del header es real.
- **Trampa**: el JS de blockwishlist recorre cada `.js-product-miniature` e inyecta su botón en `.thumbnail-container`; si la tarjeta del tema no tiene ese contenedor lanza un error que **corta todo el bundle** (también `custom.js`: nada funciona). Solución en el tema: la zona de la imagen lleva la clase `thumbnail-container` y se oculta el botón que inyecta el módulo (`.card .wishlist-button { display: none }`), porque el corazón del diseño es el de la tarjeta.
- **Corazón propio del diseño con la API del módulo** (JS nativo, sin jQuery): `window.blockwishlistController` + `POST` con `ajax=1`, `action=getAllWishList` (crea la lista por defecto si no hay; devuelve `wishlists[]` con `default`), `addProductToWishList` y `deleteProductFromWishList`, con `params[idWishList]`, `params[id_product]`, `params[id_product_attribute]` y `params[quantity]`. Los productos ya guardados llegan en `window.productsAlreadyTagged` (`id_product`, `id_wishlist`). `prestashop.customer.is_logged` dice si hay sesión.
- **Contador del header**: plugin de Smarty del tema que cuenta `WishList::getAllProductByCustomer()`; el JS lo actualiza al añadir o quitar.
- **No se usan** los modales Vue del módulo (elegir o crear lista): el diseño tiene una sola lista. Si el cliente quiere varias listas, es otra decisión.
- **Página de favoritos**: paso aparte (`pagina-favoritos`): vista con la misma tarjeta del tema, estado vacío del diseño y qué ve un invitado.

## Cesta, listado y comprobación con sesión (aprendido en la práctica)
- **Choque de clases**: el widget de la cesta del header ya usa `.jc-cart`; la página de cesta usa otro prefijo (`.jc-basket`). Antes de nombrar una clase de página, buscar si el nombre ya existe en `custom.css`.
- **Selector de cantidad** (`components/qty-input.tpl`): se sustituye en el tema por el del diseño manteniendo `js-increment-button`, `js-decrement-button`, el spinner y los iconos de confirmación (ocultos con CSS); la clase propia se añade a la que pasa la plantilla, no la sustituye.
- **El JS de Hummingbird refresca la cesta por AJAX**: hay que conservar `.js-cart`, `.js-cart-list`, `.js-cart-item`, `.js-cart-summary`, `.js-cart-detailed-totals`, `.js-cart-voucher`, `data-ps-ref="voucher-*"` y `data-link-action`. Los contenedores vacíos del JS (`.js-cart-update-alert`, `.cart-grid__footer`) añaden huecos en un layout flex: se ocultan con `:not(:has(*))`.
- **Barra de envío gratis**: umbral en Preferencias de envío (`PS_SHIPPING_FREE_PRICE`; 0 = sin envío gratis). Se pinta con `<progress>` (sin estilo en línea) y un plugin de Smarty que calcula lo que falta con la cesta actual.
- **Código de descuento**: sin ninguna regla de carrito en la tienda, PrestaShop oculta el campo. Para el prototipo hay que crear la regla del diseño (p. ej. `CORNELLA10`, 10 %).
- **Límite por persona** («Máximo 2…»): no es nativo. Si el diseño lo pide, decidir con el cliente (módulo con hook de carrito) y anotarlo como desviación hasta entonces.
- **Facetas (ps_facetedsearch)**: si el diseño solo tiene un filtro (p. ej. «Ocultar agotados»), se crea la plantilla de filtros por código (tabla `layered_filter`, `buildLayeredCategories()`), y el override de `modules/ps_facetedsearch/…/facets.tpl` solo pinta esa faceta dentro de la barra del listado. Los chips de categoría son enlaces con contador real, no facetas. El orden usa `sort_orders` nativo en un `<select>` que emite el evento `updateFacets` del tema.
- **`theme.yml` heredado**: `global_settings.modules.to_disable` del padre desactiva `blockwishlist` (y otros) cada vez que se activa el tema; el hijo debe pedir `to_enable: [blockwishlist]`.
- **Comprobar páginas que dependen de la sesión** (cesta con productos, cuenta): guardar un `storage_state` de Playwright y ejecutar `HANDOFF_STORAGE_STATE=<fichero> steps.py check <paso> --url …`.
- **Cuidado con las lecturas que se cachean**: tras tocar plantillas, `Tools::clearSmartyCache()`; tras tocar CSS/JS, vaciar `assets/cache` y subir `PS_CCCCSS_VERSION` / `PS_CCCJS_VERSION`.
- **Buscador y palabras cortas**: PrestaShop no indexa palabras de menos de `PS_SEARCH_MINWORDLEN` letras (por defecto 3). Si hay productos con nombres de 2 letras (p. ej. «WO»), hay que bajar el valor a 2 y reindexar (`Search::indexation(true)`); si no, la búsqueda no los encuentra. Probarlo siempre con el nombre más corto del catálogo.
- **URL de búsqueda en pruebas**: `index.php?controller=search&s=…` redirige (302) a `/busqueda` y **pierde el término**; usar la URL amigable `/busqueda?s=…`.
- **Textos de módulos con HTML** (p. ej. condiciones de `ps_emailsubscription`): el contenido del Back Office puede llevar enlaces; en el override del tema se imprime con `nofilter` (es contenido de administración, no de visitantes).
- **Clases de Hummingbird dentro de componentes propios** (`cart-voucher__form`, `cart-summary__line`…) traen estilos que alteran el flex/altura: dejar solo los hooks `js-*` y `data-*` y estilar con clases propias.
- **El botón que inyecta blockwishlist**: tras montarse en Vue la clase `.wishlist-button` desaparece y queda `button.wishlist-button-add`; hay que ocultar ambos con CSS (el click programático sigue funcionando para abrir su modal).
- **Cuando el diseño lleva un recuento fuera de las zonas que refresca el AJAX** («N artículos» junto al H1 de la cesta), se sincroniza con el contador del header observando su contenedor (el widget se reemplaza entero).

## Ficha de producto (aprendido en la práctica)
- **El refresco por AJAX de la ficha depende de clases del núcleo** (`themes/core.js`): precio, imágenes y combinaciones solo se sustituyen dentro de un contenedor `.product-container` / `.js-product-container`; del bloque de compra solo se reemplazan `.add` (el contenedor del botón), `#product-availability` y `.product-minimal-quantity`. Si el botón «Añadir a la cesta — 349 €» debe seguir a la cantidad, va dentro de un `<div class="add">` y el contenedor principal lleva `product-container`. Conservar también `.js-images-container`, `.js-product-prices`, `.js-product-variants`, `#quantity_wanted`, `data-button-action="add-to-cart"`.
- **Plazo de entrega propio del producto**: `delivery_in_stock` solo se muestra (`{$product.delivery_information}`) si el producto tiene `additional_delivery_times = 2` (el script de datos demo lo pone). Con el producto agotado la variable sale vacía: usar `|default:$product.delivery_in_stock`.
- **Características como datos del diseño**: «Formato», «Edición» y «Fondo» (color de la tarjeta/galería) se leen de `$product.features`.
- **Una sola imagen**: la fila de miniaturas no se pinta (decisión documentada); la galería es un cuadrado de color con el marco 4:5 centrado.
- **Productos relacionados**: `ps_categoryproducts` no pinta nada si la categoría tiene un único producto y no completa con otros; si el diseño pide siempre N tarjetas, usar un plugin de Smarty del tema que lee la categoría de la tienda, excluye el producto actual y los agotados y presenta con `ProductPresenter` (el módulo no se toca).
- **Toast de «Añadido a la cesta»**: el JS de Hummingbird abre un modal Bootstrap con el HTML de `modules/ps_shoppingcart/modal.tpl`. Se conserva su estructura (`data-ps-ref="blockcart-modal"`, botón de cierre, estado accesible), se estiliza como toast fijo abajo a la derecha, se oculta el fondo oscuro y el bloqueo de scroll con `body:has(.jc-toast.show)`, y `custom.js` lo cierra a los 2400 ms.
- **Variantes como botones**: todos los tipos de grupo (select, radio, color) se pintan como radios con `data-product-attribute`; el formulario envía lo mismo y el núcleo refresca precio, stock y URL (`/4-3-wo.html#/2-idioma-espanol`).
- **Textos comunes editables una vez** (acordeones «Envío y devoluciones», «Autenticidad»): páginas CMS sin indexar y un plugin que las lee por su URL amigable.
- **Importes sin «,00»** como el diseño: `regex_replace:'/[.,]00(?=\D*$)/':''` en tarjeta, ficha y cesta.
- **Toast sin fondo oscuro**: además del CSS, el modal del toast lleva `data-bs-backdrop="false"` (Bootstrap lo lee de los atributos y el JS de Hummingbird solo pasa `focus` y `keyboard`). Al probar, contar solo los `.modal-backdrop.show`: PrestaShop deja otros `.modal-backdrop` invisibles (sin `show`) en la página.
- **Galería sin miniaturas**: el cuadrado de color debe crecer (`flex: 1`) para llenar la columna; si no, queda un hueco bajo la foto cuando la columna de compra es más alta.
- **Latencia del refresco AJAX en servidores lentos**: el JS del núcleo cancela el refresco anterior al lanzar otro; en un servidor de pruebas lento el importe del botón puede tardar unos segundos en corregirse tras añadir.

## Checkout en una página (ps_onepagecheckout, nativo de PrestaShop 9)
- **Viene incluido**: `ps_onepagecheckout` (desde 9.x) cambia la plantilla `checkout/checkout` por la suya (hook `displayOverrideTemplate`) cuando su opción está activa. Se activa con `Configuration PS_ONE_PAGE_CHECKOUT_ENABLED = 1` (Pedidos > Ajustes en el Back Office). No hace falta construir pasos propios.
- **Se maqueta con overrides del tema** en `themes/<tema>/modules/ps_onepagecheckout/views/templates/front/…` (la plantilla de página, `contact-section.tpl`, `form-fields-row.tpl`) y con CSS sobre sus clases (`.one-page-checkout__section`, `.delivery-option__*`, `.payment-option*`, `#opc-pay-button`). Su JS manda: conservar `.js-checkout-summary`, `#js-checkout-summary`, `.js-opc-*`, `#opc-pay-amount` y los `data-*`.
- **Bloques numerados 01–04** solo con CSS: `counter-reset` en el contenedor, `counter-increment` en cada `.one-page-checkout__section` y `::before` con `counter(…, decimal-leading-zero)`.
- **Resumen**: se sustituye `checkout/_partials/cart-summary.tpl`; el botón de «Ver detalle» va fuera de la sección que se refresca (el módulo conserva los `.accordion-collapse.show`).
- **Formulario de dirección = el nativo**: sus campos salen del *formato de dirección del país* (Internacional > Localización > Países > Formato de dirección) y de «Necesita número de identificación», «Contiene provincias», formato de código postal y la lista de provincias. Orden de campos, provincia obligatoria y NIF opcional se ajustan ahí (o con la tabla `address_format` / `country` por consola), no en la plantilla. Las etiquetas («Piso, puerta…») son traducciones de los campos nativos.
- **«Alias» de la dirección**: PrestaShop lo exige y el diseño no lo tiene: se renderiza oculto con un valor por defecto.
- **Transportistas por zona**: el plazo (`delay`) es por transportista, no por zona. Si el diseño muestra un plazo distinto en cada zona, hay un «Estándar» por zona (cada uno asignado solo a su zona); el precio por zona, el envío gratis desde un umbral (rangos de precio de carrito) y un «Urgente» de varias zonas con precios por zona se hacen en la tabla `delivery`. Hay que activar los países del diseño y asignarlos a zonas propias.
- **Métodos de pago**: se desactivan los que el diseño no tiene (`prestashop:module disable ps_checkpayment ps_cashondelivery ps_checkout`). Si el cliente aún no ha elegido pasarela de tarjeta, un módulo de pruebas con `PaymentOption` + controlador de validación (`validateOrder`) permite probar el flujo completo; se sustituye por la pasarela real. La transferencia usa `ps_wirepayment` (`BANK_WIRE_OWNER`, `BANK_WIRE_DETAILS`, `BANK_WIRE_ADDRESS`).
- **Condiciones de venta obligatorias**: `PS_CONDITIONS_CMS_ID` apunta a la página CMS de condiciones de venta; el texto del enlace es la traducción de «I agree to the [terms of service]…».
- **Pruebas lentas en servidores pequeños**: lanzar los scripts de navegador con `timeout` y dejarlos escribir a un fichero; un Chromium colgado puede dejar sin procesador a la propia tienda de pruebas.

## Pago en una página (ps_onepagecheckout): trampas verificadas

- El módulo **no preselecciona** método de pago (el botón de pagar queda desactivado); si el diseño trae uno elegido, preseleccionarlo desde `custom.js` (clic en la primera etiqueta una vez cargados) y ordenar los módulos en el hook `paymentOptions`.
- «Usar otra dirección de envío» **vacía el país** al abrir el modal (`resetModalFields`): sin override del módulo, reponerlo desde `custom.js` en `shown.bs.modal` y lanzar `change` para que el módulo reconstruya los campos (Provincia). Los tests deben esperar ~2,5 s antes de rellenar.
- `address-list.tpl` usa utilidades de Bootstrap con `!important` (`border`, `p-2`, `rounded-*`, `margin-top` en línea): overridearlo en el tema para poder estilarlo.
- Los contenedores de hooks vacíos del envío (`#extra_carrier`, `#hook-display-after-carrier`, `#delivery-options__hook`) suman separación: ocultarlos con `:not(:has(*))`.
- Hacer que toda la caja del método de pago active su radio: `label::after { position:absolute; inset:0 }` con la caja en `position:relative`.
- El modal de dirección tiene dos disparadores `data-type="create"` (entrega y facturación): los tests deben acotar por `data-bs-target="#modal-delivery"`.

## Confirmación de pedido y Mi cuenta: trampas verificadas

- **Confirmación (`checkout/order-confirmation.tpl`)**: el presentador no trae el país de la dirección de entrega ni el módulo de pago; un plugin del tema los saca de `Tools::getValue('id_order')` (`$order->module`, `Address`). Debe servir para tarjeta, transferencia **y contrareembolso**: el módulo decide la caja amarilla (solo transferencia, vía override de `payment_return.tpl` del módulo en el tema), el estado («Pagado / Pendiente / Pago al recibir») y los textos de «Qué pasa ahora». El nombre del pago que guarda cada módulo («Pagos por transferencia bancaria») no coincide con el del diseño: usar textos propios por módulo.
- `jc_shop_link` y similares asignan un **array** (`$jcShop.url`); usar el array como texto da `/Array`.
- La referencia del pedido es aleatoria (letras); un prefijo tipo `JC-48213` exige override de `Order::generateReference`.
- **Mi cuenta**: `customer/page.tpl` + `components/account-menu.tpl` + `customer/my-account.tpl`. Los enlaces de módulos (alertas `ps_emailalerts/account`, favoritos `blockwishlist/lists`, RGPD `psgdpr/gdpr`) se construyen con `$link->getModuleLink`; el gancho `displayCustomerAccount` los duplicaría. «Por defecto» en direcciones no existe en PrestaShop. «Tratamiento» (Sr./Sra.) se quita en Clientes > Títulos.
- `compare.py` / `steps.py check` necesitan `HANDOFF_STORAGE_STATE` (sesión con cesta o cliente) para cesta, pago, confirmación y cuenta; la página del diseño estático nunca usa la sesión.

## Avisos nativos y stock de las pruebas

- `ProductController` añade el aviso «Tu carrito contiene %1s de este producto» (notificación `info`) cada vez que la ficha se recarga con el producto en la cesta; sale por `_partials/notifications.tpl`. Un override de esa plantilla da estilo a los cuatro tipos (info, aviso, éxito, error) de toda la tienda.
- **Las compras de prueba consumen stock real**: tras pasar `e2e_checkout.py` repón el stock de los productos usados (`StockAvailable::setQuantity`) o la ficha saldrá «Agotado» al siguiente que la revise.

## «Avísame» en la ficha agotada (ps_emailalerts)

- Es nativo: el módulo pinta en el gancho `displayProductAdditionalInfo` un bloque con email (solo invitados; los clientes con sesión no lo piden) y el botón «Notify me when available». Si la plantilla de ficha del tema no pinta ese gancho, **no se ve** y nadie lo nota: incluirlo en `product-additional-info.tpl`.
- Pintar el gancho **entero** trae también los demás módulos de ese gancho (botones de compartir…): limitarlo con `{hook h='displayProductAdditionalInfo' mod='ps_emailalerts' product=$product}`.
- Override del tema de `modules/ps_emailalerts/views/templates/hook/product.tpl`: el JS del módulo busca `.js-mailalert`, sus **hijos directos** `input[type=email]` y `.js-mailalert-add`, `.gdpr_consent_wrapper` y `.js-mailalert-alerts` (donde inyecta un `<article class="alert alert-success|danger">`): conservar esa estructura y estilar `.alert` dentro de `.js-mailalert-alerts`.
- Requisitos: `MA_CUSTOMER_QTY=1`, gestión de stock activa y producto sin pedidos con stock agotado permitidos.
- El diseño casi nunca trae este bloque: se añade al paso `estados-nativos` (producto agotado: avisos de reposición) y se anota en `validation/decisiones.md`.

## Capturas estables y favicon

- **Cursor de texto en las capturas**: Playwright oculta el cursor por defecto (`caret="hide"`). **No** usar `caret="initial"`: deja el cursor parpadeando y las capturas dejan de ser estables (comprobado: 12 capturas con el valor por defecto dan 1 imagen; con `initial`, 2). Si aun así aparece, quitar el foco antes de capturar (`document.activeElement.blur()`).
- **Favicon**: la URL del favicon se versiona con `PS_IMG_UPDATE_TIME` (`FrontController::getTemplateVarShop`), no con `PS_FAVICON_UPDATE_TIME`: `ps_set_favicon.php` actualiza los dos o el navegador sigue con el antiguo.
- **Validador de colores**: `validate.py` acepta los hex de `raw-tokens.json` y también los que aparecen en `design/source/**/*.html` (hover, error y éxito no salen en las capturas).

## Provincia como campo de la dirección

- Es configuración, no código: país con `contains_states=1` (la provincia pasa a ser obligatoria), `State:name` en el formato de dirección del país y provincias activas. `scripts/ps_setup_address.php` lo hace de forma idempotente.
- **Zona de la provincia**: `Address::getZoneById` da prioridad a la zona de la provincia sobre la del país; si las provincias están en otra zona, los transportistas de la zona del país no salen. El script las pasa a la zona del país.
- El campo País debe venir antes que Provincia en el formulario; la provincia aparece al elegir país porque el formulario se recarga por país.

## Qué cuenta la revisión de diseño

- **Elementos pequeños (< 44 px)**: no se cuentan el header y el footer (son iguales en todo el sitio; `design_review.py` comprueba que lo sean), los enlaces «saltar al contenido / volver arriba» (invisibles, solo teclado) ni los enlaces dentro de texto (migas, «Ver todo»; excepción de WCAG 2.5.8). Sí cuentan los controles (botones, chips, casillas, puntos del slider): si el diseño los dibuja pequeños se acepta por escrito en `validation/decisiones.md`.
- **Diferencia visual con el diseño**: informativa, no falla (los datos de la demo nunca coinciden con los del prototipo). `compare.py --strict-visual` la vuelve a exigir.
- **Páginas públicas sin sesión**: login y registro redirigen a Mi cuenta si hay sesión. Cesta, pago y confirmación los cubre `e2e_checkout.py`; «nueva contraseña» se revisa a mano.
- **Orden del listado**: el diseño ordena «Más recientes» por el orden de los datos con los «nuevos» intercalados; con fechas de alta no se puede reproducir a la vez el orden y la etiqueta «Nuevo». `ps_seed_demo.php` da fechas descendentes en el orden del JSON (el primero, el más reciente).
