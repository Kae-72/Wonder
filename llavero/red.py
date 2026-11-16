# Wonder - WiFi y conexión con Wonder Hub
#
# El llavero RECUERDA VARIAS REDES (casa, universidad, el compartido del celular...).
# Cada red nueva que manda la app se AGREGA; las anteriores no se borran.
# Se conecta solo, en segundo plano, a la primera que encuentre.
#
# Como la IP del computador cambia en cada red, cada red guarda su propia
# dirección del hub. Si el hub no contesta, el llavero lo busca solo: el hub
# avisa por la red local dónde está (puerto UDP 37020).

import network
import time
import json
import socket
import machine

try:
    import requests
except ImportError:
    import urequests as requests

ARCHIVO = "config.json"
MAX_REDES = 8
PUERTO_BUSQUEDA = 37020
ESPERA_POR_RED_MS = 12000      # cuánto esperar a cada red antes de probar la siguiente
PAUSA_ENTRE_RONDAS_MS = 45000  # si no hay ninguna red conocida cerca, descansa
ZONA_HORARIA = -5              # Colombia (solo se usa si la hora viene de internet)

cfg = {"redes": [], "servidor": "", "clave": ""}
wlan = network.WLAN(network.STA_IF)
red_actual = None

_indice = 0
_intentando = None
_t_intento = 0
_t_ronda = -PAUSA_ENTRE_RONDAS_MS
_estaba = False
recien_conectado = False


# ---------------- Configuración guardada ----------------
def cargar():
    """Lee config.json. Acepta el formato viejo (una sola red) y lo convierte."""
    global cfg
    try:
        with open(ARCHIVO) as f:
            c = json.load(f)
    except (OSError, ValueError):
        c = {}
    redes = c.get("redes") or []
    if c.get("wifi_nombre"):                                    # formato viejo
        if not any(r.get("nombre") == c["wifi_nombre"] for r in redes):
            redes.append({"nombre": c["wifi_nombre"], "clave": c.get("wifi_clave", ""),
                          "servidor": c.get("servidor", "")})
    servidor = c.get("servidor", "")
    if servidor.endswith("/eventos"):
        servidor = servidor[:-8]
    cfg = {"redes": redes, "servidor": servidor.rstrip("/"), "clave": c.get("clave", "")}
    return configurado()


def configurado():
    return bool(cfg["redes"] and cfg["clave"])


def guardar():
    with open(ARCHIVO + ".tmp", "w") as f:
        json.dump(cfg, f)
    try:
        import os
        os.remove(ARCHIVO)
    except OSError:
        pass
    import os
    os.rename(ARCHIVO + ".tmp", ARCHIVO)


def agregar_red(nombre, clave, servidor="", clave_llavero=""):
    """Agrega (o actualiza) una red. Las demás quedan igual."""
    servidor = servidor.strip().rstrip("/")
    redes = [r for r in cfg["redes"] if r["nombre"] != nombre]
    redes.insert(0, {"nombre": nombre, "clave": clave, "servidor": servidor})
    cfg["redes"] = redes[:MAX_REDES]
    if servidor:
        cfg["servidor"] = servidor
    if clave_llavero:
        cfg["clave"] = clave_llavero
    guardar()


def olvidar_red(nombre):
    cfg["redes"] = [r for r in cfg["redes"] if r["nombre"] != nombre]
    guardar()


def nombres():
    return [r["nombre"] for r in cfg["redes"]]


def servidor():
    for r in cfg["redes"]:
        if r["nombre"] == red_actual and r.get("servidor"):
            return r["servidor"]
    return cfg["servidor"]


def _poner_servidor(url):
    cambio = False
    for r in cfg["redes"]:
        if r["nombre"] == red_actual and r.get("servidor") != url:
            r["servidor"] = url
            cambio = True
    if cfg["servidor"] != url:
        cfg["servidor"] = url
        cambio = True
    if cambio:
        guardar()


# ---------------- Conexión ----------------
def conectado():
    return wlan.isconnected()


