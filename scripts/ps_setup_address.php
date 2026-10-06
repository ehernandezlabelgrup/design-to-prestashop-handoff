<?php
/**
 * Configuración inicial de direcciones: la PROVINCIA como un campo más (obligatorio) de la dirección, como pide el diseño.
 * Para cada país indicado:
 *   1) activa «Contiene provincias» (con ello el campo Provincia es obligatorio en el formulario y en el pago);
 *   2) añade `State:name` al formato de dirección (tras la línea de ciudad/código postal) si falta;
 *   3) activa las provincias del país y las pasa a la zona del país (PrestaShop da prioridad a la zona de la provincia sobre la del
 *      país: si difieren, los transportistas de la zona del país no salen);
 *   4) opcional --no-identification: quita el DNI/NIF obligatorio del país.
 * Idempotente. Si el país no tiene provincias cargadas (International > Ubicaciones), avisa: hay que importarlas.
 *
 * Uso (como el usuario del servidor web):
 *   sudo -u www-data php ps_setup_address.php --ps-root=/var/www/html/tienda --countries=ES,PT [--no-identification]
 */
$opts = getopt('', ['ps-root:', 'countries:', 'no-identification']);
if (empty($opts['ps-root']) || empty($opts['countries'])) {
    fwrite(STDERR, "Uso: ps_setup_address.php --ps-root=… --countries=ES,PT [--no-identification]\n");
    exit(1);
}
define('_PS_ADMIN_DIR_', glob($opts['ps-root'] . '/admin*', GLOB_ONLYDIR)[0] ?? $opts['ps-root'] . '/admin');
require $opts['ps-root'] . '/config/config.inc.php';

$db = Db::getInstance();
foreach (array_filter(array_map('trim', explode(',', $opts['countries']))) as $iso) {
    $id = (int) Country::getByIso(strtoupper($iso));
    if (!$id) {
        echo "✗ $iso: el país no existe\n";
        continue;
    }
    $country = new Country($id);
    $changes = [];
    if (!$country->contains_states) {
        $country->contains_states = 1;
        $changes[] = 'contiene provincias';
    }
    if (isset($opts['no-identification']) && $country->need_identification_number) {
        $country->need_identification_number = 0;
        $changes[] = 'sin DNI/NIF obligatorio';
    }
    $country->save();

    $formatId = (int) $db->getValue('SELECT id_address_format FROM ' . _DB_PREFIX_ . 'address_format WHERE id_country = ' . $id);
    $format = new AddressFormat($formatId ?: null);
    $text = (string) $format->format;
    if ($text !== '' && strpos($text, 'State:name') === false) {
        $lines = preg_split('/\R/', $text);
        $at = count($lines);
        foreach ($lines as $i => $line) {
            if (strpos($line, 'city') !== false || strpos($line, 'postcode') !== false) {
                $at = $i + 1;
            }
        }
        array_splice($lines, $at, 0, ['State:name']);
        $format->format = implode("\n", $lines);
        $format->id_country = $id;
        $format->save();
        $changes[] = 'State:name en el formato de dirección';
    }

    $states = (int) $db->getValue('SELECT COUNT(*) FROM ' . _DB_PREFIX_ . 'state WHERE id_country = ' . $id);
    if ($states === 0) {
        echo "⚠️ $iso: no hay provincias cargadas; impórtalas en International > Ubicaciones > Provincias\n";
    } else {
        $db->execute('UPDATE ' . _DB_PREFIX_ . 'state SET active = 1, id_zone = ' . (int) $country->id_zone . ' WHERE id_country = ' . $id);
        $changes[] = "$states provincias activas en la zona del país";
    }
    echo ($changes ? '✓ ' : '= ') . $iso . ': ' . ($changes ? implode(', ', $changes) : 'ya estaba configurado') . "\n";
}
Tools::clearSmartyCache();
Tools::clearAllCache();
