<?php
/**
 * bin/console de PrestaShop 9.2 con el idioma fijado antes de arrancar.
 *
 * En algunas instalaciones 9.2.0, `prestashop:theme:enable` falla con «Cannot build Language context as no languageId has been defined»
 * (ThemeManager::enable() construye el contexto de idioma antes de que nadie lo fije). Otros comandos, como prestashop:module,
 * sí lo fijan con ContextBuilderPreparer. Este envoltorio lee el bin/console REAL de la instalación (no copia ni modifica el core),
 * inyecta esa preparación antes de arrancar el kernel y ejecuta el comando igual que lo haría la consola.
 *
 * Uso (como el usuario del servidor web):
 *   sudo -u www-data php ps_console.php --ps-root=/var/www/html/tienda prestashop:theme:enable mitema --env=prod
 * El fichero tiene que ser legible por ese usuario (p. ej. copiado a /tmp).
 */
$root = null;
$args = [$argv[0]];
foreach (array_slice($argv, 1) as $arg) {
    if (str_starts_with($arg, '--ps-root=')) {
        $root = rtrim(substr($arg, 10), '/');
    } else {
        $args[] = $arg;
    }
}
if (!$root || !is_file($root . '/bin/console')) {
    fwrite(STDERR, "Uso: ps_console.php --ps-root=/ruta/prestashop <comando> [opciones]\n");
    exit(1);
}
$_SERVER['argv'] = $argv = $args;
$_SERVER['argc'] = count($args);

$code = file_get_contents($root . '/bin/console');
$code = preg_replace('/^#!.*\n/', '', $code);
$code = preg_replace('/^<\?php/', '', $code, 1);
$code = str_replace("__DIR__ . '/../", "'" . $root . "/bin/../", $code);
$code = str_replace('dirname(__FILE__, 2)', "'" . $root . "'", $code);
$needle = '$kernel = new $kernelClass($env, $debug);';
if (!str_contains($code, $needle)) {
    fwrite(STDERR, "No se reconoce el bin/console de esta versión de PrestaShop.\n");
    exit(1);
}
$prepare = <<<'PHP'
$kernel = new $kernelClass($env, $debug);
$kernel->boot();
$langId = (int) Configuration::get('PS_LANG_DEFAULT');
Context::getContext()->language = new Language($langId);
try {
    $kernel->getContainer()->get(PrestaShop\PrestaShop\Core\Context\ContextBuilderPreparer::class)->prepareLanguageId($langId);
} catch (Throwable $e) {
    fwrite(STDERR, '[ps_console] no se pudo fijar el idioma: ' . $e->getMessage() . "\n");
}
PHP;
$code = str_replace($needle, $prepare, $code);
eval($code);
