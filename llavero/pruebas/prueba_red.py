# Wonder - PRUEBA DE RED: ¿por qué el llavero no llega al hub?
# Abre este archivo en Thonny (desde el computador) y pulsa Run. Lee el VEREDICTO al final.

import time
import socket
import json
import red

print()
print("=== 1. CONFIGURACIÓN GUARDADA ===")
red.cargar()
print("Redes guardadas:", red.nombres())
for r in red.cfg["redes"]:
    print("  ", r["nombre"], "-> hub:", r.get("servidor") or "(sin dirección)")
print("Hub general:", red.cfg["servidor"] or "(sin dirección)")
print("Clave del llavero:", "OK" if red.cfg["clave"] else "FALTA")

print()
print("=== 2. WIFI ===")
if not red.conectar_ya(lambda n: None, 30):
    print("VEREDICTO: el llavero NO se conecta a ninguna red guardada.")
    print("Revisa que el WiFi del celular esté prendido (iPhone: Maximizar compatibilidad).")
    raise SystemExit
ip, mascara, puerta, dns = red.wlan.ifconfig()
print("Conectado a:", red.red_actual, "| IP del llavero:", ip, "| router:", puerta)

print()
print("=== 3. INTERNET ===")
s = socket.socket()
s.settimeout(4)
try:
    s.connect(socket.getaddrinfo("8.8.8.8", 53)[0][-1])
    print("Internet: OK")
except OSError as e:
    print("Internet: NO (", e, ")")
finally:
    s.close()

print()
print("=== 4. BUSCAR EL HUB EN LA RED (5 s) ===")
encontrado = red.buscar_hub(5)
print("El hub avisó su dirección:", red.servidor() if encontrado else "NO se escuchó ningún aviso")

print()
print("=== 5. CONECTAR AL HUB ===")
url = red.servidor()
print("Probando:", url or "(sin dirección)")
puerto_ok = False
if url.startswith("http://"):
    hostport = url[7:].split("/")[0]
    host, _, puerto = hostport.partition(":")
    puerto = int(puerto or 80)
    mismo = host.rsplit(".", 1)[0] == ip.rsplit(".", 1)[0]
    print("¿El hub está en la misma red que el llavero?", "SÍ" if mismo else "NO (%s vs %s)" % (host, ip))
    s = socket.socket()
    s.settimeout(5)
    try:
        s.connect(socket.getaddrinfo(host, puerto)[0][-1])
        puerto_ok = True
        print("Puerto %d del computador: ABIERTO" % puerto)
    except OSError as e:
        print("Puerto %d del computador: NO RESPONDE (" % puerto, e, ")")
    finally:
        s.close()
codigo = 0
if puerto_ok:
    codigo, datos = red.pedir("/pico/estado", timeout=6, buscar=False)
    print("Respuesta del hub:", codigo, datos)

print()
print("=================== VEREDICTO ===================")
if codigo == 200:
    print("TODO BIEN: el llavero llega al hub. Si main.py dice 'Sin hub', reinicia el llavero.")
elif codigo == 401:
    print("El hub responde pero la CLAVE del llavero no coincide.")
    print("Vuelve a configurar el llavero desde la app (Agregar red WiFi).")
elif puerto_ok:
    print("El computador responde pero no es el hub (o dio error %s)." % codigo)
elif not url.startswith("http://"):
    print("El llavero no tiene la dirección del hub y no escuchó su aviso.")
    print("Pon en config.json \"servidor\": \"http://IP-DEL-COMPUTADOR:8000\".")
elif not mismo:
    print("El hub está en OTRA red. Conecta el computador al mismo WiFi que el llavero")
    print("(%s), reinicia el hub y vuelve a probar." % red.red_actual)
else:
    print("El computador está en la misma red pero NO deja entrar al llavero:")
    print("es el FIREWALL de Windows o el hub está apagado.")
    print("PowerShell como administrador:")
    print('New-NetFirewallRule -DisplayName "Wonder Hub" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Any')
print("=================================================")
