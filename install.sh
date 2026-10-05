#!/usr/bin/env bash
# Instala la skill y sus dependencias. Idempotente: se puede ejecutar varias veces.
# Uso: ./install.sh [--project]   (por defecto instala en ~/.claude/skills; --project, en ./.claude/skills)
set -euo pipefail

REPO_URL="https://github.com/ehernandezlabelgrup/design-to-prestashop-handoff"
NAME="design-to-prestashop-handoff"
SCOPE_DIR="${HOME}/.claude/skills"
[ "${1:-}" = "--project" ] && SCOPE_DIR="$(pwd)/.claude/skills"
TARGET="${SCOPE_DIR}/${NAME}"

command -v python3 >/dev/null || { echo "Falta python3" >&2; exit 1; }
command -v git >/dev/null || { echo "Falta git" >&2; exit 1; }

mkdir -p "${SCOPE_DIR}"
if [ -d "${TARGET}/.git" ]; then
  git -C "${TARGET}" pull --ff-only
else
  git clone "${REPO_URL}" "${TARGET}"
fi

python3 -m pip install --quiet --user playwright pillow 2>/dev/null \
  || python3 -m pip install --quiet --break-system-packages playwright pillow
python3 -m playwright install chromium

python3 -c "import playwright, PIL" && echo "OK · skill instalada en ${TARGET}"
echo "Reinicia Claude Code para que la detecte y pídele: «crea el handoff de PrestaShop para <ruta/index.html>»."
