<?php
/**
 * Carga datos demo (categorías y productos) en una instalación de PrestaShop 9 con las clases del core.
 * Alternativa al importador CSV del Back Office, que exige sesión y subir ficheros a mano.
 * Idempotente: no duplica categorías (por link_rewrite) ni productos (por referencia).
 *
 * Uso (como el usuario del servidor web, p. ej. www-data):
 *   sudo -u www-data php -d memory_limit=1G ps_seed_demo.php --ps-root=/var/www/html/tienda \
 *        --data=/ruta/legible/demo-data.json --images=/ruta/legible/uploads/ [--tax-group=1] [--vat=1.21]
 *
 * --data e --images tienen que ser legibles por ese usuario (p. ej. copiados a /tmp/…).
 * --tax-group: id del grupo de reglas de impuestos (por defecto 1, «ES Standard rate (21%)»).
 * --vat: divisor para pasar el PVP con IVA a precio sin impuestos (por defecto 1.21).
 * Los tipos de imagen (docs/07) deben existir ANTES de ejecutarlo para que se generen las miniaturas.
 */
$opts = getopt('', ['ps-root:', 'data:', 'images:', 'tax-group::', 'vat::']);
foreach (['ps-root', 'data', 'images'] as $required) {
    if (empty($opts[$required])) { fwrite(STDERR, "Falta --$required\n"); exit(1); }
}
$root = rtrim($opts['ps-root'], '/');
$adminDirs = glob($root . '/admin*', GLOB_ONLYDIR);
define('_PS_ADMIN_DIR_', $adminDirs[0] ?? $root . '/admin');
require $root . '/config/config.inc.php';

$taxGroup = (int) ($opts['tax-group'] ?? 1);
$vat = (float) ($opts['vat'] ?? 1.21);
$imagesDir = rtrim($opts['images'], '/') . '/';
$data = json_decode(file_get_contents($opts['data']), true);
$langs = Language::getLanguages(false);
$defaultLang = (int) $langs[0]['id_lang'];
$byLang = function ($value) use ($langs) { $out = []; foreach ($langs as $l) { $out[$l['id_lang']] = $value; } return $out; };
$db = Db::getInstance();

function seedCategories(array $data, int $lang, callable $byLang, Db $db): array
{
    $ids = [];
    $home = (int) Configuration::get('PS_HOME_CATEGORY');
    foreach ($data['categories'] as $c) {
        $existing = $db->getValue('SELECT id_category FROM ' . _DB_PREFIX_ . 'category_lang WHERE link_rewrite="' . pSQL($c['slug']) . '" AND id_lang=' . $lang);
        if ($existing) { $ids[$c['slug']] = (int) $existing; continue; }
        $cat = new Category();
        $cat->name = $byLang($c['name']); $cat->link_rewrite = $byLang($c['slug']);
        $cat->description = $byLang($c['description'] ?? ''); $cat->meta_title = $byLang($c['name']);
        $cat->id_parent = !empty($c['parent']) ? $ids[$c['parent']] : $home; $cat->active = 1;
        $cat->add();
        $ids[$c['slug']] = (int) $cat->id;
    }
    Category::regenerateEntireNtree();
    return $ids;
}

function importImage(int $productId, string $name, string $src, bool $cover, callable $byLang): void
{
    $image = new Image();
    $image->id_product = $productId; $image->position = Image::getHighestPosition($productId) + 1;
    $image->cover = $cover ? 1 : null; $image->legend = $byLang($name); $image->add();
    $path = $image->getPathForCreation();
    $err = 0; $tw = $th = $sw = $sh = 0;
    ImageManager::resize($src, $path . '.jpg', null, null, 'jpg', false, $err, $tw, $th, 5, $sw, $sh);
    foreach (ImageType::getImagesTypes('products', true) as $t) {
        ImageManager::resize($path . '.jpg', $path . '-' . stripslashes($t['name']) . '.jpg', $t['width'], $t['height'],
            'jpg', false, $err, $tw, $th, 5, $sw, $sh, $t['image_fitment']);
    }
}

function attributeGroupId(string $name, int $lang, callable $byLang, Db $db): int
{
    $id = $db->getValue('SELECT id_attribute_group FROM ' . _DB_PREFIX_ . 'attribute_group_lang WHERE name="' . pSQL($name) . '" AND id_lang=' . $lang);
    if ($id) { return (int) $id; }
    $g = new AttributeGroup();
    $g->name = $byLang($name); $g->public_name = $byLang($name); $g->group_type = 'radio'; $g->is_color_group = 0; $g->add();
    return (int) $g->id;
}

