<?php
/**
 * Inventario de la tienda PrestaShop para el README de entrega: módulos (propios y de terceros, activos o no), transportistas,
 * zonas, estados de pedido, páginas CMS, categorías y productos, tipos de imagen, traducciones personalizadas y los valores de
 * configuración que importan para maquetar. Solo lee; no modifica nada.
 *
 * Uso (como el usuario del servidor web):
 *   sudo -u www-data php ps_inventory.php --ps-root=/var/www/html/tienda --theme=mitema --out=/tmp/inventario.json [--own-prefix=jc_] [--config-prefix=JC_]
 * El fichero de salida debe estar en una carpeta que el usuario del servidor web pueda escribir (p. ej. /tmp).
 */
$opts = getopt('', ['ps-root:', 'theme:', 'out:', 'own-prefix::', 'config-prefix::']);
foreach (['ps-root', 'theme', 'out'] as $required) {
    if (empty($opts[$required])) {
        fwrite(STDERR, "Falta --$required\n");
        exit(1);
    }
}
define('_PS_ADMIN_DIR_', glob($opts['ps-root'] . '/admin*', GLOB_ONLYDIR)[0] ?? $opts['ps-root'] . '/admin');
require $opts['ps-root'] . '/config/config.inc.php';

$db = Db::getInstance();
$p = _DB_PREFIX_;
$es = (int) Language::getIdByIso('es') ?: (int) Configuration::get('PS_LANG_DEFAULT');
$ownPrefix = $opts['own-prefix'] ?? '';
$configPrefix = $opts['config-prefix'] ?? '';

$modules = [];
foreach ($db->executeS("SELECT name, active, version FROM {$p}module ORDER BY name") as $row) {
    $instance = Module::getInstanceByName($row['name']);
    $author = $instance ? (string) $instance->author : '';
    $modules[] = [
        'name' => $row['name'], 'displayName' => $instance ? (string) $instance->displayName : $row['name'], 'version' => $row['version'],
        'active' => (bool) $row['active'], 'author' => $author,
        'own' => ($ownPrefix !== '' && strpos($row['name'], $ownPrefix) === 0) || (!in_array($author, ['PrestaShop', ''], true) && $ownPrefix === ''),
    ];
}

$carriers = [];
foreach ($db->executeS("SELECT c.id_carrier, c.name, c.active, cl.delay FROM {$p}carrier c LEFT JOIN {$p}carrier_lang cl ON cl.id_carrier = c.id_carrier AND cl.id_lang = $es WHERE c.deleted = 0 ORDER BY c.id_carrier") as $c) {
    $zones = array_column($db->executeS("SELECT z.name FROM {$p}carrier_zone cz JOIN {$p}zone z ON z.id_zone = cz.id_zone WHERE cz.id_carrier = " . (int) $c['id_carrier']), 'name');
    $carriers[] = ['name' => $c['name'], 'delay' => $c['delay'], 'active' => (bool) $c['active'], 'zones' => $zones];
}

$keys = ['PS_ONE_PAGE_CHECKOUT_ENABLED', 'PS_GUEST_CHECKOUT_ENABLED', 'PS_CONDITIONS', 'PS_CONDITIONS_CMS_ID', 'PS_SHIPPING_FREE_PRICE',
    'PS_PRODUCTS_PER_PAGE', 'PS_PRODUCTS_ORDER_BY', 'PS_COUNTRY_DEFAULT', 'PS_CUSTOMER_BIRTHDATE', 'MA_CUSTOMER_QTY', 'PS_STOCK_MANAGEMENT',
    'PS_CSS_THEME_CACHE', 'PS_JS_THEME_CACHE', 'PS_SHOP_ENABLE', 'PS_FAVICON', 'PS_DISPLAY_JQUERY'];
foreach ($db->executeS("SELECT name FROM {$p}configuration" . ($configPrefix !== '' ? " WHERE name LIKE '" . pSQL($configPrefix) . "%'" : ' WHERE 1=0')) as $row) {
    $keys[] = $row['name'];
}
$config = [];
foreach (array_unique($keys) as $key) {
    $config[$key] = Configuration::get($key);
}

$translations = [];
foreach ($db->executeS("SELECT domain, COUNT(*) AS n FROM {$p}translation WHERE id_lang = $es GROUP BY domain ORDER BY domain") as $row) {
    $translations[$row['domain']] = (int) $row['n'];
}

$inventory = [
    'prestashop' => _PS_VERSION_, 'php' => PHP_VERSION, 'theme' => $opts['theme'], 'language' => Language::getIsoById($es),
    'modules' => $modules,
    'carriers' => $carriers,
    'zones' => $db->executeS("SELECT z.name, z.active, (SELECT COUNT(*) FROM {$p}country c WHERE c.id_zone = z.id_zone AND c.active = 1) AS paises_activos FROM {$p}zone z ORDER BY z.id_zone"),
    'order_states' => $db->executeS("SELECT os.id_order_state AS id, osl.name, os.paid FROM {$p}order_state os JOIN {$p}order_state_lang osl ON osl.id_order_state = os.id_order_state AND osl.id_lang = $es WHERE os.deleted = 0 ORDER BY os.id_order_state"),
    'cms' => $db->executeS("SELECT c.id_cms AS id, cl.meta_title AS title FROM {$p}cms c JOIN {$p}cms_lang cl ON cl.id_cms = c.id_cms AND cl.id_lang = $es ORDER BY c.id_cms"),
    'categories' => (int) $db->getValue("SELECT COUNT(*) FROM {$p}category WHERE active = 1 AND id_parent > 0"),
    'products' => (int) $db->getValue("SELECT COUNT(*) FROM {$p}product WHERE active = 1"),
    'demo_products' => (int) $db->getValue("SELECT COUNT(*) FROM {$p}product WHERE reference LIKE 'DEMO-%'"),
    'image_types' => $db->executeS("SELECT name, width, height, products, categories FROM {$p}image_type ORDER BY name"),
    'translations_es' => $translations,
    'config' => $config,
];
$json = json_encode($inventory, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_INVALID_UTF8_SUBSTITUTE);
if ($json === false) {
    fwrite(STDERR, 'No se pudo codificar el inventario: ' . json_last_error_msg() . "\n");
    exit(1);
}
if (@file_put_contents($opts['out'], $json) === false) {
    fwrite(STDERR, 'No se pudo escribir ' . $opts['out'] . " (usa una ruta nueva que el usuario del servidor web pueda crear, p. ej. /tmp/inventario.json)\n");
    exit(1);
}
echo 'Inventario escrito en ' . $opts['out'] . ' · ' . count($modules) . " módulos, " . count($carriers) . " transportistas\n";
