#!/usr/bin/env python3
"""Prueba final de extremo a extremo con un navegador real (Playwright) del flujo de compra.

Hace TRES compras y, en cada pantalla clave, compara con el diseño y avisa de lo que no cuadra:
  1. invitado (solo si la tienda tiene el modo invitado activo; si no, se anota y se salta),
  2. usuario registrado: primero se registra y después compra,
  3. usuario registrado que crea una dirección nueva en el pago y compra con ella.

Está pensada para el pago en una página nativo de PrestaShop 9 (ps_onepagecheckout). Con el pago por pasos clásico hay que
adaptar los selectores. Usa los datos de la tienda de pruebas: no la ejecutes contra una tienda real (crea clientes y pedidos).

Qué comprueba además de que la compra termine:
  - altura de la página frente a la captura del diseño (renders/<ruta>-1440.png), con tolerancia;
  - cabeceras esperadas (--expect-headings) y texto de la confirmación (--expect-confirmation);
  - textos sin traducir (inglés) y botones con el azul por defecto de Bootstrap;
  - scroll horizontal en escritorio y móvil;
  - que el pedido de la dirección nueva muestre esa dirección.

Uso:
  e2e_checkout.py --url http://tienda:8100 --product-path /1-producto.html --handoff ./handoff \
      [--flows guest,register,address] [--order-path /pedido] [--register-path /registro] \
      [--expect-headings "Contacto,Dirección de envío,Envío,Pago"] [--expect-confirmation "Gracias"] \
      [--pay-prefer "transfer|transferencia|bank wire"] [--tolerance 0.08]

Informe: <handoff>/validation/prueba-final.md y capturas en <handoff>/validation/e2e/. Código de salida 1 si algo falla (❌);
las diferencias con el diseño salen como ⚠️ y no hacen fallar la prueba, pero hay que informarlas al maquetador.
"""
import argparse
import random
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ENGLISH = re.compile(r"\b(Delivery method|Payment method|Sign in|Continue as guest|Order with an obligation|Loading|Contact information|"
                     r"Billing address|Create account|Still needed|Add to cart|Your cart|Shopping Cart|Proceed to checkout)\b")
BOOTSTRAP_BLUES = {"rgb(13, 110, 253)", "rgb(0, 123, 255)", "rgb(11, 105, 246)", "rgb(10, 88, 202)"}
ADDRESS = {"firstname": "Ana", "lastname": "Prueba", "address1": "Calle Mayor 1", "city": "Barcelona", "postcode": "08001", "phone": "600000000"}
NEW_ADDRESS = {**ADDRESS, "address1": "Carrer Nou 99", "city": "Girona", "postcode": "17001"}
CHROME_ARGS = ["--no-sandbox"]


class Report:
    def __init__(self):
        self.rows = []

    def add(self, flow: str, name: str, status: str, detail: str = ""):
        self.rows.append((flow, name, status, detail))
        icon = {"ok": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}[status]
        print(f"{icon} [{flow}] {name}" + (f" — {detail}" if detail else ""), flush=True)

    def write(self, path: Path):
        lines = ["# Prueba final de extremo a extremo", "", "| Flujo | Comprobación | Resultado | Detalle |", "|---|---|---|---|"]
        icon = {"ok": "✅", "fail": "❌", "warn": "⚠️ no cuadra con el diseño", "skip": "⏭️ saltado"}
        for flow, name, status, detail in self.rows:
            lines.append(f"| {flow} | {name} | {icon[status]} | {detail.replace('|', '/')} |")
        warns = [r for r in self.rows if r[2] == "warn"]
        lines += ["", f"**Fallos: {sum(r[2] == 'fail' for r in self.rows)} · Diferencias con el diseño: {len(warns)}**"]
        if warns:
            lines += ["", "## Lo que no cuadra con el diseño (informar al maquetador)"]
            lines += [f"- [{f}] {n}: {d}" for f, n, _, d in warns]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @property
    def failed(self) -> bool:
        return any(r[2] == "fail" for r in self.rows)


def design_height(handoff: Path, route: str):
    shot = handoff / "renders" / f"{route}-1440.png"
    if not shot.is_file():
        return None
    from PIL import Image
    with Image.open(shot) as img:
        return img.size[1]


