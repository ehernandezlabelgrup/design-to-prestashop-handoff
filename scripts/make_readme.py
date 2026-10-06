#!/usr/bin/env python3
"""Genera README-ENTREGA.md: qué se ha hecho en la tienda, para que cualquiera que coja el proyecto lo entienda.

Reúne, sin inventar nada: módulos propios creados (con sus ficheros), módulos de terceros (activos y, si hay inventario inicial,
cuáles se instalaron, activaron o desactivaron), overrides del tema (plantillas, módulos sobrescritos, plugins de Smarty, CSS y JS),
configuración relevante (y cambios), transportistas, zonas, estados de pedido, CMS, catálogo, traducciones, el estado de los pasos
(aprobados, aplazados, pendientes), las decisiones por confirmar y el resumen de la revisión de diseño.

Uso:
  1) al EMPEZAR:  sudo -u www-data php ps_inventory.php --ps-root=… --theme=… --out=/tmp/inicial.json  y copiarlo a design/inventario-inicial.json
  2) al TERMINAR: sudo -u www-data php ps_inventory.php … --out=/tmp/final.json  y copiarlo a design/inventario-final.json
  3) make_readme.py --handoff ./handoff-tienda --theme-dir /ruta/themes/mitema --ps-root /ruta/tienda [--own-prefix jc_]
El registro de cambios hechos a mano se escribe en validation/cambios-tienda.md (una línea por cambio) y se incluye tal cual.
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def doc_line(path: Path) -> str:
    """Primera frase útil del comentario de cabecera de un fichero (plugin PHP, plantilla Smarty o módulo)."""
    text = path.read_text(encoding="utf-8", errors="replace")[:1500]
    match = re.search(r"/\*\*(.*?)\*/", text, re.S) or re.search(r"\{\*\*(.*?)\*\}", text, re.S)
    if not match:
        return ""
    lines = [re.sub(r"^\s*\*\s?", "", ln).strip() for ln in match.group(1).splitlines()]
    return " ".join(ln for ln in lines if ln and not ln.startswith("@"))[:220]


def files_under(base: Path, pattern: str = "*") -> list:
    return sorted(str(p.relative_to(base)) for p in base.rglob(pattern) if p.is_file() and p.name != "index.php" and "/.git" not in str(p))


def theme_section(theme: Path) -> list:
    out = ["## Overrides y piezas del tema", ""]
    templates = theme / "templates"
    if templates.is_dir():
        out += [f"### Plantillas del tema ({len(files_under(templates))})", ""]
        groups = {}
        for f in files_under(templates):
            groups.setdefault(f.split("/")[0] if "/" in f else ".", []).append(f)
        out += [f"- **{g}/**: " + ", ".join(f"`{x.split('/', 1)[-1]}`" for x in fs) for g, fs in sorted(groups.items())] + [""]
    modules = theme / "modules"
    if modules.is_dir():
        out += ["### Overrides de módulos de terceros (el módulo original NO se toca)", ""]
        for mod in sorted(p for p in modules.iterdir() if p.is_dir()):
            fs = files_under(mod)
            if fs:
                out.append(f"- **{mod.name}**: " + ", ".join(f"`{f.replace('views/templates/', '')}`" for f in fs))
        out.append("")
    plugins = theme / "plugins"
    if plugins.is_dir():
        out += ["### Plugins de Smarty del tema", ""]
        out += [f"- `{p.name}` — {doc_line(p)}" for p in sorted(plugins.glob("*.php")) if p.name != "index.php"] + [""]
    assets = theme / "assets"
    if assets.is_dir():
        out += ["### CSS y JS propios", ""]
        for name in ("css/custom.css", "js/custom.js"):
            f = assets / name
            if f.is_file():
                out.append(f"- `assets/{name}` · {len(f.read_text(encoding='utf-8', errors='replace').splitlines())} líneas")
        out.append("")
    return out


def own_modules_section(inv: dict, ps_root: Path) -> list:
    own = [m for m in inv["modules"] if m["own"]]
    out = ["## Módulos propios creados", ""]
    if not own:
        return out + ["Ninguno.", ""]
    for m in own:
        base = ps_root / "modules" / m["name"]
        main = base / f"{m['name']}.php"
        out.append(f"### `{m['name']}` · {m['displayName']} · v{m['version']} · {'activo' if m['active'] else 'inactivo'}")
        if main.is_file() and doc_line(main):
            out.append(doc_line(main))
        if base.is_dir():
            out.append("Ficheros: " + ", ".join(f"`{f}`" for f in files_under(base)[:25]))
        out.append("")
    return out


def third_party_section(inv: dict, base: dict) -> list:
    out = ["## Módulos de terceros", ""]
    third = [m for m in inv["modules"] if not m["own"]]
    active = [m["name"] for m in third if m["active"]]
    out += [f"Activos ({len(active)}): " + ", ".join(f"`{n}`" for n in active), ""]
    if base:
        before = {m["name"]: m for m in base["modules"]}
        installed = [m["name"] for m in inv["modules"] if m["name"] not in before]
        activated = [m["name"] for m in inv["modules"] if m["name"] in before and m["active"] and not before[m["name"]]["active"]]
        deactivated = [m["name"] for m in inv["modules"] if m["name"] in before and not m["active"] and before[m["name"]]["active"]]
        out += ["Cambios respecto al inventario inicial:", "",
                f"- Instalados: {', '.join(f'`{n}`' for n in installed) or '—'}",
                f"- Activados: {', '.join(f'`{n}`' for n in activated) or '—'}",
                f"- Desactivados: {', '.join(f'`{n}`' for n in deactivated) or '—'}", ""]
    else:
        out += ["_No hay inventario inicial (`design/inventario-inicial.json`): no se puede decir qué módulos se instalaron o activaron durante el trabajo._", ""]
    return out


def config_section(inv: dict, base: dict) -> list:
    out = ["## Configuración relevante", "", "| Clave | Valor | Antes |", "|---|---|---|"]
    before = (base or {}).get("config", {})
    for key, value in inv["config"].items():
        old = before.get(key, "—") if base else "—"
        mark = " ✱" if base and old != value else ""
        out.append(f"| `{key}` | {value if value not in (False, None, '') else '—'}{mark} | {old if old not in (False, None, '') else '—'} |")
    return out + ["", "✱ = cambiado durante el trabajo." if base else "", ""]


def shop_section(inv: dict) -> list:
    out = ["## Estado de la tienda", ""]
    out += ["**Transportistas**: " + "; ".join(f"{c['name']} ({c['delay']}; zonas: {', '.join(c['zones']) or '—'}{'' if c['active'] else '; inactivo'})" for c in inv["carriers"]), ""]
    out += ["**Zonas con países activos**: " + ", ".join(f"{z['name']} ({z['paises_activos']})" for z in inv["zones"] if int(z["paises_activos"])), ""]
    out += ["**Estados de pedido**: " + ", ".join(f"{s['id']}·{s['name']}" for s in inv["order_states"]), ""]
    out += ["**Páginas CMS**: " + ", ".join(f"{c['id']}·{c['title']}" for c in inv["cms"]), ""]
    out += [f"**Catálogo**: {inv['categories']} categorías activas, {inv['products']} productos activos ({inv['demo_products']} de demostración, referencia `DEMO-…`).", ""]
    out += [f"**Tipos de imagen**: {len(inv['image_types'])} (`" + "`, `".join(t["name"] for t in inv["image_types"] if t["name"].startswith(('jc', 'brand'))) + "` propios si los hay)", ""]
    out += ["**Traducciones personalizadas** (" + inv["language"] + "): " + ", ".join(f"{d} ({n})" for d, n in inv["translations_es"].items()), ""]
    return out


def steps_section(handoff: Path) -> list:
    steps = (read_json(handoff / "design" / "steps.json") or {}).get("steps", [])
    state = read_json(handoff / "validation" / "estado.json") or {}
    def status(step_id):
        value = state.get(step_id, {})
        return value.get("status", "") if isinstance(value, dict) else str(value)
    done = [s for s in steps if status(s["id"]) in ("aprobado", "approved")]
    deferred = [s for s in steps if status(s["id"]) in ("aplazado", "deferred")]
    pending = [s for s in steps if s not in done and s not in deferred]
    out = ["## Pasos del plan", "", f"{len(done)} de {len(steps)} aprobados · {len(deferred)} aplazados · {len(pending)} pendientes.", ""]
    for title, group in (("Aplazados", deferred), ("Pendientes", pending)):
        if group:
            out += [f"**{title}**: " + ", ".join(f"`{s['id']}`" for s in group), ""]
    return out


def attach(handoff: Path, rel: str, title: str) -> list:
    f = handoff / rel
    if not f.is_file():
        return []
    return [f"## {title}", "", f.read_text(encoding="utf-8").strip(), ""]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--handoff", required=True, type=Path)
    ap.add_argument("--theme-dir", required=True, type=Path)
    ap.add_argument("--ps-root", required=True, type=Path)
    ap.add_argument("--inventory", type=Path, help="por defecto design/inventario-final.json")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    inv = read_json(args.inventory or args.handoff / "design" / "inventario-final.json")
    if not inv:
        raise SystemExit("Falta el inventario final: ejecuta ps_inventory.php (ver la cabecera de este script).")
    base = read_json(args.handoff / "design" / "inventario-inicial.json")
    out = [f"# Entrega · {inv['theme']}", "",
           f"_Generado el {date.today().isoformat()} por `make_readme.py`. PrestaShop {inv['prestashop']} · PHP {inv['php']} · tema hijo `{inv['theme']}`._", "",
           "Este documento resume **qué se ha hecho** en la tienda: qué módulos se crearon o se tocaron, qué se sobrescribe en el tema y qué se configuró. "
           "Regla de oro del trabajo: los módulos de terceros nunca se editan; todo se hace con overrides en el tema hijo, y solo los módulos propios se modifican.", ""]
    out += own_modules_section(inv, args.ps_root) + third_party_section(inv, base) + theme_section(args.theme_dir)
    out += config_section(inv, base) + shop_section(inv) + steps_section(args.handoff)
    out += attach(args.handoff, "validation/cambios-tienda.md", "Cambios hechos a mano en la tienda")
    out += attach(args.handoff, "validation/decisiones.md", "Decisiones por confirmar con quien diseñó")
    out += attach(args.handoff, "validation/revision-diseno.md", "Última revisión de diseño")
    out += ["## Cómo seguir", "", "- `python3 tools/steps.py status` · estado de los pasos; `python3 tools/steps.py check <paso> --url <url>` · comprobación automática.",
            "- `tools/e2e_checkout.py` · compras de prueba (consumen stock real: repónlo después). `tools/design_review.py` · revisión de diseño de páginas.",
            "- Tras cambiar CSS/JS: vaciar `assets/cache` del tema y subir `PS_CCCCSS_VERSION` / `PS_CCCJS_VERSION`.", ""]
    target = args.out or args.handoff / "README-ENTREGA.md"
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"README escrito en {target} · {len(out)} líneas")


if __name__ == "__main__":
    main()
