#!/usr/bin/env python3
"""Envia por e-mail (HTML ejecutivo) el reporte de saldos de infraestructura.

Lee Entradas/reporte_saldos.txt y envia el correo via Amazon WorkMail (SMTP SSL 465).
Variables de entorno requeridas: WORKMAIL_USER, WORKMAIL_PASS
Uso: python enviar_correo.py [--dry-run [salida.html]]
"""
import os
import re
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

REPORTE = os.path.join("Entradas", "reporte_saldos.txt")
SMTP_HOST = "smtp.mail.us-east-1.awsapps.com"
SMTP_PORT = 465
DESTINATARIOS = ["tzules@angia.tech", "aarmas@angia.tech"]
UMBRAL_CRITICO = 20.00
UMBRAL_OK = 30.00
SERVICIOS = ["OpenRouter", "CapSolver", "2Captcha", "DeCodo"]

# nivel -> (etiqueta, fondo badge, texto badge, color acento)
NIVELES = {
    "ok": ("SALDO OPTIMO", "#DCFCE7", "#166534", "#16A34A"),
    "warn": ("PRECAUCION", "#FEF3C7", "#92400E", "#F59E0B"),
    "crit": ("CRITICO", "#FEE2E2", "#991B1B", "#DC2626"),
    "na": ("SIN DATO", "#E5E7EB", "#374151", "#9CA3AF"),
}


def nivel(saldo):
    if saldo is None:
        return "na"
    if saldo >= UMBRAL_OK:
        return "ok"
    if saldo >= UMBRAL_CRITICO:
        return "warn"
    return "crit"


def leer_reporte(ruta=REPORTE):
    with open(ruta, encoding="utf-8") as f:
        texto = f.read()
    m = re.search(r"Fecha/Hora:\s*(.+)", texto)
    fecha = m.group(1).strip() if m else "No disponible"
    saldos = {}
    for s in SERVICIOS:
        m = re.search(rf"{re.escape(s)}\s*:\s*\$?\s*([\d.,]+)", texto, re.I)
        saldos[s] = float(m.group(1).replace(",", "")) if m else None
    alertas = ""
    m = re.search(r"ALERTAS DETECTADAS:\s*(.+)", texto, re.S)
    if m:
        alertas = m.group(1).strip()
    warning = "[WARNING]" in texto.upper()
    return fecha, saldos, alertas, warning


