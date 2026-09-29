import os
import requests
from datetime import datetime

# Umbral mínimo operacional en USD
UMBRAL = 20.00

# Configuración de servicios y credenciales desde GitHub Secrets
SERVICIOS = [
    {
        "nombre": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/credits",
        "key": os.getenv("OPENROUTER_API_KEY"),
        "tipo": "openrouter"
    },
    {
        "nombre": "CapSolver",
        "url": "https://api.capsolver.com/getBalance",
        "key": os.getenv("CAPSOLVER_API_KEY"),
        "tipo": "capsolver"
    },
    {
        "nombre": "2Captcha",
        "url": f"https://2captcha.com/res.php?key={os.getenv('TWOCAPTCHA_API_KEY') or ''}&action=getbalance&json=1",
        "key": os.getenv("TWOCAPTCHA_API_KEY"),
        "tipo": "2captcha"
    },
    {
        "nombre": "DeCodo",
        "url": "https://api.decodo.com/v1/user/traffic",
        "key": os.getenv("DECODO_API_KEY"),
        "tipo": "decodo"
    }
]

alertas = []
resumen = []

# Iterar y consultar cada API
for srv in SERVICIOS:
    nombre = srv["nombre"]
    key = srv["key"]
    
    if not key:
        alertas.append(f"[WARNING] {nombre}: No se encontró la API Key en los secretos del repositorio.")
        continue

    try:
        if srv["tipo"] == "openrouter":
            res = requests.get(srv["url"], headers={"Authorization": f"Bearer {key}"}, timeout=10)
            data = res.json().get("data", {})
            saldo = round(data.get("total_credits", 0) - data.get("total_usage", 0), 2)

        elif srv["tipo"] == "capsolver":
            res = requests.post(srv["url"], json={"clientKey": key}, timeout=10)
            saldo = round(res.json().get("balance", 0.0), 2)

        elif srv["tipo"] == "2captcha":
            res = requests.get(srv["url"], timeout=10)
            saldo = round(float(res.json().get("request", 0.0)), 2)

        elif srv["tipo"] == "decodo":
            res = requests.get(srv["url"], headers={"Authorization": f"Bearer {key}"}, timeout=10)
            data = res.json()
            gb_usados = float(data.get("used_bytes", 0)) / (1024**3)
            # Estimación basada en tráfico restante asignado
            saldo = round(50.00 - (gb_usados * 3.00), 2)

        resumen.append(f"{nombre}: ${saldo:.2f} USD")
        
        # Verificar si está por debajo del umbral crítico
        if saldo < UMBRAL:
            alertas.append(f"[WARNING] {nombre} tiene un saldo crítico de ${saldo:.2f} USD (Menor a ${UMBRAL:.2f} USD)")

    except Exception as e:
        alertas.append(f"[WARNING] {nombre} falló al consultar saldo: {str(e)}")

# Crear la carpeta Entradas en el repositorio si no existe
os.makedirs("Entradas", exist_ok=True)

# Escribir el reporte consolidado
fecha_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
ruta_reporte = os.path.join("Entradas", "reporte_saldos.txt")

with open(ruta_reporte, "w", encoding="utf-8") as f:
    f.write("=== REVISIÓN DE SALDOS EN INFRAESTRUCTURA (NUBE) ===\n")
    f.write(f"Fecha/Hora: {fecha_hora}\n\n")
    f.write("ESTADO DE SALDOS:\n")
    for r in resumen:
        f.write(f"- {r}\n")
    f.write("\nALERTAS DETECTADAS:\n")
    if alertas:
        for a in alertas:
            f.write(f"{a}\n")
    else:
        f.write("Sin novedades. Todos los saldos superan el umbral mínimo operativo de $20.00 USD.\n")

print(f"Reporte generado exitosamente en: {ruta_reporte}")
