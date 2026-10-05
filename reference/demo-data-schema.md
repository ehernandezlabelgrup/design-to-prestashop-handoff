# demo-data.json — formato de los datos de demostración

Lo escribe el modelo a partir de `demo-candidates.json` (salida de `find_demo_data.py`) y del fuente del diseño. Solo se genera si el usuario ha pedido datos demo. Ruta: `design/demo-data.json`.

```json
{
  "categories": [
    {"slug": "serigrafias", "name": "Serigrafías", "parent": null,
     "description": "…", "image": "uploads/x.jpg"}
  ],
  "products": [
    {"reference": "DEMO-001", "name": "Certified Idiots", "slug": "certified-idiots",
     "deliveryTime": "3-5 días", "createdAt": "2026-01-01",
     "categories": ["objetos"], "defaultCategory": "objetos",
     "priceTaxIncl": 349.0, "stock": 12, "outOfStock": false, "isNew": true,
     "shortDescription": "…", "description": "…",
     "features": [{"name": "Formato", "value": "Vinilo · 25 cm"}],
     "combinations": [{"group": "Formato", "type": "radio", "values": ["A3", "A2"]}],
     "images": ["uploads/a.jpg", "uploads/b.jpg"]}
  ],
  "customers": [
    {"email": "demo@demo.com", "password": "demodemo", "firstName": "Demo", "lastName": "Usuario",
     "addresses": [{"alias": "Casa", "address1": "…", "postcode": "…", "city": "…", "country": "España", "phone": ""}]}
  ]
}
```

Reglas:
- `parent: null` cuelga de la categoría raíz de la tienda («Home»). Los slugs de `categories` que cite un producto tienen que existir.
- `reference` único y con prefijo `DEMO-` para poder localizar y borrar todo el demo.
- Precios con IVA (`priceTaxIncl`) como en el diseño; el CSV los convierte a precio sin impuestos.
- `images` son rutas relativas a `design/source/` y tienen que existir.
- `customers` es opcional y solo para demostración (nunca contraseñas reales).
- `stock` es obligatorio (sin él, el CSV sale con todo agotado). Agotado = `stock: 0`; el producto sigue disponible para pedidos para que se vea el precio.
- `isNew: true` sin `createdAt` usa la fecha de hoy; el resto, 2020-01-01 (valor técnico, no sale del diseño).
- Los valores múltiples del CSV van con `|`: en el importador hay que elegir `|` como separador de valores múltiples.
- Genera además `combinations.csv`, `customers.csv` y `addresses.csv` si hay datos.
- Lo que el diseño no muestre, no se inventa: se omite el campo.
