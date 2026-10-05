# design-to-prestashop-handoff

Skill de Claude Code. Convierte un HTML de diseño en un paquete de handoff para maquetarlo en PrestaShop 9 (Hummingbird), con las reglas de trabajo del equipo PrestaShop de Labelgrup:

- Todo el CSS en `custom.css`, sin estilo en línea.
- Todo texto visible con el sistema de traducciones de PrestaShop.
- No se toca el core, y hay plan aprobado antes del código.

## Instalar
```
git clone https://github.com/ehernandezlabelgrup/design-to-prestashop-handoff ~/.claude/skills/design-to-prestashop-handoff
pip install playwright pillow && playwright install chromium
```

## Usar
En Claude Code: «crea el handoff de PrestaShop para `ruta/index.html`». El flujo completo está en `SKILL.md`.
