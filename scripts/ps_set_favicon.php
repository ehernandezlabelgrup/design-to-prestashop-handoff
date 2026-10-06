<?php
/**
 * Aplica un favicon en PrestaShop como lo hace Diseño > Tema y logotipo: copia el .ico a img/favicon.ico, guarda
 * PS_FAVICON y actualiza PS_FAVICON_UPDATE_TIME y PS_IMG_UPDATE_TIME (este último es el que PrestaShop añade a la URL del favicon para saltarse la caché del navegador).
 *
 * Uso (como el usuario del servidor web):
 *   sudo -u www-data php ps_set_favicon.php --ps-root=/var/www/html/tienda --ico=/ruta/favicon.ico
 */
$opts = getopt('', ['ps-root:', 'ico:']);
foreach (['ps-root', 'ico'] as $required) {
    if (empty($opts[$required])) { fwrite(STDERR, "Falta --$required\n"); exit(1); }
}
$root = rtrim($opts['ps-root'], '/');
$adminDirs = glob($root . '/admin*', GLOB_ONLYDIR);
define('_PS_ADMIN_DIR_', $adminDirs[0] ?? $root . '/admin');
require $root . '/config/config.inc.php';
if (!is_file($opts['ico'])) { fwrite(STDERR, "No existe {$opts['ico']}\n"); exit(1); }
if (!copy($opts['ico'], _PS_IMG_DIR_ . 'favicon.ico')) { fwrite(STDERR, "No se pudo escribir img/favicon.ico\n"); exit(1); }
Configuration::updateGlobalValue('PS_FAVICON', 'favicon.ico');
Configuration::updateGlobalValue('PS_FAVICON_UPDATE_TIME', time());
// La URL del favicon se versiona con PS_IMG_UPDATE_TIME (FrontController::getTemplateVarShop), no con PS_FAVICON_UPDATE_TIME: sin tocarlo el navegador sigue con el favicon antiguo en caché.
Configuration::updateGlobalValue('PS_IMG_UPDATE_TIME', time());
Tools::clearAllCache();
echo "Favicon aplicado: img/favicon.ico · PS_FAVICON_UPDATE_TIME=" . Configuration::get('PS_FAVICON_UPDATE_TIME') . " · PS_IMG_UPDATE_TIME=" . Configuration::get('PS_IMG_UPDATE_TIME') . "\n";