function attributeValueId(int $groupId, string $value, int $lang, callable $byLang, Db $db): int
{
    $id = $db->getValue('SELECT a.id_attribute FROM ' . _DB_PREFIX_ . 'attribute a JOIN ' . _DB_PREFIX_ . 'attribute_lang al USING(id_attribute) WHERE a.id_attribute_group=' . $groupId . ' AND al.name="' . pSQL($value) . '" AND al.id_lang=' . $lang);
    if ($id) { return (int) $id; }
    $a = new ProductAttribute();   // en PS 9 la clase se llama ProductAttribute
    $a->id_attribute_group = $groupId; $a->name = $byLang($value); $a->add();
    return (int) $a->id;
}

function seedProduct(array $d, array $cat, array $ctx): ?string
{
    ['lang' => $lang, 'byLang' => $byLang, 'db' => $db, 'tax' => $tax, 'vat' => $vat, 'images' => $imagesDir] = $ctx;
    if ($db->getValue('SELECT id_product FROM ' . _DB_PREFIX_ . 'product WHERE reference="' . pSQL($d['reference']) . '"')) { return null; }
    $p = new Product();
    $p->name = $byLang($d['name']); $p->link_rewrite = $byLang($d['slug']); $p->reference = $d['reference'];
    $p->description = $byLang('<p>' . htmlspecialchars($d['description'] ?? '') . '</p>');
    $p->description_short = $byLang('<p>' . htmlspecialchars($d['shortDescription'] ?? '') . '</p>');
    $p->delivery_in_stock = $byLang($d['deliveryInStock'] ?? '');
    // sin esto PrestaShop ignora el plazo propio del producto y {$product.delivery_information} sale vacío
    $p->additional_delivery_times = empty($d['deliveryInStock']) ? 1 : 2;
    $p->price = round($d['priceTaxIncl'] / $vat, 6); $p->id_tax_rules_group = $tax;
    $p->id_category_default = $cat[$d['defaultCategory']]; $p->active = 1; $p->visibility = 'both'; $p->condition = 'new';
    $p->available_for_order = 1; $p->show_price = 1; $p->indexed = 1; $p->redirect_type = '404';
    // «Nuevo» lo decide la fecha de alta: hoy para los marcados, una fecha antigua para el resto.
    $p->date_add = !empty($d['isNew']) ? date('Y-m-d H:i:s') : ($d['createdAt'] ?? '2020-01-01') . ' 00:00:00';
    $p->date_upd = $p->date_add;
    $p->add(false);
    $p->updateCategories(array_values(array_map(fn($s) => $cat[$s], $d['categories'])));
    foreach ($d['features'] ?? [] as $pos => $f) {
        $featureId = Feature::addFeatureImport($f['name'], $pos);
        Product::addFeatureProductImport($p->id, $featureId, FeatureValue::addFeatureValueImport($featureId, $f['value'], $p->id, $lang, false));
    }
    foreach ($d['images'] as $i => $rel) { importImage((int) $p->id, $d['name'], $imagesDir . basename($rel), $i === 0, $byLang); }
    if (!empty($d['combinations'])) {
        foreach ($d['combinations'] as $combo) {
            $groupId = attributeGroupId($combo['group'], $lang, $byLang, $db);
            foreach ($combo['values'] as $i => $value) {
                $c = new Combination();
                $c->id_product = $p->id; $c->reference = $d['reference'] . '-' . ($i + 1); $c->price = 0; $c->quantity = $d['stock'];
                $c->default_on = $i === 0 ? 1 : null; $c->minimal_quantity = 1; $c->add();
                $c->setAttributes([attributeValueId($groupId, $value, $lang, $byLang, $db)]);
                StockAvailable::setQuantity($p->id, $c->id, $d['stock']);
            }
        }
    } else {
        StockAvailable::setQuantity($p->id, 0, $d['stock']);   // agotado = stock 0 (sigue «disponible para pedidos» y se ve el precio)
    }
    $p->update();
    return sprintf('%s id %d %s %.2f€ qty %d', $d['reference'], $p->id, $d['name'], Product::getPriceStatic($p->id, true, null, 2), StockAvailable::getQuantityAvailableByProduct($p->id));
}

$categoryIds = seedCategories($data, $defaultLang, $byLang, $db);
echo count($categoryIds) . " categorías listas\n";
$context = ['lang' => $defaultLang, 'byLang' => $byLang, 'db' => $db, 'tax' => $taxGroup, 'vat' => $vat, 'images' => $imagesDir];
foreach ($data['products'] as $product) {
    $line = seedProduct($product, $categoryIds, $context);
    echo $line ?? "ya existe {$product['reference']}", "\n";
}
// Sin esto el buscador no encuentra los productos nuevos (el índice de búsqueda no se rellena solo).
Search::indexation(true);
echo "índice de búsqueda regenerado\n";
