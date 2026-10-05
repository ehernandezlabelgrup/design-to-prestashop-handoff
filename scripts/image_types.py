#!/usr/bin/env python3
"""Propone los tipos de imagen de PrestaShop (Diseño > Ajustes de imágenes) a partir de
cómo usa el diseño cada imagen. Lee image-usage.json (de analyze.py) y escribe
image-types.json y image-types.md en el mismo directorio.

Agrupa por proporción de la caja renderizada y por banda de tamaño. El tamaño recomendado
es el ancho máximo en CSS × RETINA_FACTOR (para pantallas 2x), redondeado y limitado al
tamaño natural de la imagen origen si se conoce. Es una propuesta: el modelo la nombra,
decide a qué entidad se aplica (productos, categorías…) y la revisa con el equipo.

Uso: image_types.py --work ./work
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

RETINA_FACTOR = 2
ROUND_TO = 10
BAND_RATIO = 1.35          # anchos dentro de esta razón van al mismo tipo
MIN_SIDE_PX = 40           # ignora iconos y decoración
KNOWN_RATIOS = {"1:1": 1.0, "4:5": 0.8, "3:4": 0.75, "2:3": 2 / 3, "3:2": 1.5, "16:10": 1.6,
                "16:9": 16 / 9, "5:4": 1.25, "4:3": 4 / 3, "21:9": 21 / 9}
RATIO_TOLERANCE = 0.04


def ratio_label(width: int, height: int) -> str:
    value = width / height
    best = min(KNOWN_RATIOS.items(), key=lambda kv: abs(kv[1] - value))
    if abs(best[1] - value) / best[1] <= RATIO_TOLERANCE:
        return best[0]
    return f"{value:.2f}:1"


def ratio_value(label: str) -> float:
    return KNOWN_RATIOS.get(label) or float(label.split(":")[0])


def collect(usage: dict) -> list:
    rows = []
    for route, by_width in usage.items():
        for viewport, items in by_width.items():
            for item in items:
                if item["w"] < MIN_SIDE_PX or item["h"] < MIN_SIDE_PX:
                    continue
                rows.append({**item, "route": route, "viewport": int(viewport)})
    return rows


def split_bands(clusters: list) -> list:
    """Agrupa clusters (listas de filas) de una misma proporción por su ancho máximo."""
    clusters = sorted(clusters, key=lambda rows: max(r["w"] for r in rows))
    bands, current = [], [clusters[0]]
    for cluster in clusters[1:]:
        if max(r["w"] for r in cluster) / max(r["w"] for r in current[0]) <= BAND_RATIO:
            current.append(cluster)
        else:
            bands.append(current)
            current = [cluster]
    bands.append(current)
    return [[row for cluster in band for row in cluster] for band in bands]


def summarize(label: str, rows: list) -> dict:
    max_w = max(r["w"] for r in rows)
    desktop = [r["w"] for r in rows if r["viewport"] >= 1000] or [0]
    mobile = [r["w"] for r in rows if r["viewport"] < 1000] or [0]
    natural = [r["nw"] for r in rows if r["nw"]]
    target_w = math.ceil(max_w * RETINA_FACTOR / ROUND_TO) * ROUND_TO
    if natural:
        target_w = min(target_w, max(natural))
    ratio = ratio_value(label)
    contexts = defaultdict(int)
    for r in rows:
        contexts[r["ctx"]] += 1
    srcs = sorted({r["src"] for r in rows})
    return {
        "ratio": label, "recommendedWidth": target_w, "recommendedHeight": round(target_w / ratio),
        "maxCssWidthDesktop": max(desktop), "maxCssWidthMobile": max(mobile),
        "usages": len(rows), "distinctImages": len(srcs), "sampleImages": srcs[:4],
        "topContexts": [c for c, _ in sorted(contexts.items(), key=lambda kv: -kv[1])[:4]],
        "routes": sorted({r["route"] for r in rows})[:8], "maxNaturalWidth": max(natural) if natural else None,
    }


def build_types(rows: list) -> list:
    # Etapa 1: mismo uso (proporción + ruta + contexto) en escritorio y móvil = un solo cluster,
    # para que un mismo componente no genere un tipo por viewport.
    by_use = defaultdict(list)
    for row in rows:
        by_use[(ratio_label(row["w"], row["h"]), row["route"], row["ctx"])].append(row)
    # Etapa 2: clusters de la misma proporción y ancho parecido comparten tipo.
    by_ratio = defaultdict(list)
    for (label, _, _), items in by_use.items():
        by_ratio[label].append(items)
    types = []
    for label, clusters in by_ratio.items():
        for band in split_bands(clusters):
            types.append(summarize(label, band))
    return sorted(types, key=lambda t: -t["usages"])


def to_markdown(types: list) -> str:
    lines = ["# Tipos de imagen propuestos (de los usos reales del diseño)", "",
             "Tamaño = ancho máximo en CSS × 2 (retina), limitado al tamaño natural de la imagen origen.", "",
             "Avisos para quien lo revise: (1) los usos con escritorio y móvil distintos se fusionan al mayor, y en móvil "
             "la caja a veces es más grande que en escritorio; (2) los tipos de imagen de PrestaShop solo valen para "
             "imágenes de producto, categoría, fabricante, etc.; las imágenes de módulos o CMS no son tipos; "
             "(3) el ajuste (`image_fitment`: fit/crop/bound) hay que decidirlo por tipo.", "",
             "| # | Proporción | Tamaño propuesto | Máx. CSS escritorio / móvil | Usos | Contextos principales | Rutas |",
             "|---|---|---|---|---|---|---|"]
    for index, t in enumerate(types, 1):
        lines.append(f"| {index} | {t['ratio']} | {t['recommendedWidth']}×{t['recommendedHeight']} | "
                     f"{t['maxCssWidthDesktop']} / {t['maxCssWidthMobile']} px | {t['usages']} | "
                     f"{'; '.join('`' + c + '`' for c in t['topContexts'])} | {', '.join(t['routes'])} |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", required=True, type=Path)
    args = ap.parse_args()
    path = args.work / "image-usage.json"
    if not path.is_file():
        sys.exit(f"Falta {path}. Ejecuta antes analyze.py")
    rows = collect(json.loads(path.read_text()))
    if not rows:
        sys.exit("El diseño no usa imágenes de tamaño relevante")
    types = build_types(rows)
    (args.work / "image-types.json").write_text(json.dumps(types, indent=1, ensure_ascii=False))
    (args.work / "image-types.md").write_text(to_markdown(types), encoding="utf-8")
    print(f"OK · {len(types)} tipos de imagen propuestos")


if __name__ == "__main__":
    main()
