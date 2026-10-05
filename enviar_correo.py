#!/usr/bin/env python3
"""Correo ejecutivo de saldos de infraestructura (Angia Tech).

Lee Entradas/reporte_saldos.txt, genera un HTML con modo claro y oscuro y lo
envia por Amazon WorkMail (SMTP SSL 465).

Variables de entorno: WORKMAIL_USER, WORKMAIL_PASS
Vista previa sin enviar: python enviar_correo.py --dry-run [salida.html]
"""
import os
import re
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

REPORTE = os.path.join("Entradas", "reporte_saldos.txt")
SMTP_SERVER = "smtp.mail.us-east-1.awsapps.com"
SMTP_PORT = 465
DESTINATARIOS = ["tzules@angia.tech", "aarmas@angia.tech"]
SERVICIOS = ["OpenRouter", "CapSolver", "2Captcha", "DeCodo"]

UMBRAL_CRITICO = 20.0   # bajo este saldo: critico
UMBRAL_OPTIMO = 30.0    # desde este saldo: optimo
ESCALA = 100.0          # el medidor de cada servicio va de $0 a $100
ECUADOR = timezone(timedelta(hours=-5))

# --- Sistema de diseño ------------------------------------------------------
# Neutros con matiz violeta; el morado es la marca, verde/ambar/rojo son solo estado.
INK, MUTED, LINE = "#1B1130", "#6B6580", "#E6DFF0"
GROUND, CARD, SOFT = "#F4F1F8", "#FFFFFF", "#F8F5FC"
HEAD, BRAND, BRAND_TX = "#24104F", "#4C1D95", "#4C1D95"
FONT_DISPLAY = "'Sora','Segoe UI',-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"
FONT_BODY = "'Figtree','Segoe UI',-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif"

# nivel: etiqueta, color solido, tinte (pista), fondo chip, texto chip
NIVELES = {
    "ok": ("ÓPTIMO", "#16A34A", "#DDF3E4", "#E3F6EA", "#166534"),
    "warn": ("ATENCIÓN", "#F59E0B", "#FCEBC8", "#FDF0D5", "#92400E"),
    "crit": ("CRÍTICO", "#DC2626", "#F9D7D7", "#FCE4E4", "#991B1B"),
    "na": ("SIN DATO", "#9CA3AF", "#E5E7EB", "#F3F4F6", "#374151"),
}
ZONAS = [  # (desde, hasta, nivel)
    (0.0, UMBRAL_CRITICO, "crit"),
    (UMBRAL_CRITICO, UMBRAL_OPTIMO, "warn"),
    (UMBRAL_OPTIMO, ESCALA, "ok"),
]

DARK_CSS = """
@media (prefers-color-scheme: dark){
 .d-bg{background:#0F0A1A!important}
 .d-card{background:#1A1228!important;border-color:#2D2342!important}
 .d-soft{background:#221834!important}
 .d-ink{color:#F1ECFA!important}
 .d-mut{color:#A79FBE!important}
 .d-brand{color:#C4B5FD!important}
 .d-line{border-color:#2D2342!important}
 .d-hide{color:#0F0A1A!important}
 .d-th{background:#221834!important;color:#C4B5FD!important}
 .d-ok{background:#12301F!important;color:#86EFAC!important}
 .d-warn{background:#3A2A0C!important;color:#FCD34D!important}
 .d-crit{background:#3F1414!important;color:#FCA5A5!important}
 .d-na{background:#2A2438!important;color:#CBD5E1!important}
 .t-crit{background:#4A1E22!important}.t-warn{background:#44330F!important}.t-ok{background:#16382A!important}.t-na{background:#2A2438!important}
}
@media only screen and (max-width:640px){
 .wrap{width:100%!important;border-radius:0!important}
 .px{padding-left:20px!important;padding-right:20px!important}
 .k{display:inline-block!important;width:50%!important;box-sizing:border-box}
 .hm{display:none!important}
 .big{font-size:40px!important}
}
"""


