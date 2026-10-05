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
