<?php
/**
 * Registra traducciones personalizadas en PrestaShop (tabla `translation`, la misma que
 * Internacional > Traducciones) sin pasar por el Back Office. Idempotente: actualiza si ya existe.
 *
 * Uso (como el usuario del servidor web):
 *   sudo -u www-data php ps_set_translations.php --ps-root=/var/www/html/tienda \
 *        --data=/ruta/legible/translations.json [--iso=es]
 *
 * translations.json: {"Shop.Theme.Global": {"Main menu": "Menú principal", "Cart": "Cesta"}, ...}
 * El dominio se escribe con puntos (Shop.Theme.Global); la herramienta lo guarda sin ellos, como PrestaShop.
 * La clave es el texto FUENTE (el de la plantilla, normalmente en inglés) y el valor es el texto del
 * diseño en el idioma --iso (por defecto «es»). Las cadenas de la skill llevan el texto del diseño tal cual.
 */
$opts = getopt('', ['ps-root:', 'data:', 'iso::']);
foreach (['ps-root', 'data'] as $required) {
    if (empty($opts[$required])) { fwrite(STDERR, "Falta --$required\n"); exit(1); }
}
$root = rtrim($opts['ps-root'], '/');
$adminDirs = glob($root . '/admin*', GLOB_ONLYDIR);
define('_PS_ADMIN_DIR_', $adminDirs[0] ?? $root . '/admin');
require $root . '/config/config.inc.php';

$langId = (int) Language::getIdByIso($opts['iso'] ?? 'es');
if (!$langId) { fwrite(STDERR, "Idioma no encontrado\n"); exit(1); }
$data = json_decode(file_get_contents($opts['data']), true);
$db = Db::getInstance();
$created = $updated = 0;
foreach ($data as $domainName => $pairs) {
    // En la tabla `translation` el dominio se guarda sin puntos: «Shop.Theme.Global» -> «ShopThemeGlobal».
    $domain = str_replace('.', '', $domainName);
    foreach ($pairs as $key => $text) {
        $where = 'id_lang=' . $langId . ' AND `key`="' . pSQL($key) . '" AND domain="' . pSQL($domain) . '"';
        $id = $db->getValue('SELECT id_translation FROM ' . _DB_PREFIX_ . 'translation WHERE ' . $where);
        if ($id) { $db->update('translation', ['translation' => pSQL($text)], 'id_translation=' . (int) $id); $updated++; }
        else { $db->insert('translation', ['id_lang' => $langId, 'key' => pSQL($key), 'translation' => pSQL($text), 'domain' => pSQL($domain), 'theme' => null], true); $created++; }
    }
}
Tools::clearAllCache();
echo "traducciones: $created nuevas, $updated actualizadas\n";