def nivel(v):
    if v is None:
        return "na"
    if v >= UMBRAL_OPTIMO:
        return "ok"
    return "warn" if v >= UMBRAL_CRITICO else "crit"


def money(v):
    return "N/D" if v is None else f"${v:,.2f}"


def margen_txt(v):
    if v is None:
        return "N/D"
    d = v - UMBRAL_CRITICO
    return f"+${d:,.2f}" if d >= 0 else f"-${-d:,.2f}"


# --- Datos --------------------------------------------------------------------
def leer_reporte(ruta=REPORTE):
    """Devuelve (datetime_utc|None, {servicio: saldo|None}, alertas, hay_warning)."""
    with open(ruta, encoding="utf-8") as f:
        texto = f.read()
    fecha = None
    m = re.search(r"Fecha/Hora:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", texto)
    if m:
        fecha = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    saldos = {}
    for s in SERVICIOS:
        m = re.search(rf"{re.escape(s)}\s*:\s*\$?\s*([\d.,]+)", texto, re.I)
        saldos[s] = float(m.group(1).replace(",", "")) if m else None
    m = re.search(r"ALERTAS DETECTADAS:\s*(.+)", texto, re.S)
    alertas = m.group(1).strip() if m else ""
    return fecha, saldos, alertas, "[WARNING]" in texto.upper()


# --- Componentes --------------------------------------------------------------
def medidor(v):
    """Barra de $0 a $100 con zonas critica/atencion/optima; relleno solido hasta el saldo."""
    if v is None:
        return '<div style="height:10px;background:#E5E7EB;border-radius:99px;font-size:0;">&nbsp;</div>'
    v = max(0.0, min(ESCALA, v))
    celdas = ""

    def celda(ancho, nv, solido):
        if ancho <= 0:
            return ""
        _, col, tinte, _, _ = NIVELES[nv]
        cls = "" if solido else f' class="t-{nv}"'
        bg = col if solido else tinte
        return f'<td width="{ancho:.1f}%"{cls} height="10" style="width:{ancho:.1f}%;height:10px;background:{bg};font-size:0;line-height:0;">&nbsp;</td>'

    for lo, hi, nv in ZONAS:
        if v >= hi:
            celdas += celda(hi - lo, nv, True)
        elif v <= lo:
            celdas += celda(hi - lo, nv, False)
        else:
            celdas += celda(v - lo, nv, True) + celda(hi - v, nv, False)
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-radius:99px;border-collapse:separate;overflow:hidden;"><tr>{celdas}</tr></table>'
    )


def tarjeta(servicio, v):
    n = nivel(v)
    et, col, _, bg, fg = NIVELES[n]
    sub = "Sin dato" if v is None else f"{margen_txt(v)} margen"
    return f"""<td class="k" width="25%" valign="top" style="padding:5px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="d-card" style="background:{CARD};border:1px solid {LINE};border-radius:14px;border-collapse:separate;">
<tr><td style="padding:16px 16px 15px 16px;">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td width="8" height="8" style="width:8px;height:8px;background:{col};border-radius:99px;font-size:0;line-height:0;">&nbsp;</td>
<td class="d-mut" style="padding-left:7px;font-family:{FONT_BODY};font-size:11px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;color:{MUTED};">{escape(servicio)}</td></tr></table>
<div class="d-ink" style="font-family:{FONT_DISPLAY};font-size:26px;font-weight:700;letter-spacing:-.8px;color:{INK};margin-top:10px;">{money(v)}</div>
<div class="d-mut" style="font-family:{FONT_BODY};font-size:11.5px;color:{MUTED};margin-top:3px;">{escape(sub)}</div>
</td></tr></table></td>"""