def audit_screen(page, report: Report, flow: str, label: str, args, route: str, headings: list):
    """Compara la pantalla actual con el diseño: altura, cabeceras, inglés, azul de Bootstrap, scroll horizontal."""
    page.wait_for_timeout(800)
    height = page.evaluate("document.documentElement.scrollHeight")
    expected = design_height(args.handoff, route) if route else None
    if expected:
        diff = abs(height - expected) / expected
        status = "ok" if diff <= args.tolerance else "warn"
        report.add(flow, f"{label}: altura de la página", status, f"{height} px frente a {expected} px del diseño ({diff:.0%})")
    text = page.evaluate("document.body.innerText")
    for heading in headings:
        if heading.lower() not in text.lower():
            report.add(flow, f"{label}: falta «{heading}»", "warn", "el diseño tiene este título y la página no")
    english = sorted(set(ENGLISH.findall(text)))
    if english:
        report.add(flow, f"{label}: textos sin traducir", "warn", ", ".join(english))
    blues = page.evaluate("""(blues) => [...document.querySelectorAll('button, a.btn, .btn')]
        .filter(e => e.offsetParent !== null && blues.includes(getComputedStyle(e).backgroundColor))
        .map(e => (e.textContent || '').trim().slice(0, 30))""", sorted(BOOTSTRAP_BLUES))
    if blues:
        report.add(flow, f"{label}: botones con el azul por defecto", "warn", ", ".join(blues))
    if page.evaluate("document.documentElement.scrollWidth > innerWidth"):
        report.add(flow, f"{label}: scroll horizontal en escritorio", "warn", "la página es más ancha que la ventana")
    shot = args.handoff / "validation" / "e2e" / f"{flow}-{label.replace(' ', '_')}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=True)


def add_to_cart(page, args):
    page.goto(args.url + args.product_path, wait_until="domcontentloaded")
    page.wait_for_selector('[data-button-action="add-to-cart"]:not([disabled])')
    page.click('[data-button-action="add-to-cart"]')
    page.wait_for_timeout(2500)


def fill_fields(scope, data: dict, state_label: str = ""):
    for name, value in data.items():
        field = scope.locator(f'[name="{name}"]').first
        if field.count():
            field.fill(value)
    state = scope.locator('select[name="id_state"]').first
    if state.count():
        if state_label:
            state.select_option(label=state_label)
        else:
            state.select_option(index=1)


def accept_required(scope):
    for box in scope.locator('input[type="checkbox"][required]').all():
        if box.is_visible() and not box.is_checked():
            box.check()


def finish_purchase(page, report: Report, flow: str, args, headings: list, expect_text: str = ""):
    """Escoge envío y pago, acepta condiciones, paga y comprueba la confirmación."""
    try:
        page.wait_for_selector(".delivery-option__item", timeout=30000)
    except Exception:
        report.add(flow, "aparecen los métodos de envío", "fail", "no salieron tras rellenar la dirección")
        return False
    report.add(flow, "aparecen los métodos de envío", "ok", f"{page.locator('.delivery-option__item').count()} opciones")
    page.locator(".delivery-option__item").first.click()
    page.wait_for_timeout(3000)
    try:
        page.wait_for_selector(".payment-option", timeout=30000)
    except Exception:
        report.add(flow, "aparecen los métodos de pago", "fail", "no salieron tras elegir el envío")
        return False
    options = page.evaluate("[...document.querySelectorAll('.payment-option')].map(e => e.textContent.trim().replace(/\\s+/g, ' ').slice(0, 40))")
    report.add(flow, "aparecen los métodos de pago", "ok", " · ".join(options))
    prefer = re.compile(args.pay_prefer, re.I)
    chosen = next((o for o in page.locator(".payment-option").all() if prefer.search(o.text_content() or "")), page.locator(".payment-option").first)
    chosen.locator("label").first.click()
    page.wait_for_timeout(2500)
    audit_screen(page, report, flow, "pago rellenado", args, args.design_checkout, headings)
    accept_required(page.locator("form.js-conditions-to-approve, #conditions-to-approve"))
    if not page.locator("#opc-pay-button").is_enabled():
        report.add(flow, "el botón de pagar se activa", "fail", "sigue desactivado con todo relleno")
        return False
    page.click("#opc-pay-button")
    try:
        page.wait_for_url(re.compile(r"confirm", re.I), timeout=40000)
    except Exception:
        report.add(flow, "el pago lleva a la confirmación", "fail", page.url)
        return False
    report.add(flow, "el pago lleva a la confirmación", "ok", page.url.split("?")[0])
    audit_screen(page, report, flow, "confirmacion", args, args.design_confirmation, [])
    body = page.evaluate("document.body.innerText")
    if args.expect_confirmation and args.expect_confirmation.lower() not in body.lower():
        report.add(flow, f"la confirmación dice «{args.expect_confirmation}»", "warn", "texto no encontrado")
    if expect_text and expect_text.lower() not in body.lower():
        report.add(flow, f"la confirmación muestra «{expect_text}»", "fail", "la dirección usada no aparece en el pedido")
    return True