def mantener():
    """Llamar seguido (cada ~1 s). Conecta solo, sin detener la pantalla."""
    global _indice, _intentando, _t_intento, _t_ronda, red_actual, _estaba, recien_conectado
    ahora = time.ticks_ms()
    if wlan.isconnected():
        if not _estaba:
            _estaba = True
            recien_conectado = True
            red_actual = _intentando or red_actual
            if not red_actual:
                try:
                    red_actual = wlan.config("ssid")
                except Exception:
                    pass
            print("WiFi conectado a", red_actual, wlan.ifconfig()[0])
        _intentando = None
        return True
    if _estaba:
        print("WiFi perdido")
        _estaba = False
        red_actual = None
    if not cfg["redes"]:
        return False
    if _intentando and time.ticks_diff(ahora, _t_intento) < ESPERA_POR_RED_MS:
        return False
    if _indice >= len(cfg["redes"]):                 # terminó una ronda sin suerte
        if time.ticks_diff(ahora, _t_ronda) < PAUSA_ENTRE_RONDAS_MS:
            if _intentando:
                wlan.disconnect()
                _intentando = None
            return False
        _indice = 0
    if _indice == 0:
        _t_ronda = ahora
    r = cfg["redes"][_indice]
    _indice += 1
    try:
        wlan.active(True)
        if _intentando:
            wlan.disconnect()
        wlan.connect(r["nombre"], r["clave"])
        _intentando = r["nombre"]
        _t_intento = ahora
    except Exception as e:
        print("WiFi:", e)
    return False


def reconectar():
    """Tras apagar el WiFi un instante (p. ej. para medir la batería): vuelve a conectar ya."""
    global _indice, _t_ronda, _intentando
    _indice = 0
    _intentando = None
    _t_ronda = time.ticks_add(time.ticks_ms(), -PAUSA_ENTRE_RONDAS_MS)


def conectar_ya(al_esperar=None, segundos=25):
    """Conexión con espera (cuando el usuario pidió algo que necesita internet)."""
    global _indice, _t_ronda
    if wlan.isconnected():
        return True
    _indice = 0
    _t_ronda = time.ticks_add(time.ticks_ms(), -PAUSA_ENTRE_RONDAS_MS)
    fin = time.ticks_add(time.ticks_ms(), segundos * 1000)
    while time.ticks_diff(fin, time.ticks_ms()) > 0:
        if mantener():
            return True
        if al_esperar:
            al_esperar(_intentando or "")
        time.sleep_ms(300)
    return mantener()


def apagar_wifi():
    global _intentando, _estaba, red_actual
    wlan.active(False)
    _intentando = None
    _estaba = False
    red_actual = None


# ---------------- Hablar con Wonder Hub ----------------
def _cabeceras():
    return {"X-Wonder-Key": cfg["clave"]}


