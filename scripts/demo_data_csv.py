#!/usr/bin/env python3
"""Convierte design/demo-data.json en CSV para el importador de PrestaShop
(Parámetros avanzados > Importar): categories.csv y products.csv.

Genera categories.csv, products.csv y, si hay datos, combinations.csv, customers.csv y
addresses.csv. Los valores múltiples (categorías, imágenes, características) se separan con
MULTI_SEP («|»), porque las comas aparecen en textos reales («Edición limitada, firmada»):
en el importador hay que poner «|» como separador de valores múltiples.

Uso:
  demo_data_csv.py --demo ./handoff/design/demo-data.json --out ./handoff/design/demo-csv \
                   [--image-base-url https://tienda.local/demo-img/] [--vat 21] [--tax-rules-id 1]

Las columnas se mapean en la pantalla del importador, así que los nombres de cabecera
son orientativos. El importador de PrestaShop descarga las imágenes por URL: hay que servir
`design/source/uploads/` en una URL accesible y pasarla en --image-base-url.
Es una propuesta: valida el formato en la instalación real antes de importar.
"""
import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

DEFAULT_VAT_PERCENT = 21.0
ROOT_CATEGORY = "Home"
CATEGORY_HEADER = ["Active (0/1)", "Name *", "Parent category", "Root category (0/1)", "Description",
                   "URL rewritten", "Image URL"]
MULTI_SEP = "|"
DEFAULT_NEW_DATE = "2020-01-01"
PRODUCT_HEADER = ["Active (0/1)", "Name *", "Categories (x|y|z...)", "Price tax excluded", "Tax rules ID",
                  "Reference #", "Quantity", "Short description", "Description", "URL rewritten",
                  "Available for order (0 = No, 1 = Yes)", "Image URLs (x|y|z...)",
                  "Delete existing images (0 = No, 1 = Yes)", "Feature(Name:Value:Position)",
                  "Delivery time of in-stock products", "Product creation date"]
COMBINATION_HEADER = ["Product Reference", "Attribute (Name:Type:Position)*", "Value (Value:Position)*", "Reference",
                      "Quantity", "Default (0 = No, 1 = Yes)"]
CUSTOMER_HEADER = ["Active (0/1)", "Email *", "Password *", "Last Name *", "First Name *", "Groups (x|y|z...)"]
ADDRESS_HEADER = ["Alias*", "Active (0/1)", "Customer e-mail*", "Lastname*", "Firstname*", "Address 1*", "Address 2",
                  "Zipcode*", "City*", "Country*", "Phone"]


def image_url(base: str, rel: str) -> str:
    return (base.rstrip("/") + "/" + Path(rel).name) if base else rel


def category_rows(data: dict, base: str) -> list:
    names = {c["slug"]: c["name"] for c in data.get("categories", [])}
    rows = []
    for cat in data.get("categories", []):
        parent = names.get(cat["parent"], ROOT_CATEGORY) if cat.get("parent") else ROOT_CATEGORY
        rows.append([1, cat["name"], parent, 0, cat.get("description", ""), cat["slug"],
                     image_url(base, cat["image"]) if cat.get("image") else ""])
    return rows


def price_excl(product: dict, vat: float) -> str:
    if "priceTaxExcl" in product:
        return f"{product['priceTaxExcl']:.6f}"
    return f"{product['priceTaxIncl'] / (1 + vat / 100):.6f}"


def product_rows(data: dict, base: str, vat: float, tax_rules: str) -> list:
    names = {c["slug"]: c["name"] for c in data.get("categories", [])}
    rows = []
    for p in data.get("products", []):
        if "stock" not in p:
            sys.exit(f"{p['reference']}: falta «stock» (sin él todo saldría agotado)")
        cats = MULTI_SEP.join(names.get(s, s) for s in p["categories"])
        feats = MULTI_SEP.join(f"{f['name']}:{f['value']}:{i}" for i, f in enumerate(p.get("features", [])))
        images = MULTI_SEP.join(image_url(base, i) for i in p.get("images", []))
        created = p.get("createdAt") or (date.today().isoformat() if p.get("isNew") else DEFAULT_NEW_DATE)
        # Agotado = stock 0 pero sigue «disponible para pedidos» (si no, PrestaShop oculta el precio).
        rows.append([1, p["name"], cats, price_excl(p, vat), tax_rules, p["reference"], p["stock"],
                     p.get("shortDescription", ""), p.get("description", ""), p["slug"], 1, images, 1, feats,
                     p.get("deliveryTime", ""), created])
    return rows


def combination_rows(data: dict) -> list:
    rows = []
    for p in data.get("products", []):
        for combo in p.get("combinations", []):
            kind = combo.get("type", "radio")
            for index, value in enumerate(combo["values"]):
                rows.append([p["reference"], f"{combo['group']}:{kind}:0", f"{value}:{index}",
                             f"{p['reference']}-{index + 1}", p["stock"], 1 if index == 0 else 0])
    return rows


def customer_rows(data: dict) -> tuple:
    customers, addresses = [], []
    for c in data.get("customers", []):
        customers.append([1, c["email"], c["password"], c["lastName"], c["firstName"], "Customer"])
        for a in c.get("addresses", []):
            addresses.append([a["alias"], 1, c["email"], c["lastName"], c["firstName"], a["address1"],
                              a.get("address2", ""), a["postcode"], a["city"], a["country"], a.get("phone", "")])
    return customers, addresses


def write_csv(path: Path, header: list, rows: list):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--demo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--image-base-url", default="")
    ap.add_argument("--vat", type=float, default=DEFAULT_VAT_PERCENT)
    ap.add_argument("--tax-rules-id", default="")
    args = ap.parse_args()
    if not args.demo.is_file():
        sys.exit(f"No existe {args.demo}")
    data = json.loads(args.demo.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "categories.csv", CATEGORY_HEADER, category_rows(data, args.image_base_url))
    write_csv(args.out / "products.csv", PRODUCT_HEADER,
              product_rows(data, args.image_base_url, args.vat, args.tax_rules_id))
    if combination_rows(data):
        write_csv(args.out / "combinations.csv", COMBINATION_HEADER, combination_rows(data))
    customers, addresses = customer_rows(data)
    if customers:
        write_csv(args.out / "customers.csv", CUSTOMER_HEADER, customers)
        write_csv(args.out / "addresses.csv", ADDRESS_HEADER, addresses)
    print(f"OK · {len(data.get('categories', []))} categorías, {len(data.get('products', []))} productos → {args.out}")
    if not args.image_base_url:
        print("AVISO: sin --image-base-url las imágenes quedan con ruta relativa y el importador no las descargará",
              file=sys.stderr)


if __name__ == "__main__":
    main()
