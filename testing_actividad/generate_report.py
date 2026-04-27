"""
=============================================================
  GENERADOR DE REPORTE HTML COMPLETO
  Incluye:
    - Capturas de pantalla por sitio
    - Detección de errores (consola JS, HTTP, imágenes, seguridad)
    - Dashboard de métricas
    - Tabs por sección

  FLUJO RECOMENDADO:
      1. pytest tests/ -v              <- toma capturas
      2. python error_detector.py      <- detecta errores
      3. python generate_report.py     <- genera el HTML

  O TODO EN UN SOLO COMANDO:
      python generate_report.py --full
=============================================================
"""

import os
import sys
import json
import base64
import glob
import subprocess
from datetime import datetime

SCREENSHOTS_DIR = "screenshots"
ERROR_JSON      = "error_report.json"
OUTPUT_FILE     = "reporte_testing.html"

STEP_MAP = {
    "01":  ("Demoblaze",            "Página de inicio"),
    "02":  ("Demoblaze",            "Categoría Phones"),
    "03":  ("Demoblaze",            "Detalle de producto"),
    "04":  ("Demoblaze",            "Producto agregado al carrito"),
    "05":  ("Demoblaze",            "Vista del carrito"),
    "06":  ("Automation Exercise",  "Página de inicio"),
    "07":  ("Automation Exercise",  "Catálogo de productos"),
    "08":  ("Automation Exercise",  "Búsqueda: 'shirt'"),
    "09":  ("Automation Exercise",  "Formulario de Login"),
    "10":  ("Automation Exercise",  "Página de Contacto"),
    "11":  ("Rahul Shetty",         "Tienda — inicio"),
    "12":  ("Rahul Shetty",         "Búsqueda: 'Tomato'"),
    "13":  ("Rahul Shetty",         "Producto agregado"),
    "14":  ("Rahul Shetty",         "Detalle del carrito"),
    "15":  ("Rahul Shetty",         "Todos los productos"),
    "16":  ("ParaBank",             "Portal bancario — inicio"),
    "17":  ("ParaBank",             "Formulario de login"),
    "18":  ("ParaBank",             "Dashboard autenticado"),
    "19":  ("ParaBank",             "Cuentas bancarias"),
    "20":  ("ParaBank",             "Transferencia de fondos"),
    "21":  ("Petstore Swagger",     "Swagger UI cargado"),
    "21b": ("Petstore Swagger",     "Sin banner de cookies"),
    "22":  ("Petstore Swagger",     "Sección 'pet' expandida"),
    "23":  ("Petstore Swagger",     "Endpoint GET /pet/findByStatus"),
    "24":  ("Petstore Swagger",     "Try it out activado"),
    "25":  ("Petstore Swagger",     "Respuesta de la API"),
    "26":  ("Petstore Swagger",     "Sección 'store'"),
    "27":  ("Juice Shop",           "Página de inicio"),
    "28":  ("Juice Shop",           "Dialogs cerrados"),
    "29":  ("Juice Shop",           "Búsqueda de producto"),
    "30":  ("Juice Shop",           "Formulario de Login"),
}

SITE_URLS = {
    "Demoblaze":            "https://www.demoblaze.com/",
    "Automation Exercise":  "https://www.automationexercise.com/",
    "Rahul Shetty":         "https://rahulshettyacademy.com/seleniumPractise/#/",
    "ParaBank":             "https://parabank.parasoft.com/",
    "Petstore Swagger":     "https://petstore.swagger.io/",
    "Juice Shop":           "https://juice-shop.herokuapp.com",
}


