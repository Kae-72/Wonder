"""
Wonder Hub - el servidor local que une todo

    python hub.py            -> abre http://localhost:8000

Que hace:
  - Sirve la app web (carpeta ../app).
  - Login de Google (Calendar solo lectura + Google Docs).
  - Le entrega al llavero su calendario, su hora y su Wonder personalizado.
  - Vigila la carpeta de clases y procesa los audios (Whisper + Gemini).
  - Avisa por la red local donde esta (UDP 37020), para que el llavero lo
    encuentre solo aunque cambie la IP (por ejemplo, con el WiFi del celular).

Quien puede hablar con el hub:
  - La app en ESTE computador (http://localhost:8000): sin clave.
  - La app desde otro dispositivo del mismo WiFi: pide el PIN que aparece al
    arrancar el hub (y en la app, en este computador).
  - El llavero: manda su clave en la cabecera X-Wonder-Key.
"""

import hmac
import io
import json
import os
import secrets
import socket
import threading
import time
import urllib.parse
from datetime import datetime

from flask import Flask, Response, jsonify, redirect, request, send_file, send_from_directory

import calendario
import logros
import grabaciones
import pantallas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(BASE_DIR), "app")
DATOS_DIR = os.path.join(BASE_DIR, "datos")
CONFIG_FILE = os.path.join(DATOS_DIR, "config.json")
WONDER_FILE = os.path.join(DATOS_DIR, "wonder.json")

PUERTO = int(os.environ.get("WONDER_PUERTO", "8000"))
PUERTO_AVISO = 37020            # el llavero escucha aqui para encontrar el hub
DIAS_CALENDARIO = 7
POMODORO_DEFECTO = {"estudio": 25, "descanso": 5, "sesiones": 4}

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 620 * 1024 * 1024
_candado = threading.Lock()


# ---------------------------------------------------------------
# Configuracion del hub (se crea sola la primera vez)
# ---------------------------------------------------------------
def _leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def _escribir_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".tmp", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(ruta + ".tmp", ruta)
    try:
        os.chmod(ruta, 0o600)
    except OSError:
        pass


def cargar_config():
    cfg = _leer_json(CONFIG_FILE, {})
    cambio = False
    if not cfg.get("clave_pico"):
        cfg["clave_pico"] = secrets.token_hex(8)                 # la clave del llavero
        cambio = True
    if not cfg.get("pin"):
        cfg["pin"] = "%06d" % secrets.randbelow(1000000)         # para abrir la app desde el celular
        cambio = True
    if cambio:
        _escribir_json(CONFIG_FILE, cfg)
    return cfg


CONFIG = cargar_config()


