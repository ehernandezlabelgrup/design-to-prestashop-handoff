#!/usr/bin/env python3
"""Paso 0: prepara el repositorio git privado del proyecto (la tienda entera, sin vendor ni parámetros).

Hace, en este orden, y se detiene en el primer fallo:
  1. Verifica la URL: `git ls-remote` con las credenciales del usuario. Si es https, comprueba además que SIN credenciales
     no responde (si responde, el repositorio es público y se rechaza).
  2. `git init` en la raíz de PrestaShop si aún no es un repositorio, y añade el bloque de `templates/gitignore.tmpl` al .gitignore.
  3. Configura `origin` y la rama de trabajo `handoff/<theme-slug>` (nunca toca main ni hace force push).
  4. Primer commit local «chore: initial project snapshot» y comprueba que no hay secretos en lo preparado.
NO sube nada: el primer push lo hace `tools/steps.py approve prep-git` cuando el maquetador da su OK.

Uso: git_setup.py --ps-root /var/www/html/tienda --url <git-url> --theme-slug <slug>
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
BEGIN, END = "# >>> design-to-prestashop-handoff", "# <<< design-to-prestashop-handoff"
HUGE_FILE_BYTES = 50_000_000  # GitHub rechaza ficheros de más de 100 MB; a partir de 50 MB avisa
SECRETS = ("app/config/parameters.php", "app/config/parameters.yml", "config/settings.inc.php", ".env")


def git(root: Path, *args: str, env=None, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=check, env=env)


def fail(message: str):
    sys.exit(f"✗ {message}")


def verify_url(url: str):
    probe = subprocess.run(["git", "ls-remote", url], capture_output=True, text=True,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if probe.returncode != 0:
        fail(f"no se puede acceder al repositorio con tus credenciales:\n{probe.stderr.strip()}")
    if url.startswith("https://"):
        anon = subprocess.run(["git", "-c", "credential.helper=", "ls-remote", url], capture_output=True, text=True,
                              env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"})
        if anon.returncode == 0:
            fail("el repositorio responde sin credenciales: es PÚBLICO. Tiene que ser privado.")
    print("✓ repositorio accesible y privado")


def write_gitignore(root: Path):
    block = (SKILL_ROOT / "templates" / "gitignore.tmpl").read_text(encoding="utf-8")
    target = root / ".gitignore"
    current = target.read_text(encoding="utf-8") if target.is_file() else ""
    if BEGIN in current:
        head, rest = current.split(BEGIN, 1)
        tail = rest.split(END, 1)[1].lstrip("\n") if END in rest else ""
        current = head.rstrip("\n") + ("\n\n" if head.strip() else "")
        target.write_text(current + block + ("\n" + tail if tail else ""), encoding="utf-8")
    else:
        target.write_text(current.rstrip("\n") + ("\n\n" if current.strip() else "") + block, encoding="utf-8")
    print("✓ .gitignore con vendor, parámetros, caché y contenido generado")


def assert_no_secrets(root: Path):
    staged = set(git(root, "diff", "--cached", "--name-only").stdout.split("\n"))
    leaked = sorted(f for f in staged if f in SECRETS or f.startswith("vendor/") or "/vendor/" in f)
    if leaked:
        git(root, "reset", "-q")
        fail("habría subido ficheros que no deben ir al repositorio: " + ", ".join(leaked[:10]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ps-root", required=True, type=Path)
    ap.add_argument("--url", required=True)
    ap.add_argument("--theme-slug", required=True)
    args = ap.parse_args()
    root = args.ps_root.resolve()
    if not (root / "config" / "config.inc.php").is_file():
        fail(f"{root} no parece una instalación de PrestaShop")
    verify_url(args.url)
    if git(root, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
        git(root, "init", "-q")
    if git(root, "rev-parse", "--show-toplevel").stdout.strip() != str(root):
        fail(f"{root} está dentro de otro repositorio git; el proyecto tiene que ser la raíz de PrestaShop")
    branch = f"handoff/{args.theme_slug}"
    git(root, "checkout", "-q", "-B", branch)
    remotes = git(root, "remote").stdout.split()
    git(root, "remote", "set-url" if "origin" in remotes else "add", "origin", args.url)
    write_gitignore(root)
    git(root, "add", "-A")
    assert_no_secrets(root)
    report_size(root, branch)
    if git(root, "diff", "--cached", "--quiet", check=False).returncode != 0:
        commit = git(root, "commit", "-q", "-m", "chore: initial project snapshot", check=False)
        if commit.returncode != 0:
            fail("no se pudo hacer el commit (¿falta git config user.name / user.email?):\n" + commit.stderr.strip())


def report_size(root: Path, branch: str):
    """Tamaño de lo que se subirá y de lo más pesado, para que el usuario decida si hay que ignorar más."""
    sizes, by_dir = {}, {}
    for name in filter(None, git(root, "ls-files").stdout.split("\n")):
        try:
            sizes[name] = (root / name).stat().st_size
        except OSError:
            continue
        top = name.split("/")[0]
        by_dir[top] = by_dir.get(top, 0) + sizes[name]
    total = sum(sizes.values())
    print(f"✓ rama {branch}: {len(sizes)} ficheros, {total / 1e6:.0f} MB sin comprimir (sin vendor, parámetros ni imágenes de producto)")
    print("  Lo más pesado: " + ", ".join(f"{d} {s / 1e6:.0f} MB" for d, s in sorted(by_dir.items(), key=lambda x: -x[1])[:5]))
    huge = [n for n, s in sizes.items() if s > HUGE_FILE_BYTES]
    if huge:
        git(root, "reset", "-q", check=False)
        fail(f"hay ficheros de más de {HUGE_FILE_BYTES // 1_000_000} MB que no deben ir al repositorio: " + ", ".join(huge[:5]))
    print("  Sin subir todavía: el primer push se hace al aprobar el paso prep-git.")


if __name__ == "__main__":
    main()
