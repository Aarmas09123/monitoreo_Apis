import os
import requests
import json
from datetime import datetime

UMBRAL = 20.00

SERVICIOS = [
    {"nombre": "OpenRouter", "url": "https://openrouter.ai/api/v1/credits", "key": os.getenv("OPENROUTER_API_KEY"), "tipo": "openrouter"},
    {"nombre": "CapSolver", "url": "https://api.capsolver.com/getBalance", "key": os.getenv("CAPSOLVER_API_KEY"), "tipo": "capsolver"},
    {"nombre": "2Captcha", "url": "https://2captcha.com/res.php?key=" + (os.getenv("TWOCAPTCHA_API_KEY") or "") + "&action=getbalance&json=1", "key": os.getenv("TWOCAPTCHA_API_KEY"), "tipo": "2captcha"},
    {"nombre": "DeCodo", "url": "https://api.decodo.com/v1/user/traffic", "key": os.getenv("DECODO_API_KEY"), "tipo": "decodo"}
]

alertas = []
resumen = []

for srv in SERVICIOS:
    nombre = srv["nombre"]
    key = srv["key"]
    if not key:
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
            saldo = round(50.00 - (gb_usados * 3.00), 2) # Estimación según tráfico

        resumen.append(f"{nombre}: ${saldo:.2f} USD")
        if saldo < UMBRAL:
            alertas.append(f"[WARNING] {nombre} tiene un saldo crítico de ${saldo:.2f} USD (Menor a $20.00 USD)")
    except Exception as e:
        alertas.append(f"[WARNING] {nombre} falló al consultar saldo: {str(e)}")

print("=== REVISIÓN DE SALDOS EN INFRAESTRUCTURA (NUBE) ===")
print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
for r in resumen:
    print(f"- {r}")

print("\nALERTAS DETECTADAS:")
if alertas:
    for a in alertas:
        print(a)
else:
    print("Sin novedades. Todos los saldos superan los $20.00 USD.")
