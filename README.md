# design-to-prestashop-handoff

Skill de Claude Code. Convierte un HTML de diseño en un paquete de handoff para maquetarlo en PrestaShop 9 (Hummingbird), con las reglas de trabajo del equipo PrestaShop de Labelgrup:

- Todo el CSS en `custom.css`, sin estilo en línea.
- Todo texto visible con el sistema de traducciones de PrestaShop.
- No se toca el core, y hay plan aprobado antes del código.

## Instalar (se la pides a tu Claude)
Abre Claude Code y escribe: «Instala esta skill: https://github.com/ehernandezlabelgrup/design-to-prestashop-handoff».

**Instrucciones para Claude, si te piden instalarla:**
1. Clona el repo y ejecuta su instalador: `git clone https://github.com/ehernandezlabelgrup/design-to-prestashop-handoff /tmp/dph && /tmp/dph/install.sh` (añade `--project` si el usuario la quiere solo en el proyecto actual; por defecto es global, en `~/.claude/skills/`).
2. Comprueba que termina con «OK · skill instalada». Si falla una dependencia, dilo con el error exacto y no lo maquilles.
3. Dile al usuario que reinicie Claude Code para que cargue la skill.
4. No hace falta nada más: la skill no usa credenciales ni toca la instalación de PrestaShop (solo la lee).

Instalación global (recomendada): una vez por persona, sirve para todos los diseños y se actualiza con `git pull` o repitiendo el instalador. Instalación por proyecto: fija una versión de la skill dentro de un repo.

## Usar
En Claude Code: «crea el handoff de PrestaShop para `ruta/index.html`». El flujo completo está en `SKILL.md`.