def antiguedad_horas(fecha):
    try:
        return (datetime.now() - datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
    except ValueError:
        return None


def money(v):
    return "N/D" if v is None else f"${v:,.2f}"


def construir_html(fecha, saldos, alertas, warning):
    niveles = {s: nivel(v) for s, v in saldos.items()}
    hay_crit = any(n == "crit" for n in niveles.values()) or warning
    hay_warn = any(n == "warn" for n in niveles.values())
    if hay_crit:
        estado, est_nivel = "ACCION REQUERIDA: saldo bajo el umbral critico", "crit"
    elif hay_warn:
        estado, est_nivel = "OPERATIVO CON PRECAUCION: saldos proximos al umbral", "warn"
    else:
        estado, est_nivel = "OPERATIVO: todos los saldos en rango optimo", "ok"
    est_color = NIVELES[est_nivel][3]

    validos = {s: v for s, v in saldos.items() if v is not None}
    total = sum(validos.values())
    menor_s = min(validos, key=validos.get) if validos else None
    menor_txt = f"{menor_s} {money(validos[menor_s])}" if menor_s else "N/D"

    horas = antiguedad_horas(fecha)
    aviso = ""
    if horas is not None and horas > 24:
        aviso = (
            '<tr><td style="padding:0 32px 16px 32px;"><div style="background:#FEF3C7;border-left:4px solid #F59E0B;'
            'padding:12px 16px;border-radius:6px;font-size:13px;color:#92400E;">'
            f"<strong>Reporte desactualizado:</strong> tiene {horas/24:.1f} dias de antiguedad. "
            "Verifique la ejecucion del workflow.</div></td></tr>"
        )

    def kpi(titulo, valor, color):
        return (
            '<td width="25%" style="padding:6px;" valign="top"><div style="background:#F8FAFC;border:1px solid #E2E8F0;'
            f'border-top:4px solid {color};border-radius:8px;padding:14px 12px;text-align:center;">'
            f'<div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:.5px;">{escape(titulo)}</div>'
            f'<div style="font-size:20px;font-weight:700;color:#0F172A;margin-top:6px;">{escape(valor)}</div></div></td>'
        )

    tarjetas = "".join(kpi(s, money(v), NIVELES[niveles[s]][3]) for s, v in saldos.items())

    filas = ""
    for i, (s, v) in enumerate(sorted(saldos.items(), key=lambda kv: (kv[1] is None, kv[1] or 0))):
        etiqueta, bg, fg, _ = NIVELES[niveles[s]]
        margen = "N/D" if v is None else (f"+${v - UMBRAL_CRITICO:,.2f}" if v >= UMBRAL_CRITICO else f"-${UMBRAL_CRITICO - v:,.2f}")
        fondo = "#FFFFFF" if i % 2 == 0 else "#F8FAFC"
        filas += (
            f'<tr style="background:{fondo};">'
            f'<td style="padding:12px 14px;border-bottom:1px solid #E2E8F0;font-weight:600;color:#0F172A;">{escape(s)}</td>'
            f'<td style="padding:12px 14px;border-bottom:1px solid #E2E8F0;text-align:right;color:#0F172A;">{money(v)}</td>'
            f'<td style="padding:12px 14px;border-bottom:1px solid #E2E8F0;text-align:right;color:#475569;">{margen}</td>'
            f'<td style="padding:12px 14px;border-bottom:1px solid #E2E8F0;text-align:center;">'
            f'<span style="display:inline-block;background:{bg};color:{fg};font-size:11px;font-weight:700;'
            f'padding:4px 10px;border-radius:999px;">{etiqueta}</span></td></tr>'
        )

    alerta_html = escape(alertas).replace("\n", "<br>") if alertas else "Sin alertas registradas."

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Informe de saldos de infraestructura</title>
<style>@media only screen and (max-width:620px){{.kpi td{{display:block!important;width:100%!important;box-sizing:border-box}}.wrap{{width:100%!important}}}}</style>
</head>
<body style="margin:0;padding:0;background:#EEF2F7;font-family:Segoe UI,Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#EEF2F7;padding:24px 8px;"><tr><td align="center">
<table role="presentation" class="wrap" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:640px;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(15,23,42,.08);">
  <tr><td style="background:#4C1D95;padding:24px 32px;">
    <div style="font-size:12px;letter-spacing:2px;color:#DDD6FE;font-weight:700;">ANGIA TECH</div>
    <div style="font-size:22px;font-weight:700;color:#FFFFFF;margin-top:6px;">Informe de saldos de infraestructura</div>
    <div style="font-size:13px;color:#EDE9FE;margin-top:6px;">Reporte generado: {escape(fecha)} &middot; Origen: GitHub Actions 24/7</div>
  </td></tr>
  <tr><td style="padding:24px 32px 8px 32px;">
    <div style="border-left:5px solid {est_color};background:#F8FAFC;padding:14px 16px;border-radius:6px;">
      <div style="font-size:11px;color:#64748B;text-transform:uppercase;letter-spacing:.5px;">Estado general</div>
      <div style="font-size:16px;font-weight:700;color:#0F172A;margin-top:4px;">{escape(estado)}</div>
    </div>
  </td></tr>
  {aviso}
  <tr><td style="padding:8px 26px 0 26px;"><table role="presentation" class="kpi" width="100%" cellpadding="0" cellspacing="0"><tr>{tarjetas}</tr></table></td></tr>
  <tr><td style="padding:16px 32px 0 32px;font-size:13px;color:#475569;">
    Total acumulado: <strong style="color:#0F172A;">{money(total)}</strong> &nbsp;|&nbsp; Saldo mas bajo: <strong style="color:#0F172A;">{escape(menor_txt)}</strong>
  </td></tr>
  <tr><td style="padding:20px 32px 8px 32px;">
    <div style="font-size:15px;font-weight:700;color:#0F172A;margin-bottom:10px;">Detalle por servicio</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #E2E8F0;border-radius:8px;border-collapse:separate;font-size:14px;">
      <tr style="background:#4C1D95;"><th align="left" style="padding:10px 14px;color:#fff;font-size:12px;">Servicio</th><th align="right" style="padding:10px 14px;color:#fff;font-size:12px;">Saldo</th><th align="right" style="padding:10px 14px;color:#fff;font-size:12px;">Margen vs $20</th><th style="padding:10px 14px;color:#fff;font-size:12px;">Estado</th></tr>
      {filas}
    </table>
  </td></tr>
  <tr><td style="padding:16px 32px 8px 32px;">
    <div style="font-size:15px;font-weight:700;color:#0F172A;margin-bottom:6px;">Alertas</div>
    <div style="font-size:13px;color:#475569;line-height:1.5;">{alerta_html}</div>
  </td></tr>
  <tr><td style="padding:16px 32px 8px 32px;font-size:12px;color:#64748B;">
    <span style="color:#16A34A;font-weight:700;">&#9679;</span> Optimo &ge; ${UMBRAL_OK:.2f} &nbsp;
    <span style="color:#F59E0B;font-weight:700;">&#9679;</span> Precaucion ${UMBRAL_CRITICO:.2f}&ndash;${UMBRAL_OK - 0.01:.2f} &nbsp;
    <span style="color:#DC2626;font-weight:700;">&#9679;</span> Critico &lt; ${UMBRAL_CRITICO:.2f}
  </td></tr>
  <tr><td style="background:#F1F5F9;padding:18px 32px;margin-top:16px;font-size:11px;color:#64748B;text-align:center;">
    Angia Tech &middot; Monitoreo automatizado de infraestructura<br>Mensaje generado automaticamente; no responder.
  </td></tr>
</table></td></tr></table></body></html>"""


def construir_texto(fecha, saldos, alertas):
    lineas = ["INFORME DE SALDOS DE INFRAESTRUCTURA - ANGIA TECH", f"Reporte: {fecha}", ""]
    lineas += [f"- {s}: {money(v)}" for s, v in saldos.items()]
    lineas += ["", alertas or "Sin alertas registradas."]
    return "\n".join(lineas)


def asunto(saldos, warning):
    if warning or any(nivel(v) == "crit" for v in saldos.values()):
        bajos = [s for s, v in saldos.items() if nivel(v) == "crit"]
        return "URGENTE: Saldos de infraestructura - " + (", ".join(bajos) or "revisar alertas")
    return f"Mini informe de saldos de infraestructura - {datetime.now():%Y-%m-%d %H:%M}"


def main():
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
        print("ERROR: faltan variables de entorno WORKMAIL_USER / WORKMAIL_PASS", file=sys.stderr)
        return 1

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto(saldos, warning)
    msg["From"] = user
    msg["To"] = ", ".join(DESTINATARIOS)
    msg.attach(MIMEText(construir_texto(fecha, saldos, alertas), "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.login(user, pwd)
        server.sendmail(user, DESTINATARIOS, msg.as_string())
    print("Correo enviado a: " + ", ".join(DESTINATARIOS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