def fila(servicio, v, par):
    n = nivel(v)
    et, col, _, bg, fg = NIVELES[n]
    fondo = CARD if par else SOFT
    clase_fondo = "d-card" if par else "d-soft"
    return f"""<tr class="{clase_fondo}" style="background:{fondo};">
<td class="d-line" style="padding:16px 18px;border-top:1px solid {LINE};font-family:{FONT_BODY};">
<div class="d-ink" style="font-size:14px;font-weight:700;color:{INK};">{escape(servicio)}</div>
<div style="margin-top:9px;">{medidor(v)}</div></td>
<td class="d-line d-ink" align="right" style="padding:16px 18px;border-top:1px solid {LINE};font-family:{FONT_DISPLAY};font-size:16px;font-weight:700;letter-spacing:-.3px;color:{INK};white-space:nowrap;">{money(v)}</td>
<td class="d-line d-mut hm" align="right" style="padding:16px 18px;border-top:1px solid {LINE};font-family:{FONT_BODY};font-size:13px;color:{MUTED};white-space:nowrap;">{margen_txt(v)}</td>
<td class="d-line" align="center" style="padding:16px 18px;border-top:1px solid {LINE};">
<span class="d-{n}" style="display:inline-block;background:{bg};color:{fg};font-family:{FONT_BODY};font-size:10px;font-weight:800;letter-spacing:1px;padding:5px 11px;border-radius:99px;white-space:nowrap;">{et}</span></td></tr>"""