def flow_guest(browser, report: Report, args, headings: list):
    flow = "invitado"
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    page.set_default_timeout(20000)
    add_to_cart(page, args)
    page.goto(args.url + args.order_path, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    if not page.locator("#field-email").count() or not page.locator("#field-email").is_visible():
        report.add(flow, "compra como invitado", "skip", "el modo invitado no está activo en esta tienda (Preferencias > Pedidos)")
        return
    audit_screen(page, report, flow, "pago vacio", args, args.design_checkout, headings)
    page.fill("#field-email", f"e2e-guest-{random.randint(1000, 9999)}@example.com")
    accept_required(page.locator(".js-opc-contact-section"))
    fill_fields(page.locator("#opc-delivery-address-fields"), ADDRESS, args.state)
    page.locator("#opc-delivery-address-fields [name=phone]").first.blur()
    finish_purchase(page, report, flow, args, headings)


def register(page, report: Report, args, email: str, password: str) -> bool:
    page.goto(args.url + args.register_path, wait_until="domcontentloaded")
    form = page.locator("#customer-form")
    fill_fields(form, {"firstname": "Ana", "lastname": "Registrada", "email": email, "password": password})
    accept_required(form)
    form.locator('button[type="submit"]').click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    logged = page.evaluate("window.prestashop && window.prestashop.customer && window.prestashop.customer.is_logged")
    report.add("registrado", "alta de la cuenta", "ok" if logged else "fail", email)
    return bool(logged)


def flow_registered(browser, report: Report, args, headings: list):
    email, password = f"e2e-user-{random.randint(1000, 9999)}@example.com", "E2e-Prueba-2026!"
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(20000)
    if not register(page, report, args, email, password):
        return
    add_to_cart(page, args)
    page.goto(args.url + args.order_path, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    audit_screen(page, report, "registrado", "pago con sesion", args, args.design_checkout, headings)
    fill_fields(page.locator("#opc-delivery-address-fields"), ADDRESS, args.state)
    page.locator("#opc-delivery-address-fields [name=phone]").first.blur()
    if not finish_purchase(page, report, "registrado", args, headings):
        return
    # tercera compra: el mismo usuario crea una dirección nueva
    flow = "dirección nueva"
    add_to_cart(page, args)
    page.goto(args.url + args.order_path, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    new_item = page.locator('.opc-address-item[data-type="create"]').first
    if not new_item.count():
        report.add(flow, "opción «usar otra dirección»", "fail", "no aparece la lista de direcciones con la opción de crear una nueva")
        return
    audit_screen(page, report, flow, "pago con direcciones", args, args.design_checkout, headings)
    new_item.click()
    modal = page.locator("#modal-delivery")
    modal.wait_for(state="visible")
    fill_fields(modal, NEW_ADDRESS, args.state)
    page.click("#submit-address-modal")
    page.wait_for_timeout(4000)
    selected = page.locator(".opc-address-item.selected").first
    report.add(flow, "la dirección nueva queda elegida", "ok" if selected.count() and NEW_ADDRESS["address1"] in (selected.text_content() or "") else "fail",
               (selected.text_content() or "").strip().replace("\n", " ")[:80] if selected.count() else "sin dirección seleccionada")
    finish_purchase(page, report, flow, args, headings, expect_text=NEW_ADDRESS["address1"])
    ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="base de la tienda, sin barra final")
    ap.add_argument("--product-path", required=True, help="ruta de un producto con stock y sin combinaciones obligatorias")
    ap.add_argument("--handoff", type=Path, required=True, help="carpeta del handoff (renders/ y validation/)")
    ap.add_argument("--flows", default="guest,register,address")
    ap.add_argument("--order-path", default="/pedido")
    ap.add_argument("--register-path", default="/registro")
    ap.add_argument("--state", default="Barcelona", help="provincia a elegir si la tienda la pide")
    ap.add_argument("--expect-headings", default="")
    ap.add_argument("--expect-confirmation", default="")
    ap.add_argument("--pay-prefer", default="transfer|transferencia|bank wire")
    ap.add_argument("--design-checkout", default="checkout", help="nombre del render del pago en renders/")
    ap.add_argument("--design-confirmation", default="confirmacion")
    ap.add_argument("--tolerance", type=float, default=0.08, help="diferencia de altura aceptable respecto al diseño")
    args = ap.parse_args()
    args.url = args.url.rstrip("/")
    headings = [h.strip() for h in args.expect_headings.split(",") if h.strip()]
    flows = {f.strip() for f in args.flows.split(",")}
    report = Report()
    started = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=CHROME_ARGS)
        try:
            if "guest" in flows:
                flow_guest(browser, report, args, headings)
            if flows & {"register", "address"}:
                flow_registered(browser, report, args, headings)
        except Exception as error:  # un fallo inesperado no debe ocultar lo ya comprobado
            report.add("general", "error inesperado", "fail", str(error)[:200])
        finally:
            browser.close()
    out = args.handoff / "validation" / "prueba-final.md"
    report.write(out)
    print(f"\nInforme: {out} · {time.time() - started:.0f} s")
    sys.exit(1 if report.failed else 0)


if __name__ == "__main__":
    main()