def load_screenshots():
    sites = {}
    files = sorted(glob.glob(os.path.join(SCREENSHOTS_DIR, "*.png")))
    for filepath in files:
        filename = os.path.basename(filepath)
        prefix = filename.split("_")[0]
        if prefix not in STEP_MAP:
            continue
        site_name, step_desc = STEP_MAP[prefix]
        with open(filepath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        if site_name not in sites:
            sites[site_name] = []
        sites[site_name].append({"num": prefix, "desc": step_desc, "b64": b64, "file": filename})
    return sites


def load_errors():
    if not os.path.isfile(ERROR_JSON):
        return {}
    with open(ERROR_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {r["name"]: r for r in data}


def severity_of(err_data):
    if not err_data:
        return "unknown"
    if err_data.get("console_errors") or err_data.get("failed_requests"):
        return "critical"
    if err_data.get("broken_images") or err_data.get("security_issues") or err_data.get("slow_requests"):
        return "warning"
    return "ok"


def build_error_panel(err):
    if not err:
        return '<div class="no-errors">⚪ Ejecuta <code>python error_detector.py</code> para analizar este sitio.</div>'

    load = err.get("load_time_ms", 0)
    load_cls = "fast" if load < 3000 else ("medium" if load < 5000 else "slow")

    summary_pills = "".join(
        f'<span class="pill">{s}</span>' for s in err.get("summary", [])
    )

    metrics = f"""
    <div class="metrics-row">
      <div class="metric metric-{load_cls}">
        <div class="mval">{load}ms</div><div class="mlbl">Tiempo carga</div>
      </div>
      <div class="metric {'metric-red' if err.get('console_errors') else ''}">
        <div class="mval">{len(err.get('console_errors',[]))}</div><div class="mlbl">Errores JS</div>
      </div>
      <div class="metric {'metric-red' if err.get('failed_requests') else ''}">
        <div class="mval">{len(err.get('failed_requests',[]))}</div><div class="mlbl">HTTP fallidos</div>
      </div>
      <div class="metric {'metric-yellow' if err.get('broken_images') else ''}">
        <div class="mval">{len(err.get('broken_images',[]))}</div><div class="mlbl">Imgs rotas</div>
      </div>
      <div class="metric {'metric-yellow' if err.get('security_issues') else ''}">
        <div class="mval">{len(err.get('security_issues',[]))}</div><div class="mlbl">Seguridad</div>
      </div>
      <div class="metric">
        <div class="mval">{len(err.get('console_warnings',[]))}</div><div class="mlbl">Advertencias</div>
      </div>
    </div>"""

    def tbl(icon, title, rows, cols, color):
        if not rows:
            return f'<div class="eg-empty">{icon} <b>{title}</b>: <span class="ok">Sin problemas ✅</span></div>'
        ths = "".join(f"<th>{c}</th>" for c in cols)
        trs = ""
        for r in rows:
            if isinstance(r, dict):
                trs += "<tr>" + "".join(f"<td>{str(v)[:150]}</td>" for v in r.values()) + "</tr>"
            else:
                trs += f"<tr><td colspan='{len(cols)}'>{str(r)[:250]}</td></tr>"
        return f"""<div class="eg eg-{color}">
          <div class="eg-title">{icon} {title}<span class="eg-cnt">{len(rows)}</span></div>
          <div class="tbl-wrap"><table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>
        </div>"""

    def lst(icon, title, items, color):
        if not items:
            return f'<div class="eg-empty">{icon} <b>{title}</b>: <span class="ok">Sin problemas ✅</span></div>'
        lis = "".join(f"<li>{str(i)[:250]}</li>" for i in items)
        return f"""<div class="eg eg-{color}">
          <div class="eg-title">{icon} {title}<span class="eg-cnt">{len(items)}</span></div>
          <ul class="eg-list">{lis}</ul>
        </div>"""

    details = (
        tbl("🔴", "Errores de Consola JavaScript", err.get("console_errors",[]),   ["Mensaje", "Archivo", "Línea"], "red") +
        tbl("🔴", "Peticiones HTTP Fallidas",      err.get("failed_requests",[]),  ["URL", "Código", "Tipo"],       "red") +
        tbl("🟠", "Peticiones Lentas (>3s)",       err.get("slow_requests",[]),    ["URL", "Tiempo (ms)"],          "orange") +
        lst("🟡", "Imágenes Rotas",                err.get("broken_images",[]),    "yellow") +
        lst("🔒", "Problemas de Seguridad",        err.get("security_issues",[]),  "orange") +
        lst("♿", "Imágenes sin atributo ALT",     err.get("missing_alt",[]),      "blue") +
        lst("📋", "Problemas en Formularios",      err.get("form_issues",[]),      "blue") +
        lst("⚡", "Rendimiento",                   err.get("perf_issues",[]),      "blue") +
        lst("🟡", "Advertencias de Consola",       err.get("console_warnings",[]), "yellow")
    )

    return f"""<div class="err-panel">
      <div class="pills-row">{summary_pills}</div>
      {metrics}
      <div class="err-details">{details}</div>
    </div>"""


def build_html(screenshots, errors):
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    total_sites = len(SITE_URLS)
    total_shots = sum(len(v) for v in screenshots.values())
    total_errs  = sum(
        len(e.get("console_errors",[])) + len(e.get("failed_requests",[]))
        for e in errors.values()
    )
    sites_with_errs = sum(
        1 for e in errors.values()
        if e.get("console_errors") or e.get("failed_requests")
    )
    clean_sites = total_sites - sites_with_errs
    rate = int(clean_sites / total_sites * 100) if total_sites else 0

    nav_html = ""
    sections_html = ""

    for idx, (site_name, url) in enumerate(SITE_URLS.items()):
        steps = screenshots.get(site_name, [])
        err   = errors.get(site_name, {})
        sev   = severity_of(err)

        icons = {"ok":"✅","warning":"⚠️","critical":"🔴","unknown":"⚪"}
        nav_html += f'<a href="#site-{idx}" class="nl nl-{sev}">{icons.get(sev,"")} {site_name}</a>\n'

        steps_html = ""
        for j, s in enumerate(steps):
            steps_html += f"""
            <div class="sc" style="animation-delay:{j*.05}s">
              <div class="sc-hdr"><span class="sc-num">Paso {j+1}</span><span class="sc-file">{s['file']}</span></div>
              <div class="sc-desc">{s['desc']}</div>
              <div class="sc-img" onclick="openModal('data:image/png;base64,{s['b64']}','{s['desc']}')">
                <img src="data:image/png;base64,{s['b64']}" alt="{s['desc']}" loading="lazy"/>
                <div class="sc-ov">🔍 Ampliar</div>
              </div>
            </div>"""
        if not steps_html:
            steps_html = '<div class="nd">⚠ Sin capturas para este sitio</div>'

        badge_map  = {"ok":"badge-ok","warning":"badge-warn","critical":"badge-crit","unknown":"badge-unk"}
        badge_text = {"ok":"✅ Sin errores críticos","warning":"⚠️ Advertencias","critical":"🔴 Errores críticos","unknown":"⚪ Sin analizar"}

        sections_html += f"""
        <section class="ss sev-{sev}" id="site-{idx}">
          <div class="ss-hdr">
            <div><h2>{site_name}</h2><a href="{url}" target="_blank" class="su">{url}</a></div>
            <div class="bdgs">
              <span class="bdg {badge_map.get(sev,'badge-unk')}">{badge_text.get(sev,'')}</span>
              <span class="bdg bdg-cnt">📸 {len(steps)} capturas</span>
            </div>
          </div>
          <div class="tabs">
            <button class="tb active" onclick="tab(this,'pss-{idx}')">📸 Capturas de pantalla</button>
            <button class="tb" onclick="tab(this,'perr-{idx}')">🔍 Detección de errores</button>
          </div>
          <div class="tp active" id="pss-{idx}"><div class="sg">{steps_html}</div></div>
          <div class="tp" id="perr-{idx}">{build_error_panel(err)}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Reporte de Testing QA</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#07111e;--sf:#0d1b2a;--sf2:#132233;--bd:#1a2e42;
  --ac:#00d4ff;--pu:#7c3aed;--gn:#10b981;--rd:#ef4444;
  --or:#f97316;--yw:#f59e0b;--bl:#3b82f6;
  --tx:#dde6f0;--mu:#4a6070;
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif;
}}
*{{margin:0;padding:0;box-sizing:border-box;}} html{{scroll-behavior:smooth;}}
body{{background:var(--bg);color:var(--tx);font-family:var(--sans);
  background-image:radial-gradient(ellipse 60% 40% at 5% 0%,rgba(0,212,255,.05) 0%,transparent 70%),
                   radial-gradient(ellipse 50% 40% at 95% 100%,rgba(124,58,237,.05) 0%,transparent 70%);}}

/* HEADER */
.hdr{{background:linear-gradient(180deg,#0a1520,var(--sf));border-bottom:1px solid var(--bd);
  padding:2rem 3rem 1.5rem;position:sticky;top:0;z-index:200;backdrop-filter:blur(16px);}}
.hr1{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.5rem;flex-wrap:wrap;gap:1rem;}}
.brand{{display:flex;align-items:center;gap:1rem;}}
.bicon{{width:52px;height:52px;background:linear-gradient(135deg,var(--ac),var(--pu));border-radius:14px;
  display:flex;align-items:center;justify-content:center;font-size:1.5rem;flex-shrink:0;
  box-shadow:0 0 28px rgba(0,212,255,.22);}}
.btext h1{{font-size:1.6rem;font-weight:800;letter-spacing:-.03em;
  background:linear-gradient(90deg,var(--ac),#a78bfa 60%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.1;}}
.btext .sub{{font-family:var(--mono);font-size:.67rem;color:var(--mu);margin-top:.3rem;letter-spacing:.08em;}}
.hmeta{{text-align:right;font-family:var(--mono);font-size:.7rem;color:var(--mu);line-height:2;}}
.hmeta span{{color:var(--ac);}}
.sr{{display:flex;gap:.9rem;flex-wrap:wrap;margin-bottom:1rem;}}
.st{{background:var(--sf2);border:1px solid var(--bd);border-radius:10px;padding:.65rem 1.1rem;
  display:flex;align-items:center;gap:.9rem;min-width:105px;}}
.sv{{font-family:var(--mono);font-size:1.55rem;font-weight:700;line-height:1;}}
.sl{{font-size:.62rem;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-top:.2rem;}}
.s1 .sv{{color:var(--ac);}} .s2 .sv{{color:var(--gn);}} .s3 .sv{{color:var(--rd);}}
.s4 .sv{{color:var(--yw);}} .s5 .sv{{color:#a78bfa;}}
.pt{{height:5px;background:var(--sf2);border-radius:4px;overflow:hidden;border:1px solid var(--bd);}}
.pf{{height:100%;background:linear-gradient(90deg,var(--gn),var(--ac));width:{rate}%;border-radius:4px;}}

/* NAV */
.nav{{background:var(--sf);border-bottom:1px solid var(--bd);padding:.75rem 3rem;
  display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;}}
.nlbl{{font-family:var(--mono);font-size:.62rem;color:var(--mu);text-transform:uppercase;letter-spacing:.1em;margin-right:.5rem;}}
.nl{{font-family:var(--mono);font-size:.68rem;padding:.3rem .8rem;border-radius:20px;
  text-decoration:none;border:1px solid transparent;transition:all .18s;white-space:nowrap;}}
.nl:hover{{transform:translateY(-1px);filter:brightness(1.2);}}
.nl-ok{{color:var(--gn);border-color:rgba(16,185,129,.35);background:rgba(16,185,129,.06);}}
.nl-warning{{color:var(--yw);border-color:rgba(245,158,11,.35);background:rgba(245,158,11,.06);}}
.nl-critical{{color:var(--rd);border-color:rgba(239,68,68,.35);background:rgba(239,68,68,.06);}}
.nl-unknown{{color:var(--mu);border-color:var(--bd);}}

/* MAIN */
.main{{padding:2.5rem 3rem 5rem;max-width:1440px;margin:0 auto;}}

/* SECTION */
.ss{{background:var(--sf);border:1px solid var(--bd);border-radius:16px;margin-bottom:2.2rem;
  overflow:hidden;animation:ru .4s ease both;}}
.sev-ok{{border-top:3px solid var(--gn);}} .sev-warning{{border-top:3px solid var(--yw);}}
.sev-critical{{border-top:3px solid var(--rd);}} .sev-unknown{{border-top:3px solid var(--mu);}}
@keyframes ru{{from{{opacity:0;transform:translateY(20px)}}to{{opacity:1;transform:translateY(0)}}}}
.ss-hdr{{padding:1.3rem 1.8rem;background:var(--sf2);border-bottom:1px solid var(--bd);
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;}}
.ss-hdr h2{{font-size:1.1rem;font-weight:800;}}
.su{{font-family:var(--mono);font-size:.67rem;color:var(--ac);text-decoration:none;opacity:.75;}}
.su:hover{{opacity:1;text-decoration:underline;}}
.bdgs{{display:flex;gap:.5rem;flex-wrap:wrap;}}
.bdg{{font-family:var(--mono);font-size:.65rem;font-weight:700;padding:.22rem .65rem;border-radius:20px;border:1px solid transparent;letter-spacing:.04em;}}
.badge-ok{{background:rgba(16,185,129,.1);color:var(--gn);border-color:rgba(16,185,129,.3);}}
.badge-warn{{background:rgba(245,158,11,.1);color:var(--yw);border-color:rgba(245,158,11,.3);}}
.badge-crit{{background:rgba(239,68,68,.1);color:var(--rd);border-color:rgba(239,68,68,.3);}}
.badge-unk{{background:rgba(255,255,255,.04);color:var(--mu);border-color:var(--bd);}}
.bdg-cnt{{background:rgba(0,212,255,.07);color:var(--ac);border-color:rgba(0,212,255,.2);}}

/* TABS */
.tabs{{display:flex;border-bottom:1px solid var(--bd);background:var(--sf2);}}
.tb{{background:none;border:none;color:var(--mu);font-family:var(--mono);font-size:.73rem;
  padding:.85rem 1.5rem;cursor:pointer;border-bottom:2px solid transparent;transition:all .2s;}}
.tb:hover{{color:var(--tx);}} .tb.active{{color:var(--ac);border-bottom-color:var(--ac);}}
.tp{{display:none;}} .tp.active{{display:block;}}

/* SCREENSHOTS */
.sg{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:1.1rem;padding:1.5rem 1.8rem;}}
.sc{{background:var(--bg);border:1px solid var(--bd);border-radius:12px;overflow:hidden;
  animation:ru .35s ease both;transition:border-color .2s,transform .2s,box-shadow .2s;}}
.sc:hover{{border-color:rgba(0,212,255,.3);transform:translateY(-3px);box-shadow:0 8px 30px rgba(0,0,0,.4);}}
.sc-hdr{{display:flex;justify-content:space-between;align-items:center;padding:.5rem .9rem 0;}}
.sc-num{{font-family:var(--mono);font-size:.6rem;color:var(--ac);letter-spacing:.1em;text-transform:uppercase;}}
.sc-file{{font-family:var(--mono);font-size:.57rem;color:var(--mu);}}
.sc-desc{{font-size:.78rem;font-weight:600;padding:.25rem .9rem .7rem;line-height:1.4;}}
.sc-img{{border-top:1px solid var(--bd);position:relative;overflow:hidden;cursor:zoom-in;}}
.sc-img img{{width:100%;display:block;transition:transform .3s;}}
.sc-img:hover img{{transform:scale(1.03);}}
.sc-ov{{position:absolute;inset:0;background:linear-gradient(transparent 60%,rgba(0,0,0,.75));
  display:flex;align-items:flex-end;justify-content:center;padding-bottom:.7rem;
  color:var(--ac);font-family:var(--mono);font-size:.65rem;opacity:0;transition:opacity .2s;}}
.sc-img:hover .sc-ov{{opacity:1;}}
.nd{{grid-column:1/-1;padding:2rem;text-align:center;color:var(--mu);
  font-family:var(--mono);font-size:.8rem;border:1px dashed var(--bd);border-radius:10px;}}

/* ERROR PANEL */
.err-panel{{padding:1.5rem 1.8rem;}}
.no-errors{{padding:1.5rem;color:var(--mu);font-family:var(--mono);font-size:.8rem;}}
.no-errors code{{color:var(--ac);}}
.pills-row{{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1.2rem;}}
.pill{{font-family:var(--mono);font-size:.72rem;background:var(--sf2);
  border:1px solid var(--bd);border-radius:20px;padding:.3rem .85rem;}}
.metrics-row{{display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1.5rem;}}
.metric{{background:var(--sf2);border:1px solid var(--bd);border-radius:10px;
  padding:.65rem 1rem;min-width:92px;text-align:center;}}
.mval{{font-family:var(--mono);font-size:1.5rem;font-weight:700;line-height:1;}}
.mlbl{{font-size:.6rem;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-top:.25rem;}}
.metric-fast .mval{{color:var(--gn);}} .metric-medium .mval{{color:var(--yw);}} .metric-slow .mval{{color:var(--rd);}}
.metric-red .mval{{color:var(--rd);}} .metric-yellow .mval{{color:var(--yw);}}
.err-details{{display:flex;flex-direction:column;gap:.9rem;}}
.eg{{background:var(--bg);border-radius:10px;overflow:hidden;border:1px solid var(--bd);}}
.eg-empty{{padding:.6rem 1rem;font-family:var(--mono);font-size:.72rem;color:var(--mu);
  border:1px dashed var(--bd);border-radius:8px;}}
.ok{{color:var(--gn);}}
.eg-title{{padding:.7rem 1rem;font-family:var(--mono);font-size:.75rem;font-weight:700;
  display:flex;align-items:center;gap:.5rem;background:var(--sf2);border-bottom:1px solid var(--bd);}}
.eg-cnt{{background:var(--rd);color:#fff;font-size:.6rem;padding:.1rem .4rem;border-radius:10px;margin-left:auto;}}
.eg-red .eg-title{{border-left:3px solid var(--rd);}}
.eg-orange .eg-title{{border-left:3px solid var(--or);}}
.eg-yellow .eg-title{{border-left:3px solid var(--yw);}}
.eg-blue .eg-title{{border-left:3px solid var(--bl);}}
.tbl-wrap{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:.7rem;}}
th{{background:var(--sf2);color:var(--mu);padding:.55rem .8rem;text-align:left;
  font-size:.63rem;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--bd);}}
td{{padding:.5rem .8rem;border-bottom:1px solid var(--bd);color:var(--tx);word-break:break-all;max-width:400px;}}
tr:last-child td{{border-bottom:none;}} tr:hover td{{background:rgba(255,255,255,.02);}}
.eg-list{{list-style:none;padding:.5rem 0;}}
.eg-list li{{padding:.45rem 1rem;font-family:var(--mono);font-size:.72rem;
  border-bottom:1px solid var(--bd);color:var(--tx);}}
.eg-list li:last-child{{border-bottom:none;}}

/* MODAL */
.modal{{display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.93);
  align-items:center;justify-content:center;padding:2rem;}}
.modal.open{{display:flex;}}
.mbox{{max-width:96vw;max-height:92vh;display:flex;flex-direction:column;align-items:center;gap:.8rem;}}
.mcap{{color:var(--ac);font-family:var(--mono);font-size:.78rem;text-align:center;}}
.mbox img{{max-width:94vw;max-height:84vh;border-radius:10px;border:1px solid var(--bd);object-fit:contain;}}
.mclose{{position:fixed;top:1rem;right:1.2rem;background:var(--sf2);border:1px solid var(--bd);
  color:var(--tx);font-family:var(--mono);font-size:.8rem;padding:.4rem .9rem;
  border-radius:8px;cursor:pointer;transition:background .2s;}}
.mclose:hover{{background:var(--rd);border-color:var(--rd);}}

footer{{text-align:center;padding:2rem;font-family:var(--mono);font-size:.68rem;
  color:var(--mu);border-top:1px solid var(--bd);}}
@media(max-width:768px){{
  .hdr,.main{{padding:1.2rem;}} .nav{{padding:.6rem 1rem;}}
  .sg{{grid-template-columns:1fr;padding:1rem;}} .hr1{{flex-direction:column;}}
}}
</style>
</head>
<body>

<header class="hdr">
  <div class="hr1">
    <div class="brand">
      <div class="bicon">🧪</div>
      <div class="btext">
        <h1>REPORTE DE TESTING QA</h1>
        <div class="sub">Actividad &nbsp;·&nbsp; Playwright &nbsp;·&nbsp; Chromium &nbsp;·&nbsp; Python</div>
      </div>
    </div>
    <div class="hmeta">
      <div>📅 Generado: <span>{now}</span></div>
      <div>🌐 {total_sites} sitios &nbsp;|&nbsp; 📸 <span>{total_shots}</span> capturas</div>
      <div>🔴 <span>{total_errs}</span> errores detectados en {sites_with_errs} sitios</div>
    </div>
  </div>
  <div class="sr">
    <div class="st s1"><div><div class="sv">{total_sites}</div><div class="sl">Sitios</div></div></div>
    <div class="st s2"><div><div class="sv">{total_sites - sites_with_errs}</div><div class="sl">Sin errores</div></div></div>
    <div class="st s3"><div><div class="sv">{sites_with_errs}</div><div class="sl">Con errores</div></div></div>
    <div class="st s4"><div><div class="sv">{total_errs}</div><div class="sl">Total errores</div></div></div>
    <div class="st s5"><div><div class="sv">{total_shots}</div><div class="sl">Capturas</div></div></div>
  </div>
  <div class="pt"><div class="pf"></div></div>
</header>

<nav class="nav">
  <span class="nlbl">Ir a →</span>
  {nav_html}
</nav>

<main class="main">
  {sections_html}
</main>

<footer>
  Reporte de Testing QA &nbsp;·&nbsp; Playwright + Python &nbsp;·&nbsp; {now}
</footer>

<div class="modal" id="modal" onclick="closeModal(event)">
  <button class="mclose" onclick="closeModal()">✕ Cerrar</button>
  <div class="mbox">
    <div class="mcap" id="mcap"></div>
    <img id="mimg" src="" alt=""/>
  </div>
</div>

<script>
function openModal(src,title){{
  document.getElementById('mimg').src=src;
  document.getElementById('mcap').textContent=title;
  document.getElementById('modal').classList.add('open');
  document.body.style.overflow='hidden';
}}
function closeModal(e){{
  if(!e||e.target===document.getElementById('modal')||e.currentTarget?.classList?.contains('mclose')){{
    document.getElementById('modal').classList.remove('open');
    document.body.style.overflow='';
  }}
}}
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeModal({{target:document.getElementById('modal')}});}});
function tab(btn,pid){{
  const sec=btn.closest('.ss');
  sec.querySelectorAll('.tb').forEach(b=>b.classList.remove('active'));
  sec.querySelectorAll('.tp').forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(pid).classList.add('active');
}}
</script>
</body>
</html>"""


def main():
    if "--full" in sys.argv:
        print("\n🔄 Modo --full: ejecutando todo el pipeline...\n")
        print("  [1/3] Tests de Playwright...")
        subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], check=False)
        print("\n  [2/3] Detector de errores...")
        from error_detector import run_all
        run_all()

    print("\n" + "="*55)
    print("  📊  GENERANDO REPORTE HTML")
    print("="*55)

    screenshots = load_screenshots()
    errors      = load_errors()

    print(f"  📸 Capturas cargadas : {sum(len(v) for v in screenshots.values())}")
    print(f"  🔍 Sitios analizados : {len(errors)}")

    html = build_html(screenshots, errors)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\n  ✅ Reporte: {OUTPUT_FILE}  ({size_kb:.0f} KB)")
    print("     Ábrelo en tu navegador.")
    print("="*55 + "\n")


if __name__ == "__main__":
    main()