def buscar_hub(segundos=2):
    """Escucha el aviso del hub en la red local y guarda su dirección."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", PUERTO_BUSQUEDA))
        s.settimeout(segundos)
        datos, _ = s.recvfrom(256)
        texto = datos.decode()
        if texto.startswith("WONDER-HUB "):
            url = texto.split()[1].rstrip("/")
            print("Hub encontrado en", url)
            _poner_servidor(url)
            return True
    except OSError:
        pass
    finally:
        s.close()
    return False


def pedir(ruta, timeout=6, buscar=True):
    """GET al hub. Devuelve (codigo, datos_json o None). Si el hub no
    contesta, lo busca en la red y lo intenta una vez más."""
    for intento in (0, 1):
        url = servidor()
        if url:
            try:
                r = requests.get(url + ruta, headers=_cabeceras(), timeout=timeout)
                try:
                    codigo = r.status_code
                    datos = json.loads(r.text) if codigo in (200, 401, 409, 503) else None
                finally:
                    r.close()
                return codigo, datos
            except (OSError, ValueError) as e:
                print("Hub no responde:", e)
        if intento == 0 and buscar and buscar_hub():
            continue
        break
    return 0, None


def enviar(ruta, datos, timeout=6):
    """POST con JSON al hub. Devuelve (codigo, datos_json o None)."""
    url = servidor()
    if not url:
        return 0, None
    try:
        r = requests.post(url + ruta, json=datos, headers=_cabeceras(), timeout=timeout)
        try:
            codigo = r.status_code
            texto = r.text
        finally:
            r.close()
        return codigo, (json.loads(texto) if texto else None)
    except (OSError, ValueError) as e:
        print("Hub no responde:", e)
        return 0, None


def descargar(ruta, archivo, tam, timeout=10):
    """Descarga binaria al archivo (para Mi Wonder). True si llegó completa."""
    r = requests.get(servidor() + ruta, headers=_cabeceras(), timeout=timeout)
    falta = tam
    try:
        if r.status_code != 200:
            return False
        trozo = bytearray(1024)
        vista = memoryview(trozo)
        with open(archivo, "wb") as f:
            while falta:
                n = r.raw.readinto(trozo)
                if not n:
                    break
                f.write(vista[:n])
                falta -= n
    finally:
        r.close()
    return falta == 0


def poner_hora(ahora):
    """ahora = [año, mes, día, hora, min, seg, día_semana(0=lunes)] desde el hub."""
    try:
        a, mes, d, h, mi, s, ds = ahora
        machine.RTC().datetime((a, mes, d, ds, h, mi, s, 0))
        return True
    except Exception as e:
        print("Hora:", e)
        return False


def hora_de_internet():
    """Plan B si no hay hub: la hora de internet (NTP), ajustada a Colombia."""
    try:
        import ntptime
        ntptime.settime()
        t = time.localtime(time.time() + ZONA_HORARIA * 3600)
        machine.RTC().datetime((t[0], t[1], t[2], t[6], t[3], t[4], t[5], 0))
        return True
    except Exception as e:
        print("NTP:", e)
        return False


def citar(t):
    """Codifica texto para ponerlo en una URL."""
    seguro = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    return "".join(c if c in seguro else "".join("%%%02X" % b for b in c.encode()) for c in t)


def subir_archivo(ruta, nombre, al_avanzar=None, parte=256 * 1024):
    """Sube un .wav al hub por partes (se puede retomar si se corta).
    Guarda el avance en ruta + '.pos'."""
    import os
    total = os.stat(ruta)[6]
    try:
        with open(ruta + ".pos") as f:
            pos = int(f.read())
    except (OSError, ValueError):
        pos = 0
    url = servidor()
    if not url.startswith("http://"):
        raise OSError("sin hub")
    hostport = url[7:].split("/")[0]
    host, _, puerto = hostport.partition(":")
    puerto = int(puerto or 80)
    trozo = bytearray(4096)
    mv = memoryview(trozo)
    with open(ruta, "rb") as f:
        while True:
            if pos > total:
                pos = 0
            n = min(parte, total - pos)
            fin = pos + n >= total
            ruta_http = "/pico/audio?nombre=%s&pos=%d%s" % (citar(nombre), pos, "&fin=1" if fin else "")
            s = socket.socket()
            try:
                s.settimeout(20)
                s.connect(socket.getaddrinfo(host, puerto)[0][-1])
                s.write(("POST %s HTTP/1.1\r\nHost: %s\r\nX-Wonder-Key: %s\r\n"
                         "Content-Type: application/octet-stream\r\nContent-Length: %d\r\n"
                         "Connection: close\r\n\r\n" % (ruta_http, hostport, cfg["clave"], n)).encode())
                f.seek(pos)
                falta = n
                while falta:
                    k = f.readinto(mv[:min(4096, falta)])
                    if not k:
                        raise OSError("archivo corto")
                    s.write(mv[:k])
                    falta -= k
                resp = b""
                while True:
                    d = s.read(512)
                    if not d:
                        break
                    resp += d
            finally:
                s.close()
            cabeza, _, cuerpo = resp.partition(b"\r\n\r\n")
            codigo = int(cabeza.split(b" ")[1]) if cabeza else 0
            try:
                datos = json.loads(cuerpo)
            except ValueError:
                datos = {}
            if codigo == 200:
                pos = datos.get("pos", pos + n)
            elif codigo == 409 and "pos" in datos:
                pos = datos["pos"]              # el hub tenía otro avance: retomar desde ahí
            else:
                raise OSError("hub respondió %d" % codigo)
            with open(ruta + ".pos", "w") as fp:
                fp.write(str(pos))
            if al_avanzar:
                al_avanzar(pos, total)
            if codigo == 200 and fin:
                break
    try:
        os.remove(ruta + ".pos")
    except OSError:
        pass
    return True