def construir_html(fecha, saldos, alertas, warning, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    niv = {s: nivel(v) for s, v in saldos.items()}
    hay_crit = warning or "crit" in niv.values()
    hay_warn = "warn" in niv.values()
    if hay_crit:
        est_n, estado, detalle = "crit", "Acción requerida", "Hay servicios bajo el umbral crítico de $20.00. Se recomienda recargar de inmediato."
    elif hay_warn:
        est_n, estado, detalle = "warn", "Operativo, con atención", "Todos los servicios superan $20.00, pero algunos están cerca del umbral."
    else:
        est_n, estado, detalle = "ok", "Operativo normal", "Todos los servicios mantienen saldo óptimo."
    _, _, _, chip_bg, chip_fg = NIVELES[est_n]

    validos = {s: v for s, v in saldos.items() if v is not None}
    total = sum(validos.values())
    menor = min(validos, key=validos.get) if validos else None

    if fecha:
        corte = f"{fecha:%d/%m/%Y} &middot; {fecha:%H:%M} UTC ({fecha.astimezone(ECUADOR):%H:%M} Ecuador)"
        horas = (ahora - fecha).total_seconds() / 3600
    else:
        corte, horas = "Fecha no disponible", None

    aviso = ""
    if horas is not None and horas > 24:
        aviso = (
            '<tr><td class="px" style="padding:0 36px 18px 36px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'class="d-warn" style="background:#FDF0D5;border-radius:12px;border-collapse:separate;"><tr>'
            f'<td style="padding:13px 16px;font-family:{FONT_BODY};font-size:13px;line-height:1.5;color:#92400E;">'
            f"<strong>Reporte desactualizado.</strong> Tiene {horas / 24:.1f} días de antigüedad. Revise la ejecución del workflow."
            "</td></tr></table></td></tr>"
        )

    tarjetas = "".join(tarjeta(s, v) for s, v in saldos.items())
    orden = sorted(saldos.items(), key=lambda kv: (kv[1] is None, kv[1] or 0))
    filas = "".join(fila(s, v, i % 2 == 0) for i, (s, v) in enumerate(orden))
    alertas_html = escape(alertas).replace("\n", "<br>") if alertas else "Sin alertas registradas."
    pre = f"{estado}. Saldo total {money(total)}" + (f"; el más bajo es {menor} con {money(validos[menor])}." if menor else ".")

    th = f'class="d-th" style="padding:12px 18px;background:{SOFT};font-family:{FONT_BODY};font-size:10.5px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;color:{BRAND_TX};'

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>Reporte de saldos | Angia Tech</title>
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;600;700;800&family=Sora:wght@600;700&display=swap" rel="stylesheet">
<style>{DARK_CSS}</style></head>
<body class="d-bg" style="margin:0;padding:0;background:{GROUND};">
<div class="d-hide" style="display:none;max-height:0;overflow:hidden;opacity:0;color:{GROUND};">{escape(pre)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="d-bg" style="background:{GROUND};"><tr><td align="center" style="padding:32px 12px;">
<table role="presentation" class="wrap d-card" width="680" cellpadding="0" cellspacing="0" style="width:680px;max-width:680px;background:{CARD};border:1px solid {LINE};border-radius:20px;border-collapse:separate;overflow:hidden;">

<tr><td class="px" bgcolor="{HEAD}" style="background:{HEAD};background-image:linear-gradient(160deg,#1E0F45 0%,#3B1A78 100%);padding:30px 36px 32px 36px;">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
  <td style="font-family:{FONT_DISPLAY};font-size:13px;font-weight:700;letter-spacing:3px;color:#FFFFFF;">ANGIA<span style="color:#C4B5FD;">&nbsp;TECH</span></td>
  <td align="right" style="font-family:{FONT_BODY};font-size:11px;letter-spacing:.6px;color:#C4B5FD;">Monitoreo 24/7 &middot; GitHub Actions</td>
 </tr></table>
 <div style="font-family:{FONT_BODY};font-size:11px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:#C4B5FD;margin-top:30px;">Saldo total en infraestructura</div>
 <div class="big" style="font-family:{FONT_DISPLAY};font-size:52px;font-weight:700;letter-spacing:-2px;line-height:1.05;color:#FFFFFF;margin-top:6px;">{money(total)}</div>
 <div style="font-family:{FONT_BODY};font-size:13px;color:#DDD6FE;margin-top:10px;">Corte: {corte}</div>
</td></tr>

<tr><td class="px" style="padding:26px 36px 8px 36px;">
 <table role="presentation" cellpadding="0" cellspacing="0"><tr>
  <td><span class="d-{est_n}" style="display:inline-block;background:{chip_bg};color:{chip_fg};font-family:{FONT_BODY};font-size:10px;font-weight:800;letter-spacing:1px;padding:5px 11px;border-radius:99px;">ESTADO GENERAL</span></td>
 </tr></table>
 <div class="d-ink" style="font-family:{FONT_DISPLAY};font-size:21px;font-weight:700;letter-spacing:-.4px;color:{INK};margin-top:12px;">{escape(estado)}</div>
 <div class="d-mut" style="font-family:{FONT_BODY};font-size:14px;line-height:1.55;color:{MUTED};margin-top:5px;">{escape(detalle)}</div>
</td></tr>
{aviso}
<tr><td class="px" style="padding:14px 31px 0 31px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{tarjetas}</tr></table></td></tr>

<tr><td class="px" style="padding:26px 36px 4px 36px;">
 <div class="d-ink" style="font-family:{FONT_DISPLAY};font-size:16px;font-weight:700;letter-spacing:-.2px;color:{INK};margin-bottom:12px;">Detalle por servicio</div>
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="d-line" style="border:1px solid {LINE};border-radius:14px;border-collapse:separate;overflow:hidden;">
  <tr><th align="left" {th}">Servicio</th><th align="right" {th}">Saldo</th><th align="right" class="d-th hm" style="padding:12px 18px;background:{SOFT};font-family:{FONT_BODY};font-size:10.5px;font-weight:800;letter-spacing:1.2px;text-transform:uppercase;color:{BRAND_TX};">Margen</th><th {th}">Estado</th></tr>
  {filas}
 </table>
 <div class="d-mut" style="font-family:{FONT_BODY};font-size:11.5px;line-height:1.8;color:{MUTED};margin-top:12px;">
  Medidor de $0 a ${ESCALA:.0f}:
  <span style="color:#DC2626;">&#9632;</span> crítico &lt; ${UMBRAL_CRITICO:.0f} &nbsp;
  <span style="color:#F59E0B;">&#9632;</span> atención ${UMBRAL_CRITICO:.0f}&ndash;${UMBRAL_OPTIMO - 0.01:.2f} &nbsp;
  <span style="color:#16A34A;">&#9632;</span> óptimo &ge; ${UMBRAL_OPTIMO:.0f}
 </div>
</td></tr>

<tr><td class="px" style="padding:22px 36px 30px 36px;">
 <div class="d-ink" style="font-family:{FONT_DISPLAY};font-size:16px;font-weight:700;letter-spacing:-.2px;color:{INK};margin-bottom:10px;">Alertas</div>
 <div class="d-soft d-mut" style="font-family:{FONT_BODY};font-size:13.5px;line-height:1.6;color:{MUTED};background:{SOFT};border-radius:12px;padding:14px 18px;">{alertas_html}</div>
</td></tr>

<tr><td class="px" bgcolor="{HEAD}" align="center" style="background:{HEAD};padding:22px 36px;">
 <div style="font-family:{FONT_BODY};font-size:12px;font-weight:700;letter-spacing:.3px;color:#EDE9FE;">Angia Tech &middot; Monitoreo automatizado de infraestructura</div>
 <div style="font-family:{FONT_BODY};font-size:11px;line-height:1.5;color:#A78BFA;margin-top:6px;">Enviado automáticamente por GitHub Actions vía Amazon WorkMail. Mensaje de sistema, no responder.</div>
</td></tr>
</table></td></tr></table></body></html>"""


def construir_texto(fecha, saldos, alertas):
    corte = f"{fecha:%Y-%m-%d %H:%M} UTC" if fecha else "fecha no disponible"
    lineas = ["REPORTE EJECUTIVO DE SALDOS - ANGIA TECH", f"Corte: {corte}", ""]
    lineas += [f"- {s}: {money(v)}  [{NIVELES[nivel(v)][0]}]" for s, v in saldos.items()]
    return "\n".join(lineas + ["", alertas or "Sin alertas registradas."])


def asunto(saldos, warning):
    bajos = [s for s, v in saldos.items() if nivel(v) == "crit"]
    if warning or bajos:
        return "URGENTE: Saldos de infraestructura - " + (", ".join(bajos) or "revisar alertas")
    return "Reporte ejecutivo de saldos de infraestructura - Angia Tech"


def enviar_reporte():
    fecha, saldos, alertas, warning = leer_reporte()
    html = construir_html(fecha, saldos, alertas, warning)

    if "--dry-run" in sys.argv:
        i = sys.argv.index("--dry-run")
        salida = sys.argv[i + 1] if len(sys.argv) > i + 1 else "preview_correo.html"
        with open(salida, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Vista previa escrita en {salida}")
        return 0

    user, pwd = os.environ.get("WORKMAIL_USER"), os.environ.get("WORKMAIL_PASS")
    if not user or not pwd:
        print("ERROR: faltan WORKMAIL_USER / WORKMAIL_PASS", file=sys.stderr)
        return 1

    msg = MIMEMultipart("alternative")
    msg["From"] = user
    msg["To"] = ", ".join(DESTINATARIOS)
    msg["Subject"] = asunto(saldos, warning)
    msg.attach(MIMEText(construir_texto(fecha, saldos, alertas), "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
            server.login(user, pwd)
            server.sendmail(user, DESTINATARIOS, msg.as_string())
    except Exception as e:  # que el paso del workflow falle de forma visible
        print(f"Error al enviar correo: {e}", file=sys.stderr)
        return 1
    print("Correo enviado vía WorkMail a: " + ", ".join(DESTINATARIOS))
    return 0


if __name__ == "__main__":
    sys.exit(enviar_reporte())