def ip_local():
    """La IP de este computador en el WiFi (la que debe usar el llavero)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))        # no envia nada; solo elige la interfaz
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


# ---------------------------------------------------------------
# Estado de Wonder (emocion + accesorios) y del llavero
# ---------------------------------------------------------------
def leer_wonder():
    w = _leer_json(WONDER_FILE, {})
    emocion = w.get("emocion") if w.get("emocion") in pantallas.EMOCIONES else "base"
    accesorios = [a for a in pantallas.ACCESORIOS if a in (w.get("accesorios") or [])]
    return {"emocion": emocion, "accesorios": accesorios, "version": int(w.get("version", 1))}


PICO = {"visto": None, "ip": None, "wonder_version": None, "eventos": None,
        "bateria": None, "usb": None, "red": None, "redes": None}


def ahora_para_pico():
    """[anio, mes, dia, hora, min, seg, dia_semana(0=lunes)] para el reloj del llavero."""
    t = datetime.now(calendario.TIMEZONE)
    return [t.year, t.month, t.day, t.hour, t.minute, t.second, t.weekday()]


def leer_pomodoro():
    p = dict(POMODORO_DEFECTO)
    p.update({k: v for k, v in (CONFIG.get("pomodoro") or {}).items() if k in p})
    return p


def _pico_visto(**extra):
    with _candado:
        PICO["visto"] = time.time()
        PICO["ip"] = request.remote_addr
        PICO.update(extra)


# ---------------------------------------------------------------
# Permisos
# ---------------------------------------------------------------
_intentos = {}      # ip -> [fallos, bloqueado_hasta]


def _es_local():
    return request.remote_addr in ("127.0.0.1", "::1", "::ffff:127.0.0.1")


def _igual(a, b):
    return hmac.compare_digest(str(a or "").encode(), str(b or "").encode())


def _autorizado():
    return _es_local() or _igual(request.cookies.get("wonder_pin"), CONFIG["pin"])


@app.before_request
def _proteger():
    ruta = request.path
    if ruta.startswith("/api/") and ruta != "/api/emparejar":
        if not _autorizado():
            return jsonify(error="pin", mensaje="Escribe el PIN que muestra Wonder Hub en el computador."), 401
        if request.method != "GET" and request.headers.get("X-Wonder") != "app":
            return jsonify(error="origen"), 403         # evita que otra pagina web mande ordenes
    if ruta == "/eventos" or ruta.startswith("/pico/"):
        if not _igual(request.headers.get("X-Wonder-Key"), CONFIG["clave_pico"]):
            return jsonify(error="clave"), 401


@app.after_request
def _sin_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.errorhandler(413)
def _muy_grande(_e):
    return jsonify(error="El archivo es demasiado grande."), 413


def _error(e, codigo=400):
    return jsonify(error=str(e)), codigo


# ---------------------------------------------------------------
# App web (archivos) + regreso del login de Google
# ---------------------------------------------------------------
@app.get("/")
def inicio():
    if "state" in request.args and ("code" in request.args or "error" in request.args):
        if "error" in request.args:
            return redirect("/?google=cancelado#inicio")
        try:
            calendario.terminar_login(request.args["state"], request.url)
        except Exception as e:
            print("Login de Google fallo:", e)
            return redirect("/?google=error#inicio")
        return redirect("/?google=ok#inicio")
    return send_from_directory(APP_DIR, "index.html")


@app.get("/<path:ruta>")
def archivos(ruta):
    return send_from_directory(APP_DIR, ruta)


# ---------------------------------------------------------------
# API de la app
# ---------------------------------------------------------------
@app.post("/api/emparejar")
def emparejar():
    ip = request.remote_addr
    fallos, hasta = _intentos.get(ip, [0, 0])
    if time.time() < hasta:
        return jsonify(error="Demasiados intentos. Espera un minuto."), 429
    pin = (request.get_json(silent=True) or {}).get("pin", "")
    if not _igual(pin, CONFIG["pin"]):
        fallos += 1
        _intentos[ip] = [0, time.time() + 60] if fallos >= 5 else [fallos, 0]
        return jsonify(error="PIN incorrecto."), 401
    _intentos.pop(ip, None)
    resp = jsonify(ok=True)
    resp.set_cookie("wonder_pin", CONFIG["pin"], max_age=30 * 24 * 3600, httponly=True, samesite="Strict")
    return resp


@app.get("/api/estado")
def api_estado():
    ip = ip_local()
    with _candado:
        pico = dict(PICO)
    hace = None if pico["visto"] is None else int(time.time() - pico["visto"])
    wonder = leer_wonder()
    return jsonify(
        hub={
            "ip": ip,
            "puerto": PUERTO,
            "url": f"http://{ip}:{PUERTO}",
            "local": _es_local(),
            "pin": CONFIG["pin"] if _es_local() else None,
            "clave_pico": CONFIG["clave_pico"],
        },
        google=calendario.estado(),
        pico={
            "visto_hace_seg": hace,
            "en_linea": hace is not None and hace < 15 * 60,
            "ip": pico["ip"],
            "wonder_al_dia": pico["wonder_version"] == wonder["version"],
            "eventos": pico["eventos"],
            "bateria": pico["bateria"],
            "usb": pico["usb"],
            "red": pico["red"],
            "redes": pico["redes"],
        },
        pomodoro=leer_pomodoro(),
        logros=logros.resumen(),
        wonder=wonder,
        ia=grabaciones.herramientas(),
    )


@app.post("/api/google/login")
def google_login():
    if not _es_local():
        return _error("Inicia sesion con Google desde el computador donde corre Wonder Hub (http://localhost:%d)." % PUERTO, 409)
    try:
        return jsonify(url=calendario.url_de_login(f"http://localhost:{PUERTO}/"))
    except Exception as e:
        return _error(e, 409)


@app.post("/api/google/logout")
def google_logout():
    calendario.cerrar_sesion()
    return jsonify(ok=True)


@app.get("/api/eventos")
def api_eventos():
    try:
        dias = max(1, min(int(request.args.get("dias", DIAS_CALENDARIO)), 31))
        lista = calendario.eventos(dias, forzar=request.args.get("forzar") == "1")
    except calendario.SinLogin as e:
        return jsonify(error="login", mensaje=str(e)), 401
    except calendario.FaltanLibrerias as e:
        return _error(e, 409)
    except Exception as e:
        return _error(f"No se pudo leer Google Calendar: {e}", 502)
    return jsonify(eventos=lista, hora=datetime.now(calendario.TIMEZONE).strftime("%H:%M"),
                   cuenta=calendario.estado().get("cuenta"))


@app.post("/api/wonder")
def api_wonder():
    datos = request.get_json(silent=True) or {}
    if datos.get("emocion") not in pantallas.EMOCIONES:
        return _error("Emocion desconocida.")
    accesorios = [a for a in pantallas.ACCESORIOS if a in (datos.get("accesorios") or [])]
    with _candado:
        version = leer_wonder()["version"] + 1
        _escribir_json(WONDER_FILE, {"emocion": datos["emocion"], "accesorios": accesorios, "version": version})
    return jsonify(leer_wonder())


@app.post("/api/pomodoro")
def api_pomodoro():
    datos = request.get_json(silent=True) or {}
    nuevo = {}
    for k, (minimo, maximo) in (("estudio", (5, 120)), ("descanso", (1, 60)), ("sesiones", (1, 12))):
        try:
            v = int(datos.get(k))
        except (TypeError, ValueError):
            return _error("Revisa los minutos del pomodoro.")
        if not minimo <= v <= maximo:
            return _error(f"{k.capitalize()} debe estar entre {minimo} y {maximo}.")
        nuevo[k] = v
    with _candado:
        CONFIG["pomodoro"] = nuevo
        _escribir_json(CONFIG_FILE, CONFIG)
    return jsonify(leer_pomodoro())


@app.get("/api/wonder/pantalla.png")
def api_wonder_png():
    """Como se vera 'Mi Wonder' en la pantalla del llavero (160x128)."""
    w = leer_wonder()
    emocion = request.args.get("emocion", w["emocion"])
    accesorios = request.args.get("accesorios")
    accesorios = accesorios.split(",") if accesorios is not None else w["accesorios"]
    salida = io.BytesIO()
    pantallas.componer(emocion, accesorios).save(salida, "PNG")
    salida.seek(0)
    return send_file(salida, mimetype="image/png")


@app.get("/api/grabaciones")
def api_grabaciones():
    return jsonify(grabaciones=grabaciones.listar())


@app.post("/api/grabaciones")
def api_subir():
    nombre = urllib.parse.unquote(request.headers.get("X-Nombre", ""))
    try:
        reg = grabaciones.guardar_subida(nombre, request.stream)
    except ValueError as e:
        return _error(e)
    return jsonify(reg)


@app.get("/api/grabaciones/<ident>")
def api_grabacion(ident):
    reg = grabaciones.leer(ident)
    return jsonify(reg) if reg else _error("No existe esa grabacion.", 404)


@app.post("/api/grabaciones/<ident>/reprocesar")
def api_reprocesar(ident):
    try:
        grabaciones.reprocesar(ident)
    except ValueError as e:
        return _error(e)
    return jsonify(ok=True)


@app.post("/api/grabaciones/<ident>/google-doc")
def api_google_doc(ident):
    try:
        return jsonify(url=grabaciones.crear_google_doc(ident))
    except calendario.SinLogin as e:
        return jsonify(error="login", mensaje=str(e)), 401
    except Exception as e:
        return _error(e, 502)


@app.get("/api/grabaciones/<ident>/audio")
def api_audio(ident):
    reg = grabaciones.leer(ident)
    if not reg or not os.path.exists(grabaciones.ruta_audio(reg)):
        return _error("El audio ya no esta en la carpeta de clases.", 404)
    return send_file(grabaciones.ruta_audio(reg), conditional=True)


@app.get("/api/grabaciones/<ident>/word")
def api_word(ident):
    reg = grabaciones.leer(ident)
    if not reg or not reg.get("word"):
        return _error("Esa grabacion no tiene Word.", 404)
    return send_from_directory(grabaciones.CARPETA_RESULTADOS, reg["word"], as_attachment=True)


# ---------------------------------------------------------------
# API del llavero (cabecera X-Wonder-Key)
# ---------------------------------------------------------------
@app.get("/eventos")
def pico_eventos():
    """Lo que pide main.py: {"eventos": [{dia, fecha, hora, titulo}], "hora": "HH:MM"}."""
    try:
        datos = calendario.para_pico(DIAS_CALENDARIO, hechos=logros.ids_hechos())
    except (calendario.SinLogin, calendario.FaltanLibrerias):
        _pico_visto()
        return jsonify(error="login"), 503
    except Exception as e:
        _pico_visto()
        return _error(e, 502)
    datos["ahora"] = ahora_para_pico()
    r = logros.resumen()
    datos["logros"] = {"total": r["total"], "hoy": r["hoy"], "racha": r["racha"]}
    _pico_visto(eventos=len(datos["eventos"]))
    return Response(json.dumps(datos, ensure_ascii=True, separators=(",", ":")), mimetype="application/json")


@app.post("/pico/hecho")
def pico_hecho():
    """El llavero marca un evento como hecho: {"id": "...", "t": "2026-11-15T09:30"}."""
    d = request.get_json(silent=True, force=True) or {}
    try:
        r = logros.marcar(str(d.get("id", "")), d.get("t"))
    except logros.Rechazado as e:
        return jsonify(ok=False, motivo=str(e)), 409
    except (calendario.SinLogin, calendario.FaltanLibrerias):
        return jsonify(ok=False, motivo="Falta Google"), 503
    except Exception as e:
        return _error(e, 502)
    print(f"[{datetime.now():%H:%M:%S}] Hecho: {d.get('id')} (total {r['total']})")
    return jsonify(ok=True, total=r["total"], hoy=r["hoy"])


@app.get("/pico/estado")
def pico_estado():
    """Consulta ligera: que version de Wonder hay y que hora es."""
    w = leer_wonder()
    try:
        tiene = int(request.args.get("v", ""))
    except ValueError:
        tiene = None
    extra = {"wonder_version": tiene}
    a = request.args
    if a.get("bat", "").isdigit():
        extra["bateria"] = int(a["bat"])
    elif "bat" in a:
        extra["bateria"] = None
    if "usb" in a:
        extra["usb"] = a.get("usb") == "1"
    if "red" in a:
        extra["red"] = a.get("red") or None
    if "redes" in a:
        extra["redes"] = [r for r in a.get("redes", "").split("|") if r]
    _pico_visto(**extra)
    return jsonify(wonder=w["version"], emocion=w["emocion"],
                   hora=datetime.now(calendario.TIMEZONE).strftime("%H:%M"),
                   ahora=ahora_para_pico(), pomodoro=leer_pomodoro())


@app.get("/pico/wonder.raw")
def pico_wonder():
    """Pantalla 'Mi Wonder' lista para el Pico: 160x128 RGB565 (40960 bytes)."""
    w = leer_wonder()
    _pico_visto()
    resp = Response(pantallas.wonder_raw(w["emocion"], w["accesorios"]), mimetype="application/octet-stream")
    resp.headers["X-Wonder-Version"] = str(w["version"])
    return resp


@app.post("/pico/audio")
def pico_audio():
    """El llavero sube una grabacion por partes: ?nombre=clase_x.wav&pos=0 ... &fin=1"""
    try:
        pos = int(request.args.get("pos", "0"))
        r = grabaciones.recibir_trozo_pico(request.args.get("nombre", ""), pos,
                                           request.get_data(), request.args.get("fin") == "1")
    except ValueError as e:
        return _error(e)
    _pico_visto()
    return jsonify(r), (200 if r["ok"] else 409)


# ---------------------------------------------------------------
def _avisar_en_la_red():
    """Cada 2 s grita 'WONDER-HUB http://IP:PUERTO' a toda la red local.
    Asi el llavero encuentra el hub aunque el computador cambie de IP."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        try:
            ip = ip_local()
            mensaje = f"WONDER-HUB http://{ip}:{PUERTO}".encode()
            for destino in ("255.255.255.255", ip.rsplit(".", 1)[0] + ".255"):
                try:
                    s.sendto(mensaje, (destino, PUERTO_AVISO))
                except OSError:
                    pass
        except Exception:
            pass
        time.sleep(2)


def main():
    grabaciones.iniciar()
    threading.Thread(target=_avisar_en_la_red, daemon=True).start()
    ip = ip_local()
    print()
    print("  WONDER HUB")
    print("  ----------------------------------------------")
    print(f"  En este computador:   http://localhost:{PUERTO}")
    print(f"  Desde el celular:     http://{ip}:{PUERTO}    PIN: {CONFIG['pin']}")
    print(f"  Llavero (servidor):   http://{ip}:{PUERTO}    (la app se lo configura)")
    if not calendario.hay_credenciales():
        print("  ! Falta hub/credentials.json para el login de Google")
    if not os.environ.get("GEMINI_API_KEY"):
        print("  ! Falta GEMINI_API_KEY para resumir las grabaciones")
    print("  Ctrl+C para detener")
    print()
    app.run(host="0.0.0.0", port=PUERTO, threaded=True, debug=False)


if __name__ == "__main__":
    main()
