"""
=============================================================
  DETECTOR DE ERRORES — Módulo de análisis de calidad
  Detecta errores reales en cada sitio web:
    - Errores de consola JavaScript
    - Peticiones HTTP fallidas (4xx / 5xx)
    - Elementos rotos (imágenes, links)
    - Formularios sin validación
    - Tiempos de carga lentos
    - Errores de seguridad básicos
=============================================================
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# ─── Sitios a analizar ────────────────────────────────────
SITES = [
    {
        "name": "Demoblaze",
        "url":  "https://www.demoblaze.com/",
        "extra_urls": [
            "https://www.demoblaze.com/cart.html",
        ],
    },
    {
        "name": "Automation Exercise",
        "url":  "https://www.automationexercise.com/",
        "extra_urls": [
            "https://www.automationexercise.com/login",
            "https://www.automationexercise.com/products",
        ],
    },
    {
        "name": "Rahul Shetty Greens",
        "url":  "https://rahulshettyacademy.com/seleniumPractise/#/",
        "extra_urls": [],
    },
    {
        "name": "ParaBank",
        "url":  "https://parabank.parasoft.com/",
        "extra_urls": [],
    },
    {
        "name": "Petstore Swagger",
        "url":  "https://petstore.swagger.io/",
        "extra_urls": [],
    },
    {
        "name": "Juice Shop",
        "url":  "https://juice-shop.herokuapp.com",
        "extra_urls": [
            "https://juice-shop.herokuapp.com/#/login",
        ],
    },
]


def analyze_site(page, site):
    """
    Analiza un sitio y devuelve un dict con todos los errores encontrados.
    """
    result = {
        "name":          site["name"],
        "url":           site["url"],
        "timestamp":     datetime.now().strftime("%H:%M:%S"),
        "load_time_ms":  0,
        "http_status":   0,
        "console_errors":   [],
        "console_warnings": [],
        "failed_requests":  [],
        "slow_requests":    [],   # > 3 segundos
        "broken_images":    [],
        "broken_links":     [],
        "missing_alt":      [],
        "security_issues":  [],
        "form_issues":      [],
        "perf_issues":      [],
        "summary":          [],   # resumen legible
    }

    # ── 1. Capturar errores de consola ──────────────────────
    def on_console(msg):
        if msg.type == "error":
            result["console_errors"].append({
                "text": msg.text[:200],
                "url":  msg.location.get("url", "")[:100] if msg.location else "",
                "line": msg.location.get("lineNumber", "") if msg.location else "",
            })
        elif msg.type == "warning":
            result["console_warnings"].append(msg.text[:200])

    page.on("console", on_console)

    # ── 2. Capturar peticiones HTTP fallidas ────────────────
    request_times = {}

    def on_request(req):
        request_times[req.url] = time.time()

    def on_response(resp):
        status = resp.status
        url    = resp.url
        elapsed_ms = int((time.time() - request_times.get(url, time.time())) * 1000)

        if status >= 400:
            result["failed_requests"].append({
                "url":    url[:120],
                "status": status,
                "type":   _status_label(status),
            })

        if elapsed_ms > 3000 and not url.endswith((".png", ".jpg", ".gif", ".woff2")):
            result["slow_requests"].append({
                "url":        url[:120],
                "elapsed_ms": elapsed_ms,
            })

    page.on("request",  on_request)
    page.on("response", on_response)

    # ── 3. Navegar y medir tiempo de carga ──────────────────
    t0 = time.time()
    try:
        page.goto(site["url"], wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2500)
    except Exception as e:
        result["summary"].append(f"❌ No se pudo cargar la página: {e}")
        return result

    result["load_time_ms"] = int((time.time() - t0) * 1000)

    # ── 4. Imágenes rotas ───────────────────────────────────
    broken = page.evaluate("""
        () => {
            const imgs = Array.from(document.querySelectorAll('img'));
            return imgs
                .filter(img => !img.complete || img.naturalWidth === 0)
                .map(img => img.src || img.getAttribute('src') || '(sin src)')
                .filter(src => src && !src.startsWith('data:'))
                .slice(0, 10);
        }
    """)
    result["broken_images"] = broken

    # ── 5. Atributos alt faltantes en imágenes ──────────────
    missing_alt = page.evaluate("""
        () => {
            const imgs = Array.from(document.querySelectorAll('img'));
            return imgs
                .filter(img => !img.alt || img.alt.trim() === '')
                .map(img => img.src || '(sin src)')
                .slice(0, 8);
        }
    """)
    result["missing_alt"] = missing_alt

    # ── 6. Links rotos (href vacío o "#" sin propósito) ─────
    bad_links = page.evaluate("""
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            return links
                .filter(a => {
                    const h = a.getAttribute('href');
                    return h === '' || h === null;
                })
                .map(a => a.textContent.trim().slice(0, 60) || '(sin texto)')
                .filter(t => t)
                .slice(0, 8);
        }
    """)
    result["broken_links"] = bad_links

    # ── 7. Problemas de seguridad básicos ───────────────────
    sec = []

    # HTTP en vez de HTTPS
    if site["url"].startswith("http://"):
        sec.append("⚠ El sitio usa HTTP (sin cifrado)")

    # Campos password sin autocomplete=off
    pwd_issues = page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input[type=password]'));
            return inputs.filter(i => i.autocomplete !== 'off' && i.autocomplete !== 'new-password').length;
        }
    """)
    if pwd_issues > 0:
        sec.append(f"⚠ {pwd_issues} campo(s) de contraseña sin autocomplete adecuado")

    # Inputs sin label asociado
    unlabeled = page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input:not([type=hidden]):not([type=submit])'));
            return inputs.filter(i => {
                const id = i.id;
                if (id && document.querySelector(`label[for='${id}']`)) return false;
                if (i.getAttribute('aria-label')) return false;
                if (i.getAttribute('placeholder')) return false;
                return true;
            }).length;
        }
    """)
    if unlabeled > 0:
        sec.append(f"⚠ {unlabeled} input(s) sin label ni aria-label (accesibilidad)")

    result["security_issues"] = sec

    # ── 8. Problemas de formularios ─────────────────────────
    form_issues = page.evaluate("""
        () => {
            const issues = [];
            const forms = Array.from(document.querySelectorAll('form'));
            forms.forEach((form, i) => {
                // Formulario sin action
                if (!form.action || form.action === window.location.href) {
                    // solo reportar si tiene inputs
                    const inputs = form.querySelectorAll('input:not([type=hidden])');
                    if (inputs.length > 0) issues.push(`Formulario ${i+1}: sin atributo action definido`);
                }
                // Inputs required sin indicación visual
                const required = form.querySelectorAll('[required]');
                if (required.length > 0) {
                    issues.push(`Formulario ${i+1}: ${required.length} campo(s) required`);
                }
            });
            return issues.slice(0, 6);
        }
    """)
    result["form_issues"] = form_issues

    # ── 9. Problemas de rendimiento ─────────────────────────
    perf = []
    if result["load_time_ms"] > 5000:
        perf.append(f"⚠ Carga muy lenta: {result['load_time_ms']}ms (>5s)")
    elif result["load_time_ms"] > 3000:
        perf.append(f"⚡ Carga moderada: {result['load_time_ms']}ms (3-5s)")
    else:
        perf.append(f"✅ Carga rápida: {result['load_time_ms']}ms (<3s)")

    if len(result["slow_requests"]) > 0:
        perf.append(f"⚠ {len(result['slow_requests'])} petición(es) tomaron más de 3s")

    result["perf_issues"] = perf

    # ── 10. Construir resumen ejecutivo ─────────────────────
    total_issues = (
        len(result["console_errors"]) +
        len(result["failed_requests"]) +
        len(result["broken_images"]) +
        len(result["security_issues"])
    )

    if total_issues == 0:
        result["summary"].append("✅ Sin errores críticos detectados")
    else:
        if result["console_errors"]:
            result["summary"].append(f"🔴 {len(result['console_errors'])} error(es) de consola JS")
        if result["failed_requests"]:
            result["summary"].append(f"🔴 {len(result['failed_requests'])} petición(es) HTTP fallida(s)")
        if result["broken_images"]:
            result["summary"].append(f"🟡 {len(result['broken_images'])} imagen(es) rota(s)")
        if result["security_issues"]:
            result["summary"].append(f"🟠 {len(result['security_issues'])} problema(s) de seguridad")

    if result["console_warnings"]:
        result["summary"].append(f"🟡 {len(result['console_warnings'])} advertencia(s) de consola")
    if result["missing_alt"]:
        result["summary"].append(f"ℹ️ {len(result['missing_alt'])} imagen(es) sin atributo alt")

    return result


def _status_label(code):
    labels = {
        400: "Bad Request",
        401: "No autorizado",
        403: "Prohibido",
        404: "No encontrado",
        405: "Método no permitido",
        408: "Timeout del servidor",
        429: "Demasiadas peticiones",
        500: "Error interno del servidor",
        502: "Bad Gateway",
        503: "Servicio no disponible",
        504: "Gateway Timeout",
    }
    return labels.get(code, f"Error HTTP {code}")


def run_all():
    all_results = []
    print("\n" + "="*60)
    print("  🔍  DETECTOR DE ERRORES — INICIO")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        for site in SITES:
            print(f"\n  Analizando: {site['name']}  →  {site['url']}")
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True
            )
            page = context.new_page()
            result = analyze_site(page, site)
            all_results.append(result)
            context.close()

            # Mini resumen en consola
            for s in result["summary"]:
                print(f"    {s}")
            print(f"    ⏱ Tiempo de carga: {result['load_time_ms']}ms")

        browser.close()

    # Guardar JSON para el reporte
    with open("error_report.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("\n" + "="*60)
    print("  ✅  Análisis completo → error_report.json")
    print("="*60 + "\n")
    return all_results


if __name__ == "__main__":
    run_all()