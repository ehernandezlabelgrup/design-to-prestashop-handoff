#!/usr/bin/env python3
"""Repo git del proyecto PrestaShop: se entrega la URL de un remoto PRIVADO y se sube allí.

La skill NO crea el repo: lo crea quien entrega el proyecto y pasa la URL. Aquí se comprueba
que es privado y que el usuario puede ESCRIBIR, se crean las ramas que falten (rama principal
y develop) y, con cada paso aprobado, se hace commit y push a develop.

Subcomandos (idempotentes):
  check-remote <url>                       accesible, PRIVADO y con permiso de escritura
  audit --ps-root <ruta>                   busca credenciales en lo que entraría al repo
  setup --ps-root <ruta> --remote <url>    .gitignore, git init, remoto, ramas en local y en remoto
        [--handoff <dir>]   (ramas fijas: main y develop)
        guarda la configuración en <handoff>/validation/git.json y hace el primer push
  pull --handoff <dir>                     actualiza develop desde el remoto (ff-only)
  sync --handoff <dir> --message "..."     commit + push a develop (lo llama `steps.py approve`)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GITIGNORE_TEMPLATE = next((p for p in (HERE.parent / "templates" / "gitignore-prestashop.tmpl",
                                       HERE / "gitignore-prestashop.tmpl") if p.is_file()), None)
DEVELOP = "develop"
MAIN = "main"
CONFIG_REL = Path("validation") / "git.json"
MAX_SCAN_BYTES = 512 * 1024
SECRET_PATTERNS = [
    re.compile(r"['\"]database_password['\"]\s*=>\s*['\"][^'\"]+['\"]"),
    re.compile(r"_DB_PASSWD_['\"]\s*,\s*['\"][^'\"]+['\"]"),
    re.compile(r"^\s*(DB_PASSWORD|DATABASE_PASSWORD|MYSQL_PASSWORD)\s*=\s*\S+", re.M),
    re.compile(r"['\"]cookie_key['\"]\s*=>\s*['\"][^'\"]{16,}['\"]"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def run(cmd, cwd=None, check=True):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(cmd, cwd=cwd, env=env, check=check, capture_output=True, text=True)


def remote_heads(url: str, anonymous=False):
    """Ramas del remoto, o None si no se puede leer. Anónimo = sin credenciales."""
    cmd = ["git"] + (["-c", "credential.helper=", "-c", "core.askPass="] if anonymous else [])
    result = run(cmd + ["ls-remote", "--heads", url], check=False)
    if result.returncode != 0:
        return None
    return [line.split("refs/heads/")[1] for line in result.stdout.splitlines() if "refs/heads/" in line]


def can_push(url: str) -> bool:
    """Permiso de escritura real: `push --dry-run` pide el servicio receive-pack, que exige push."""
    with tempfile.TemporaryDirectory() as tmp:
        run(["git", "init", "-q", "-b", "probe"], cwd=tmp)
        run(["git", "-c", "user.name=probe", "-c", "user.email=probe@localhost",
             "commit", "-q", "--allow-empty", "-m", "probe"], cwd=tmp)
        return run(["git", "push", "--dry-run", url, "probe:refs/heads/_write-check"], cwd=tmp, check=False).returncode == 0


def check_remote(url: str) -> list:
    """Errores (vacía = el remoto vale: existe, es privado y se puede escribir)."""
    if not re.match(r"^(https://|git@|ssh://|file://)", url):
        return [f"URL no válida: {url} (usa https://… o git@…)"]
    if remote_heads(url) is None:
        return [f"No se puede acceder a {url} con tus credenciales. ¿Existe el repo y estás autenticado?"]
    if url.startswith("https://") and remote_heads(url, anonymous=True) is not None:
        return [f"{url} es PÚBLICO (se lee sin credenciales). El repo tiene que ser privado: cámbialo y repite."]
    if not can_push(url):
        return [f"Tu usuario puede leer {url} pero NO escribir. Pide permiso de escritura (rol Write/Developer) y repite."]
    return []


def candidate_files(root: Path) -> list:
    out = run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root).stdout
    return [root / p for p in out.split("\0") if p]


def find_secrets(root: Path) -> list:
    hits = []
    for path in candidate_files(root):
        try:
            if not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            hits.append(f"{path.relative_to(root)} (no se pudo leer: {exc})")
            continue
        if any(p.search(text) for p in SECRET_PATTERNS):
            hits.append(str(path.relative_to(root)))
    return hits


def prepare_repo(root: Path, main: str):
    if not (root / ".git").exists():
        run(["git", "init", "-q", "-b", main], cwd=root)
    if GITIGNORE_TEMPLATE is None:
        sys.exit("Falta gitignore-prestashop.tmpl: sin él no se puede garantizar que no se suban credenciales.")
    (root / ".gitignore").write_text(GITIGNORE_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")


def ensure_remote(root: Path, url: str):
    current = run(["git", "remote", "get-url", "origin"], cwd=root, check=False)
    if current.returncode != 0:
        run(["git", "remote", "add", "origin", url], cwd=root)
    elif current.stdout.strip() != url:
        sys.exit(f"origin ya apunta a {current.stdout.strip()}; no lo cambio sin que lo confirmes.")


def commit_all(root: Path, message: str) -> bool:
    """Commit de todo lo no ignorado. False si no había cambios."""
    run(["git", "add", "-A"], cwd=root)
    if run(["git", "diff", "--cached", "--quiet"], cwd=root, check=False).returncode == 0 \
            and run(["git", "rev-parse", "--verify", "HEAD"], cwd=root, check=False).returncode == 0:
        return False
    run(["git", "commit", "-q", "-m", message], cwd=root)
    return True


def ensure_branches(root: Path, main: str):
    """Crea en local y en remoto la rama principal y develop si faltan."""
    heads = remote_heads(run(["git", "remote", "get-url", "origin"], cwd=root).stdout.strip()) or []
    if run(["git", "rev-parse", "--verify", main], cwd=root, check=False).returncode != 0:
        run(["git", "branch", main], cwd=root)
    if run(["git", "rev-parse", "--verify", DEVELOP], cwd=root, check=False).returncode != 0:
        run(["git", "branch", DEVELOP, main], cwd=root)
    for branch in (main, DEVELOP):
        if branch not in heads:
            run(["git", "push", "-u", "origin", branch], cwd=root)
            print(f"  · rama «{branch}» creada en el remoto")


def write_config(handoff: Path, root: Path, url: str, main: str):
    target = handoff / CONFIG_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"psRoot": str(root), "remote": url, "main": main, "develop": DEVELOP},
                                 indent=1, ensure_ascii=False), encoding="utf-8")


def cmd_audit(args) -> int:
    root = args.ps_root.resolve()
    prepare_repo(root, MAIN)
    hits = find_secrets(root)
    for hit in hits:
        print(f"❌ credenciales en {hit}: añádelo a .gitignore")
    print(f"{len(hits)} fichero(s) con credenciales." if hits else "OK · sin credenciales en lo que se subiría.")
    return 1 if hits else 0


def cmd_setup(args) -> int:
    errors = check_remote(args.remote)
    if errors:
        print("\n".join(f"❌ {e}" for e in errors))
        return 1
    root, main = args.ps_root.resolve(), MAIN
    prepare_repo(root, main)
    if find_secrets(root):
        print("❌ hay credenciales en lo que se subiría; ejecuta `audit` y corrígelo antes.")
        return 1
    ensure_remote(root, args.remote)
    commit_all(root, "chore: initial PrestaShop import")
    ensure_branches(root, main)
    if args.handoff:
        write_config(args.handoff.resolve(), root, args.remote, main)
    print(f"OK · remoto privado, con permiso de escritura y ramas {main} y {DEVELOP} listas.")
    return 0


def cmd_sync(args) -> int:
    config = json.loads((args.handoff / CONFIG_REL).read_text(encoding="utf-8"))
    root = Path(config["psRoot"])
    if find_secrets(root):
        print("❌ sync cancelado: hay credenciales en lo que se subiría (`git_repo.py audit`).")
        return 1
    run(["git", "checkout", "-q", config["develop"]], cwd=root)
    changed = commit_all(root, args.message)
    pushed = run(["git", "push", "origin", config["develop"]], cwd=root, check=False)
    if pushed.returncode != 0:
        print(f"❌ el push a {config['develop']} falló:\n{pushed.stderr.strip()}")
        return 1
    print(f"✅ subido a {config['develop']}" + ("" if changed else " (sin cambios nuevos)"))
    return 0


def cmd_pull(args) -> int:
    """Actualiza develop desde el remoto (solo fast-forward; nunca pisa trabajo local)."""
    cfg_path = args.handoff / CONFIG_REL
    if not cfg_path.is_file():
        return 0  # sin repo configurado todavía (prep-git sin hacer): nada que actualizar
    config = json.loads(cfg_path.read_text(encoding="utf-8"))
    root, branch = Path(config["psRoot"]), config["develop"]
    run(["git", "checkout", "-q", branch], cwd=root)
    before = run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    pulled = run(["git", "pull", "--ff-only", "-q", "origin", branch], cwd=root, check=False)
    if pulled.returncode != 0:
        print(f"⚠️  No se pudo actualizar {branch} (cambios locales o ramas divergentes). No toco nada; resuélvelo a mano:\n{pulled.stderr.strip()}")
        return 1
    after = run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    if before == after:
        print(f"✅ {branch} ya estaba al día")
        return 0
    changed = run(["git", "diff", "--name-only", before, after], cwd=root).stdout.split()
    print(f"✅ {branch} actualizado ({len(changed)} fichero(s) nuevos del equipo)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check-remote")
    chk.add_argument("url")
    chk.add_argument("--save", type=Path, help="carpeta de trabajo donde guardar la URL (git-remote.json) si es válida")
    sub.add_parser("audit").add_argument("--ps-root", required=True, type=Path)
    st = sub.add_parser("setup")
    st.add_argument("--ps-root", required=True, type=Path)
    st.add_argument("--remote", required=True)
    st.add_argument("--handoff", type=Path)
    sub.add_parser("pull").add_argument("--handoff", required=True, type=Path)
    sy = sub.add_parser("sync")
    sy.add_argument("--handoff", required=True, type=Path)
    sy.add_argument("--message", required=True)
    args = ap.parse_args()
    if args.cmd == "check-remote":
        errors = check_remote(args.url)
        print("\n".join(f"❌ {e}" for e in errors) if errors else "OK · remoto privado y con permiso de escritura.")
        if not errors and args.save:
            args.save.mkdir(parents=True, exist_ok=True)
            (args.save / "git-remote.json").write_text(json.dumps({"remote": args.url}, indent=1), encoding="utf-8")
            print(f"  · URL guardada en {args.save / 'git-remote.json'}")
        sys.exit(1 if errors else 0)
    sys.exit({"audit": cmd_audit, "setup": cmd_setup, "sync": cmd_sync, "pull": cmd_pull}[args.cmd](args))


if __name__ == "__main__":
    main()
