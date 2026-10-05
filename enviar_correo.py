from datetime import datetime
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def obtener_badge(saldo_str):
  try:
    monto = float(saldo_str.replace('$', '').strip())
    if monto < 20.0:
      return '#fee2e2', '#991b1b', 'CRÍTICO'
    elif monto < 30.0:
      return '#fef3c7', '#92400e', 'ATENCIÓN'
    return '#dcfce7', '#166534', 'ÓPTIMO'
  except Exception:
    return '#f3f4f6', '#374151', 'DESCONOCIDO'


def generar_html(saldos_dict):
  fecha_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')

  filas = ''
  for servicio, saldo in saldos_dict.items():
    bg, fg, label = obtener_badge(saldo)
    filas += f"""
        <tr style="border-bottom: 1px solid #f3e8ff;">
            <td style="padding: 14px 16px; font-weight: 600; color: #3b0764;">{servicio}</td>
            <td style="padding: 14px 16px; font-weight: 700; color: #1e1b4b;">{saldo}</td>
            <td style="padding: 14px 16px; text-align: center;">
                <span style="background-color: {bg}; color: {fg}; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;">
                    {label}
                </span>
            </td>
        </tr>
        """

  return f"""
  <!DOCTYPE html>
  <html>
  <head><meta charset="utf-8"></head>
  <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #faf5ff; margin: 0; padding: 25px;">
      <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px rgba(88, 28, 135, 0.12); border: 1px solid #f3e8ff;">
          
          <!-- Header Morado Imperial -->
          <div style="background: linear-gradient(135deg, #2e1065 0%, #581c87 100%); padding: 28px; text-align: left;">
              <h2 style="color: #ffffff; margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">
                  📊 Reporte Ejecutivo de Saldos API
              </h2>
              <p style="color: #e9d5ff; margin: 6px 0 0 0; font-size: 13px; font-weight: 500;">
                  Sistema de Monitoreo Central • Angia Tech
              </p>
          </div>

          <!-- Contenido -->
          <div style="padding: 28px;">
              
              <!-- Cards KPI -->
              <table style="width: 100%; margin-bottom: 24px; border-spacing: 0;">
                  <tr>
                      <td style="width: 48%; background: #faf5ff; padding: 16px; border-radius: 10px; border: 1px solid #e9d5ff;">
                          <div style="font-size: 11px; text-transform: uppercase; color: #7e22ce; font-weight: 700; letter-spacing: 0.5px;">Última Consulta</div>
                          <div style="font-size: 13px; font-weight: 700; color: #2e1065; margin-top: 4px;">{fecha_str}</div>
                      </td>
                      <td style="width: 4%;"></td>
                      <td style="width: 48%; background: #faf5ff; padding: 16px; border-radius: 10px; border: 1px solid #e9d5ff;">
                          <div style="font-size: 11px; text-transform: uppercase; color: #7e22ce; font-weight: 700; letter-spacing: 0.5px;">Umbral Requerido</div>
                          <div style="font-size: 13px; font-weight: 700; color: #6b21a8; margin-top: 4px;">$20.00 USD</div>
                      </td>
                  </tr>
              </table>

              <!-- Tabla de Saldos -->
              <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                  <thead>
                      <tr style="background-color: #f3e8ff; text-align: left;">
                          <th style="padding: 12px 16px; color: #581c87; font-weight: 700; border-radius: 8px 0 0 8px;">Servicio</th>
                          <th style="padding: 12px 16px; color: #581c87; font-weight: 700;">Saldo Actual</th>
                          <th style="padding: 12px 16px; color: #581c87; font-weight: 700; text-align: center; border-radius: 0 8px 8px 0;">Estado</th>
                      </tr>
                  </thead>
                  <tbody>
                      {filas}
                  </tbody>
              </table>

          </div>

          <!-- Footer -->
          <div style="background-color: #faf5ff; padding: 18px 28px; text-align: center; border-top: 1px solid #f3e8ff;">
              <p style="margin: 0; font-size: 12px; color: #7e22ce; font-weight: 500;">
                  Enviado automáticamente vía Amazon WorkMail por GitHub Actions.
              </p>
          </div>
          
      </div>
  </body>
  </html>
  """


def enviar_reporte():
  smtp_server = 'smtp.mail.us-east-1.awsapps.com'
  smtp_port = 465

  remitente = os.environ.get('WORKMAIL_USER')
  password = os.environ.get('WORKMAIL_PASS')
  destinatarios = ['tzules@angia.tech', 'aarmas@angia.tech']

  saldos = {}
  try:
    with open('Entradas/reporte_saldos.txt', 'r', encoding='utf-8') as f:
      for linea in f:
        if ':' in linea:
          k, v = linea.split(':', 1)
          saldos[k.strip()] = v.strip()
  except Exception as e:
    saldos = {'Error': str(e)}

  cuerpo_html = generar_html(saldos)

  msg = MIMEMultipart('alternative')
  msg['From'] = remitente
  msg['To'] = ', '.join(destinatarios)
  msg['Subject'] = '📊 Reporte Ejecutivo de Saldos API - Angia Tech'
  msg.attach(MIMEText(cuerpo_html, 'html'))

  try:
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
      server.login(remitente, password)
      server.sendmail(remitente, destinatarios, msg.as_string())
    print('✅ Correo ejecutivo morado enviado exitosamente vía WorkMail.')
  except Exception as e:
    print(f'❌ Error al enviar correo: {e}')


if __name__ == '__main__':
  enviar_reporte()
