#!/usr/bin/env python3
"""Guía la maquetación paso a paso. Vive en tools/ del handoff.

Comandos (desde la raíz del handoff):
  steps.py status                      tabla de pasos y estado (y reescribe validation/progreso.md)
  steps.py next                        enseña el siguiente paso pendiente
  steps.py start <id>                  empieza un paso (exige los anteriores aprobados)
  steps.py crop <id>                   captura del elemento en el diseño (1440 y 390) para mirarlo
  steps.py check <id> --url <url>      ejecuta la comprobación automática contra PrestaShop
  steps.py approve <id>                da el paso por bueno (solo tras el OK del maquetador)
  steps.py reopen <id>                 vuelve a abrir un paso
  steps.py defer <id> [--reason ...]   aplaza un paso (solo si el maquetador lo pide); no bloquea los siguientes
  steps.py group <grupo> --mode elements|complete   cómo se maqueta una página (ver «Modos»)
  steps.py verify                      comprueba que los selectores del diseño existen

Por defecto TODO se maqueta por elementos (un paso cada vez). Opcional: si el maquetador lo pide
expresamente para una página, `group <página> --mode complete` la junta en un solo paso (y
`groups` en steps.json puede fijar «ask» para que se le pregunte antes de empezar esa página).

Reglas del protocolo: un paso cada vez; no se empieza el siguiente sin `approve`; y `approve`
solo se ejecuta cuando el maquetador ha revisado en el navegador y ha dado su OK explícito.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STEPS_FILE = ROOT / "design" / "steps.json"
STATE_FILE = ROOT / "validation" / "estado.json"
PROGRESS_FILE = ROOT / "validation" / "progreso.md"
PENDING, IN_PROGRESS, CHECK_OK, CHECK_FAIL, APPROVED = "pending", "in_progress", "check_ok", "check_fail", "approved"
DEFERRED = "deferred"
SATISFIED = (APPROVED, DEFERRED)
LOCKED_ELEMENTS = "elements"
LABELS = {PENDING: "⬜ pendiente", IN_PROGRESS: "🔧 en curso", CHECK_OK: "🟡 automático OK, falta revisión",
          CHECK_FAIL: "🔴 con fallos", APPROVED: "✅ aprobado", DEFERRED: "⏸ aplazado"}
VIEWPORTS = (1440, 390)


def load_doc() -> dict:
    if not STEPS_FILE.is_file():
        sys.exit(f"Falta {STEPS_FILE}")
    return json.loads(STEPS_FILE.read_text(encoding="utf-8"))


def load_steps() -> list:
    return load_doc()["steps"]


def group_of(step: dict):
    """Grupo de una página (sus pasos se maquetan por elementos o completos). None en prep y globales."""
    if step["kind"] in ("prep", "global"):
        return None
    return step.get("group") or step.get("route")


def group_mode(state: dict, group: str) -> str:
    """elements | complete | ask. La home y los globales van siempre por elementos."""
    return state.get("_groups", {}).get(group) or load_doc().get("groups", {}).get(group) or "elements"


def members(steps: list, group: str) -> list:
    return [s for s in steps if group_of(s) == group]


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.is_file() else {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")


def status_of(state: dict, step_id: str) -> str:
    return state.get(step_id, {}).get("status", PENDING)


def set_status(state: dict, step_id: str, status: str, note: str = ""):
    state[step_id] = {"status": status, "note": note, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    save_state(state)
    write_progress(load_steps(), state)


def find(steps: list, step_id: str) -> dict:
    for step in steps:
        if step["id"] == step_id:
            return step
    sys.exit(f"No existe el paso «{step_id}». Pasos: {', '.join(s['id'] for s in steps)}")


def blockers(steps: list, state: dict, step: dict, ignore: tuple = ()) -> list:
    """Pasos anteriores (en orden) o dependencias que aún no están aprobados ni aplazados."""
    earlier = steps[: steps.index(step)]
    pending = [s["id"] for s in earlier if status_of(state, s["id"]) not in SATISFIED and s["id"] not in ignore]
    return pending + [d for d in step.get("dependsOn", [])
                      if status_of(state, d) not in SATISFIED and d not in pending and d not in ignore]


def write_progress(steps: list, state: dict):
    lines = ["# Progreso de validación (generado por tools/steps.py; no editar a mano)", "",
             "| # | Paso | Tipo | Estado | Nota |", "|---|---|---|---|---|"]
    for index, step in enumerate(steps, 1):
        info = state.get(step["id"], {})
        lines.append(f"| {index} | `{step['id']}` · {step['title']} | {step['kind']} | "
                     f"{LABELS[info.get('status', PENDING)]} | {info.get('note', '')} |")
    PROGRESS_FILE.parent.mkdir(exist_ok=True)
    PROGRESS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_brief(steps: list, step: dict):
    index = steps.index(step) + 1
    print(f"\n## Paso {index}/{len(steps)} · {step['title']}  ({step['kind']})\n")
    print(f"**Qué hacemos:** {step['summary']}\n")
    if step.get("route"):
        print(f"**Diseño:** ruta `{step['route']}`" + (f", selector `{step['designSelector']}`" if step.get("designSelector") else ""))
        print(f"  Capturas: `renders/{step['route'].replace('/', '_')}-1440.png` y `-390.png`. "
              f"Recorte del elemento: `python3 tools/steps.py crop {step['id']}`")
    if step.get("docs"):
        print("**Lee antes:** " + ", ".join(f"`{d}`" for d in step["docs"]))
    if step.get("files"):
        print("**Archivos probables:** " + ", ".join(f"`{f}`" for f in step["files"]))
    print("\n**Criterios de revisión (los comprueba el maquetador):**")
    for item in step.get("acceptance", ["(sin criterios definidos)"]):
        print(f"- [ ] {item}")
    url_hint = step.get("url", "<url-del-paso>")
    print(f"\n**Cuando termines:** 1) `python3 tools/steps.py check {step['id']} --url {url_hint}`  "
          f"2) enséñale al maquetador qué revisar y **espera su OK**. No avances sin él.")
    print(f"**Con su OK:** `python3 tools/steps.py approve {step['id']}`. Si pide cambios, se corrigen dentro de este mismo paso.")


def cmd_status(args):
    steps, state = load_steps(), load_state()
    write_progress(steps, state)
    done = sum(status_of(state, s["id"]) == APPROVED for s in steps)
    deferred = [s["id"] for s in steps if status_of(state, s["id"]) == DEFERRED]
    print(f"Progreso: {done}/{len(steps)} pasos aprobados" + (f" · aplazados: {', '.join(deferred)}" if deferred else "") + "\n")
    for index, step in enumerate(steps, 1):
        print(f"{index:>2}. {LABELS[status_of(state, step['id'])]:<34} {step['id']} · {step['title']}")


ASK_TEXT = ("Antes de empezar «{g}», pregunta al maquetador: ¿se maqueta por elementos ({n} pasos) o la página completa de golpe?\n"
            "  → `python3 tools/steps.py group {g} --mode elements`  o  `--mode complete`")


def print_group_brief(steps: list, group: str):
    group_steps = members(steps, group)
    print(f"\n## Página completa · {group}  ({len(group_steps)} pasos en uno)\n")
    for step in group_steps:
        print(f"- **{step['title']}**: {step['summary']}")
    print("\n**Criterios de revisión (de todos los pasos del grupo):**")
    seen = []
    for step in group_steps:
        for item in step.get("acceptance", []):
            if item not in seen:
                seen.append(item)
                print(f"- [ ] {item}")
    page = next((s for s in group_steps if s["kind"] == "page"), group_steps[0])
    print(f"\n**Cuando termines:** `python3 tools/steps.py check {page['id']} --url {page.get('url', '<url>')}`, "
          "enséñale al maquetador qué revisar y **espera su OK**. Con su OK: `approve` aprueba todo el grupo.")


def resolve_target(steps: list, state: dict, step: dict):
    """Devuelve (mode, group). Si hay que preguntar al maquetador, lo imprime y devuelve None."""
    group = group_of(step)
    if not group:
        return LOCKED_ELEMENTS, None
    mode = group_mode(state, group)
    if mode == "ask":
        print(ASK_TEXT.format(g=group, n=len(members(steps, group))))
        return None
    return mode, group


def cmd_next(args):
    steps, state = load_steps(), load_state()
    for step in steps:
        if status_of(state, step["id"]) in SATISFIED:
            continue
        target = resolve_target(steps, state, step)
        if target is None:
            return
        mode, group = target
        if mode == "complete":
            print_group_brief(steps, group)
        else:
            print_brief(steps, step)
        print(f"\nPara empezar: `python3 tools/steps.py start {step['id']}`")
        return
    print("Todos los pasos están aprobados o aplazados. 🎉")


def cmd_start(args):
    steps, state = load_steps(), load_state()
    step = find(steps, args.id)
    target = resolve_target(steps, state, step)
    if target is None:
        return
    mode, group = target
    group_ids = tuple(s["id"] for s in members(steps, group)) if mode == "complete" else ()
    head = members(steps, group)[0] if mode == "complete" else step
    pending = blockers(steps, state, head, ignore=group_ids)
    if pending:
        sys.exit(f"No se puede empezar «{step['id']}»: faltan por aprobar {', '.join(pending)} "
                 "(si el maquetador quiere saltarlo: `steps.py defer <id>`)")
    for sid in group_ids or (step["id"],):
        set_status(state, sid, IN_PROGRESS)
    if mode == "complete":
        print_group_brief(steps, group)
    else:
        print_brief(steps, step)


def cmd_defer(args):
    steps, state = load_steps(), load_state()
    step = find(steps, args.id)
    set_status(state, step["id"], DEFERRED, args.reason or "aplazado por el maquetador")
    print(f"⏸ «{step['title']}» aplazado. No bloquea los siguientes; vuelve con `reopen {step['id']}`.")


def cmd_group(args):
    steps, state = load_steps(), load_state()
    if not members(steps, args.group):
        sys.exit(f"No hay un grupo «{args.group}». Grupos: {', '.join(sorted({group_of(s) for s in steps if group_of(s)}))}")
    if args.mode == "complete" and load_doc().get("groups", {}).get(args.group) == LOCKED_ELEMENTS:
        sys.exit(f"«{args.group}» se maqueta siempre por elementos")
    state.setdefault("_groups", {})[args.group] = args.mode
    save_state(state)
    print(f"«{args.group}» → {args.mode}.")


def run_compare(step: dict, url: str) -> int:
    cmd = [sys.executable, str(HERE / "compare.py"), "--handoff", str(ROOT), "--url", url]
    if step.get("designSelector") and step.get("liveSelector"):
        cmd += ["--route", step["route"], "--element", step["id"], "--design-selector", step["designSelector"],
                "--live-selector", step["liveSelector"]]
    else:
        cmd += ["--route", step["route"]]
    return subprocess.run(cmd).returncode


def cmd_check(args):
    steps, state = load_steps(), load_state()
    step = find(steps, args.id)
    group = group_of(step)
    if group and group_mode(state, group) == "complete":
        step = next((s for s in members(steps, group) if s["kind"] == "page"), step)
        step = {**step, "liveSelector": ""}   # página completa: sin selector de elemento
    if step["kind"] == "prep" or not step.get("route"):
        print("Este paso no tiene comprobación automática: se verifica a mano en el Back Office o en la tienda.")
        set_status(state, step["id"], CHECK_OK, "revisión manual")
        return
    code = run_compare(step, args.url)
    ids = [s["id"] for s in members(steps, group)] if group and group_mode(state, group) == "complete" else [step["id"]]
    for sid in ids:
        set_status(state, sid, CHECK_OK if code == 0 else CHECK_FAIL, "automático OK" if code == 0 else "ver validation/")
    report = f"validation/{step['id']}-informe.md" if step.get("liveSelector") else f"validation/{step['route'].replace('/', '_')}-informe.md"
    print(f"\nInforme: {report}")
    print("Siguiente: " + ("enseña al maquetador qué revisar y espera su OK." if code == 0
                           else "corrige los ❌ y vuelve a ejecutar check."))


def cmd_approve(args):
    steps, state = load_steps(), load_state()
    step = find(steps, args.id)
    group = group_of(step)
    ids = [s["id"] for s in members(steps, group)] if group and group_mode(state, group) == "complete" else [step["id"]]
    if status_of(state, step["id"]) not in (CHECK_OK, IN_PROGRESS):
        sys.exit(f"«{step['id']}» está en estado {status_of(state, step['id'])}: ejecuta check antes de aprobar")
    for sid in ids:
        set_status(state, sid, APPROVED, args.note or "OK del maquetador")
    nxt = next((s for s in steps if status_of(load_state(), s["id"]) not in SATISFIED), None)
    what = f"grupo «{group}» ({len(ids)} pasos)" if len(ids) > 1 else f"«{step['title']}»"
    print(f"✅ {what} aprobado." + (f" Siguiente paso: {nxt['id']} · {nxt['title']}." if nxt else " Era el último."))


def cmd_reopen(args):
    steps, state = load_steps(), load_state()
    step = find(steps, args.id)
    set_status(state, step["id"], IN_PROGRESS, "reabierto")
    print(f"Reabierto «{step['title']}».")


def design_server():
    sys.path.insert(0, str(HERE))
    import compare  # mismo directorio
    return compare, compare.serve_design(ROOT)


def cmd_crop(args):
    from playwright.sync_api import sync_playwright
    steps = load_steps()
    step = find(steps, args.id)
    if not step.get("designSelector"):
        sys.exit("Este paso no tiene designSelector")
    compare, server = design_server()
    url = f"http://127.0.0.1:{server.server_address[1]}/{compare.find_design_entry(ROOT)}#/{step['route']}"
    out = ROOT / "validation" / "pasos"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        for width in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto(url, wait_until="load")
            page.wait_for_timeout(compare.SETTLE_MS)
            target = page.locator(step["designSelector"]).first
            path = out / f"{step['id']}-diseno-{width}.png"
            target.screenshot(path=str(path))
            print(f"OK · {path.relative_to(ROOT)}")
            page.close()
        browser.close()
    server.shutdown()


def cmd_verify(args):
    from playwright.sync_api import sync_playwright
    steps = load_steps()
    compare, server = design_server()
    base = f"http://127.0.0.1:{server.server_address[1]}/{compare.find_design_entry(ROOT)}"
    bad = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        for step in steps:
            if not step.get("designSelector"):
                continue
            page.goto(f"{base}#/{step['route']}", wait_until="load")
            page.wait_for_timeout(compare.SETTLE_MS)
            count = page.locator(step["designSelector"]).count()
            print(f"{'✅' if count else '❌'} {step['id']}: «{step['designSelector']}» → {count} en {step['route']}")
            bad += 0 if count else 1
        browser.close()
    server.shutdown()
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, func in (("status", cmd_status), ("next", cmd_next), ("verify", cmd_verify)):
        sub.add_parser(name).set_defaults(func=func)
    for name, func in (("start", cmd_start), ("crop", cmd_crop), ("reopen", cmd_reopen)):
        sub.add_parser(name).add_argument("id")
        sub.choices[name].set_defaults(func=func)
    defer = sub.add_parser("defer")
    defer.add_argument("id")
    defer.add_argument("--reason", default="")
    defer.set_defaults(func=cmd_defer)
    grp = sub.add_parser("group")
    grp.add_argument("group")
    grp.add_argument("--mode", required=True, choices=["elements", "complete"])
    grp.set_defaults(func=cmd_group)
    check = sub.add_parser("check")
    check.add_argument("id")
    check.add_argument("--url", required=True)
    check.set_defaults(func=cmd_check)
    approve = sub.add_parser("approve")
    approve.add_argument("id")
    approve.add_argument("--note", default="")
    approve.set_defaults(func=cmd_approve)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
