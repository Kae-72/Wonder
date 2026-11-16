# Wonder - Llavero (Pico 2 W, MicroPython)
#
# Inicio -> Menú (carrusel) -> Calendario · Pomodoro · Grabadora
# Arriba a la derecha, siempre (menos en el inicio): hora, WiFi y batería.
# En batería, sin tocar nada por APAGAR_MIN minutos y sin pomodoro: se duerme
# (pantalla apagada). Cualquier botón lo despierta; también una clase que empieza.
#
# Botones (los pines salen de pines.json, que crea prueba.py):
#   Inicio:      O = empezar,  IZQ / DER = ver "Mi Wonder",  mantener O = configurar
#   Menú:        IZQ / DER = cambiar app,  O = abrir,  mantener O = volver al inicio
#   Calendario:  IZQ / DER = elegir evento,  O = ¡Hecho! (tarea o clase cumplida),
#                mantener O = volver. Se actualiza solo.
#   Pomodoro:    O = empezar / pausar,  IZQ / DER = minutos (antes de empezar)
#                en pausa: IZQ = terminar.  Mantener O = volver (el pomodoro sigue)
#   Grabadora:   O = grabar / parar,  DER = subir grabaciones,  mantener O = volver
#
# Archivos en el Pico: los .raw y .spr de las pantallas, sonidos.py, red.py,
# bateria.py, grabadora.py, rapido.py, sdcard.py.
# config.json (redes WiFi + hub) lo escribe la app; NO hay que tocarlo a mano.

from machine import Pin, SPI
import framebuf
import struct
import time
import json
import os
import gc
import sys

import red
import bateria

try:
    import sonidos
except ImportError:
    sonidos = None

# ===================== AJUSTES =====================
APAGAR_MIN = 3             # minutos sin tocar nada (en batería) para dormirse
REFRESCO_SEG = 300          # cada cuánto se sincroniza con el hub (hora, calendario, Mi Wonder)
AVISAR_MIN_ANTES = 10       # aviso con sonido antes de cada evento del calendario
AP_NOMBRE = "Wonder-Setup"  # red que crea el llavero en modo configurar
AP_CLAVE = "wonder1234"
HORIZONTAL = 0x60           # si se ve de cabeza: 0xA0
FPS_INICIO = 3
LARGO_MS = 700              # cuánto mantener O para "volver"
POMODORO = {"estudio": 25, "descanso": 5, "sesiones": 4}   # la app puede cambiarlo

APPS = [("calendario", "Calendario"), ("pomodoro", "Pomodoro"), ("grabadora", "Grabadora")]
BURBUJA_CENTRO = (39, 17)
ICONO_SEL = (114, 62)
ICONO_IZQ = (75, 62)
ICONO_DER = (151, 62)
TEXTO_INICIO_Y = 9
# ===================================================

W, H = 160, 128
TAM_PANTALLA = W * H * 2
CLAVE_FB = 0x1FF8

# ---------------- Pantalla ----------------
spi = SPI(0, baudrate=20_000_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
cs = Pin(0, Pin.OUT, value=1)
dc = Pin(1, Pin.OUT, value=0)
rst = Pin(2, Pin.OUT, value=1)
bl = Pin(5, Pin.OUT, value=1)

lienzo = bytearray(TAM_PANTALLA)
fb = framebuf.FrameBuffer(lienzo, W, H, framebuf.RGB565)
BARRA = False               # True = se dibuja la barra de arriba al mostrar


def cmd(c, data=None):
    cs.value(0); dc.value(0)
    spi.write(bytes((c,)))
    if data:
        dc.value(1)
        spi.write(data)
    cs.value(1)


def init_pantalla():
    rst.value(0); time.sleep_ms(50)
    rst.value(1); time.sleep_ms(150)
    cmd(0x01); time.sleep_ms(150)
    cmd(0x11); time.sleep_ms(255)
    cmd(0xB1, b"\x01\x2C\x2D"); cmd(0xB2, b"\x01\x2C\x2D"); cmd(0xB3, b"\x01\x2C\x2D\x01\x2C\x2D")
    cmd(0xB4, b"\x07"); cmd(0xC0, b"\xA2\x02\x84"); cmd(0xC1, b"\xC5"); cmd(0xC2, b"\x0A\x00")
    cmd(0xC3, b"\x8A\x2A"); cmd(0xC4, b"\x8A\xEE"); cmd(0xC5, b"\x0E")
    cmd(0x20); cmd(0x3A, b"\x05"); cmd(0x36, bytes((HORIZONTAL,)))
    cmd(0x13); cmd(0x29); time.sleep_ms(100)


def mostrar():
    if BARRA:
        dibujar_barra()
    cmd(0x2A, bytes((0, 0, 0, W - 1)))
    cmd(0x2B, bytes((0, 0, 0, H - 1)))
    cmd(0x2C)
    cs.value(0); dc.value(1)
    spi.write(lienzo)
    cs.value(1)


def color(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


NAVY = color(28, 51, 80)
AZUL = color(104, 178, 255)
CLARO = color(220, 234, 255)
BLANCO = color(255, 255, 255)
GRIS = color(110, 140, 170)
ROJO = color(235, 70, 70)
VERDE = color(80, 200, 110)
AMARILLO = color(255, 210, 60)


def texto_borde(t, x, y, c=BLANCO, borde=NAVY):
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        fb.text(t, x + dx, y + dy, borde)
    fb.text(t, x, y, c)


def texto_centro(t, y, c=NAVY):
    fb.text(t, (W - len(t) * 8) // 2, y, c)


def panel(x, y, w, h):
    fb.fill_rect(x, y, w, h, CLARO)
    fb.rect(x, y, w, h, NAVY)
    for px, py in ((x, y), (x + w - 1, y), (x, y + h - 1), (x + w - 1, y + h - 1)):
        fb.pixel(px, py, AZUL)


# ---- Letra pixelada pequeña (3x5) para la hora y los números grandes ----
LETRA = {
    "0": (7, 5, 5, 5, 7), "1": (2, 6, 2, 2, 7), "2": (7, 1, 7, 4, 7), "3": (7, 1, 7, 1, 7),
    "4": (5, 5, 7, 1, 1), "5": (7, 4, 7, 1, 7), "6": (7, 4, 7, 5, 7), "7": (7, 1, 1, 1, 1),
    "8": (7, 5, 7, 5, 7), "9": (7, 5, 7, 1, 7), ":": (0, 2, 0, 2, 0), "-": (0, 0, 7, 0, 0),
    "%": (5, 1, 2, 4, 5), "/": (1, 1, 2, 4, 4), " ": (0, 0, 0, 0, 0),
}


def ancho_chico(t, e=1):
    return len(t) * 4 * e - e


def chico(t, x, y, c=BLANCO, borde=NAVY, e=1):
    """Escribe con la letra 3x5. e = escala. Con borde para leerse sobre cualquier fondo."""
    pasadas = (0, 1) if borde is not None else (1,)
    for pasada in pasadas:
        cx = x
        for ch in t:
            filas = LETRA.get(ch, LETRA[" "])
            for fy in range(5):
                bits = filas[fy]
                for fx in range(3):
                    if bits & (4 >> fx):
                        if pasada:
                            fb.fill_rect(cx + fx * e, y + fy * e, e, e, c)
                        else:
                            fb.fill_rect(cx + fx * e - 1, y + fy * e - 1, e + 2, e + 2, borde)
            cx += 4 * e


# ---------------- Archivos ----------------
def existe(nombre):
    try:
        os.stat(nombre)
        return True
    except OSError:
        return False


def cargar_spr(nombre):
    if not existe(nombre):
        print("Falta", nombre)
        return None
    with open(nombre, "rb") as f:
        w, h = struct.unpack(">HH", f.read(4))
        datos = bytearray(f.read())
    return framebuf.FrameBuffer(datos, w, h, framebuf.RGB565), w, h


def pegar(spr, cx, cy, transparente=True):
    if spr is None:
        return
    s, w, h = spr
    if transparente:
        fb.blit(s, cx - w // 2, cy - h // 2, CLAVE_FB)
    else:
        fb.blit(s, cx - w // 2, cy - h // 2)


def cargar_pantalla(nombre, indice=0):
    with open(nombre, "rb") as f:
        f.seek(indice * TAM_PANTALLA)
        f.readinto(lienzo)


_fondo = {"nombre": None, "datos": bytearray(TAM_PANTALLA)}   # reservado al arrancar


def poner_fondo(nombre, respaldo=AZUL):
    """Copia un fondo .raw al lienzo (queda guardado en memoria para ir rápido).
    Si no existe el archivo, pinta un color (placeholder)."""
    if _fondo["nombre"] != nombre:
        if existe(nombre):
            with open(nombre, "rb") as f:
                f.readinto(_fondo["datos"])
            _fondo["nombre"] = nombre
        else:
            fb.fill(respaldo)
            return
    lienzo[:] = _fondo["datos"]


# ---------------- Botones ----------------
PINES = {"izq": 14, "o": 15, "der": 16}   # izquierdo GP14, centro GP15, derecho GP16
try:
    with open("pines.json") as f:
        PINES.update({k: v for k, v in json.load(f).items() if v is not None and k in PINES})
except (OSError, ValueError):
    pass
print("Pines:", PINES)


ACT = {"t": time.ticks_ms()}     # última vez que se tocó un botón


class Boton:
    def __init__(self, n):
        self.p = Pin(n, Pin.IN, Pin.PULL_UP)
        self.antes = 1
        self.t0 = 0
        self.largo_hecho = False

    def leer(self):
        """None, 'presion' (al bajar), 'corto' (al soltar rápido) o 'largo' (mantenido)."""
        v = self.p.value()
        ahora = time.ticks_ms()
        ev = None
        if v == 0 and self.antes == 1:
            self.t0 = ahora
            self.largo_hecho = False
            ev = "presion"
        elif v == 0 and not self.largo_hecho and time.ticks_diff(ahora, self.t0) >= LARGO_MS:
            self.largo_hecho = True
            ev = "largo"
        elif v == 1 and self.antes == 0 and not self.largo_hecho and time.ticks_diff(ahora, self.t0) > 30:
            ev = "corto"
        self.antes = v
        if ev:
            ACT["t"] = ahora
        return ev


b_izq = Boton(PINES["izq"])
b_o = Boton(PINES["o"])
b_der = Boton(PINES["der"])


def esperar_soltar():
    while b_o.p.value() == 0 or b_izq.p.value() == 0 or b_der.p.value() == 0:
        time.sleep_ms(10)
    for b in (b_izq, b_o, b_der):
        b.antes = 1


def sonar(nombre, *args):
    if sonidos:
        try:
            getattr(sonidos, nombre)(*args)
        except Exception as e:
            print("Sonido:", e)


# ======================================================================
#  BARRA DE ARRIBA (hora · pomodoro · WiFi · batería) y tareas de fondo
# ======================================================================
BAT = {"pct": None, "usb": False}
T = {"red": 0, "bat": None, "sync": None, "ev": 0, "sync_ok": True}
OCUPADO = False              # True mientras graba: no sincroniza (no interrumpir)
_barra_dibujada = None


def hora_ok():
    return time.localtime()[0] >= 2025


def texto_hora():
    t = time.localtime()
    return "%02d:%02d" % (t[3], t[4]) if hora_ok() else "--:--"


def firma_barra():
    return (texto_hora(), BAT["pct"], BAT["usb"], red.conectado(),
            pomo_estado() if pomo_estado() != "parado" else None,
            pomo_resta_s() // 60 if pomo_estado() != "parado" else None)


def barra_cambio():
    return BARRA and firma_barra() != _barra_dibujada


def dibujar_barra():
    global _barra_dibujada
    _barra_dibujada = firma_barra()
    x = W - 16
    # batería: cuerpo 12x7 + punta
    fb.fill_rect(x - 1, 1, 16, 9, NAVY)
    fb.rect(x, 2, 12, 7, BLANCO)
    fb.fill_rect(x + 12, 4, 2, 3, BLANCO)
    if BAT["usb"]:
        for px, py in ((6, 3), (5, 4), (4, 5), (5, 5), (6, 5), (7, 5), (6, 6), (5, 7)):
            fb.pixel(x + px, py, AMARILLO)                 # rayito = cargando / USB
    elif BAT["pct"] is not None:
        p = BAT["pct"]
        c = VERDE if p > 50 else AMARILLO if p > 20 else ROJO
        fb.fill_rect(x + 2, 4, max(1, 8 * p // 100), 3, c)
    else:
        fb.pixel(x + 5, 4, BLANCO); fb.pixel(x + 6, 6, BLANCO)
    # hora
    h = texto_hora()
    x -= ancho_chico(h) + 5
    chico(h, x, 3)
    # WiFi: tres rayitas
    if red.conectado():
        x -= 8
        fb.fill_rect(x - 1, 2, 7, 8, NAVY)
        fb.fill_rect(x, 7, 1, 2, BLANCO)
        fb.fill_rect(x + 2, 5, 1, 4, BLANCO)
        fb.fill_rect(x + 4, 3, 1, 6, BLANCO)
    # pomodoro corriendo: punto rojo + minutos
    if pomo_estado() != "parado":
        m = "%d" % (pomo_resta_s() // 60)
        x -= ancho_chico(m) + 8
        fb.fill_rect(x - 1, 2, 5, 7, NAVY)
        fb.fill_rect(x, 4, 3, 3, ROJO if POMO["fase"] == "estudio" else VERDE)
        chico(m, x + 5, 3)


def momento():
    """'dia' (6-17 h), 'tarde' (17-19 h) o 'noche' (19-6 h). Sin hora: 'dia'."""
    if not hora_ok():
        return "dia"
    h = time.localtime()[3]
    return "dia" if 6 <= h < 17 else "tarde" if 17 <= h < 19 else "noche"


def fondo_del_momento(base):
    """fondo_<base>_<momento>.raw si existe; si no, el fondo de siempre."""
    n = "fondo_%s_%s.raw" % (base, momento())
    return n if existe(n) else "fondo_%s.raw" % base


def leer_bateria():
    """Lee la batería. Con WiFi prendido, lo apaga un instante (el pin de la
    batería lo comparte el chip WiFi) y luego se reconecta solo."""
    pct, usb, v, apago = bateria.leer(red.wlan)
    if apago:
        red.reconectar()
    if v:
        BAT["pct"], BAT["usb"] = pct, usb


def tick():
    """Llamar en cada vuelta de cualquier pantalla. Devuelve True si hay que redibujar."""
    ahora = time.ticks_ms()
    redibujar = False
    if time.ticks_diff(ahora, T["red"]) > 1000:
        T["red"] = ahora
        red.mantener()
    if not OCUPADO and (T["bat"] is None or time.ticks_diff(ahora, T["bat"]) > 300000):
        T["bat"] = ahora                         # cada 5 min (apaga el WiFi un instante)
        leer_bateria()
    if pomo_tick():
        redibujar = True
    espera = REFRESCO_SEG * 1000 * (1 if T["sync_ok"] else 3)   # si falló, reintenta más tarde
    if red.conectado() and not OCUPADO and (red.recien_conectado or T["sync"] is None
                                            or time.ticks_diff(ahora, T["sync"]) > espera):
        red.recien_conectado = False
        T["sync"] = ahora
        gc.collect()
        T["sync_ok"] = sincronizar()
        gc.collect()
        redibujar = True
    if (not BAT["usb"] and BAT["pct"] is not None and pomo_estado() == "parado" and not OCUPADO
            and time.ticks_diff(ahora, ACT["t"]) > APAGAR_MIN * 60000):
        dormir()
        return True
    if not OCUPADO and time.ticks_diff(ahora, T["ev"]) > 30000:
        T["ev"] = ahora
        if revisar_eventos():
            redibujar = True
    return redibujar or barra_cambio()


# ---------------- Sincronizar con Wonder Hub ----------------
datos_cal = None
t_datos = 0
try:
    with open("cal.json") as f:          # el último calendario, para verlo sin WiFi
        datos_cal = json.load(f)
except (OSError, ValueError):
    pass


def version_wonder():
    try:
        with open("wonder.ver") as f:
            return f.read().strip()
    except OSError:
        return ""


def sincronizar():
    """Hora, ajustes del pomodoro, Mi Wonder y calendario. Le cuenta al hub
    cómo está el llavero (batería y redes) para que la app lo muestre."""
    global datos_cal, t_datos
    tengo = version_wonder()
    q = "/pico/estado?v=%s&bat=%s&usb=%d&red=%s&redes=%s" % (
        tengo, "" if BAT["pct"] is None else BAT["pct"], 1 if BAT["usb"] else 0,
        red.citar(red.red_actual or ""), red.citar("|".join(red.nombres())))
    codigo, d = red.pedir(q, timeout=3)
    if codigo != 200 or not d:
        print("Sin hub (", codigo, ")")
        if not hora_ok():
            red.hora_de_internet()
        return False
    if d.get("ahora"):
        red.poner_hora(d["ahora"])
    p = d.get("pomodoro")
    if p and pomo_estado() == "parado":
        for k in POMODORO:
            if isinstance(p.get(k), int) and p[k] > 0:
                POMODORO[k] = p[k]
        guardar_pomodoro()
    nueva = str(d.get("wonder", ""))
    if nueva and (nueva != tengo or not existe("wonder.raw")):
        try:
            if red.descargar("/pico/wonder.raw", "wonder.tmp", TAM_PANTALLA):
                try:
                    os.remove("wonder.raw")
                except OSError:
                    pass
                os.rename("wonder.tmp", "wonder.raw")
                with open("wonder.ver", "w") as f:
                    f.write(nueva)
                print("Mi Wonder actualizado:", nueva)
        except Exception as e:
            print("Mi Wonder:", e)
    enviar_hechos()
    codigo, d = red.pedir("/eventos", timeout=6, buscar=False)
    if codigo == 200 and d:
        if d.get("logros"):
            LOGROS.update(d["logros"])
        datos_cal = d
        t_datos = time.ticks_ms()
        if d.get("ahora"):
            red.poner_hora(d["ahora"])
        try:
            with open("cal.json", "w") as f:
                json.dump(d, f)
        except OSError:
            pass
    return True


# ======================================================================
#  ¡HECHO!  (tarea o clase cumplida)
#  Reglas anti-trampa: aquí solo se revisa lo básico (que ya haya empezado y
#  que no esté repetido). El hub lo confirma contra Google Calendar: que el
#  evento exista, que se haya creado antes de empezar, plazo de 12 h después
#  de terminar y máximo 8 por día. Sin WiFi, queda pendiente y se confirma luego.
# ======================================================================
LOGROS = {"total": 0, "hoy": 0}
ARCH_HECHOS = "hechos.json"


def _leer_hechos():
    try:
        with open(ARCH_HECHOS) as f:
            h = json.load(f)
        return {"pendientes": h.get("pendientes", []), "marcados": h.get("marcados", []),
                "logros": h.get("logros", {})}
    except (OSError, ValueError):
        return {"pendientes": [], "marcados": [], "logros": {}}


HECHOS = _leer_hechos()
LOGROS.update(HECHOS["logros"])


def _guardar_hechos():
    HECHOS["marcados"] = HECHOS["marcados"][-200:]
    HECHOS["logros"] = LOGROS
    try:
        with open(ARCH_HECHOS, "w") as f:
            json.dump(HECHOS, f)
    except OSError:
        pass


def ahora_iso():
    t = time.localtime()
    return "%04d-%02d-%02dT%02d:%02d" % t[:5]


def es_hecho(ev):
    return bool(ev.get("hecho")) or ev.get("id") in HECHOS["marcados"]


def enviar_hechos():
    """Manda al hub los ¡Hecho! pendientes. Devuelve el motivo si el hub rechazó alguno."""
    motivo = None
    for p in list(HECHOS["pendientes"]):
        codigo, d = red.enviar("/pico/hecho", p)
        d = d or {}
        if codigo == 200 or (codigo == 409 and d.get("motivo") == "Ya estaba hecho"):
            HECHOS["pendientes"].remove(p)
            if "total" in d:
                LOGROS["total"], LOGROS["hoy"] = d["total"], d.get("hoy", LOGROS["hoy"])
        elif codigo == 409:
            HECHOS["pendientes"].remove(p)
            if p["id"] in HECHOS["marcados"]:
                HECHOS["marcados"].remove(p["id"])
            motivo = d.get("motivo", "No cuenta")
        else:
            break                                   # sin hub: se intenta en la próxima sincronización
    _guardar_hechos()
    return motivo


def marcar_hecho(ev):
    titulo = ev.get("titulo", "")[:18]
    motivo = None
    if not ev.get("id"):
        motivo = "Actualiza primero"
    elif es_hecho(ev):
        motivo = "Ya estaba hecho"
    elif not hora_ok():
        motivo = "Falta la hora"
    elif ev.get("ini") and ahora_iso() < ev["ini"]:
        motivo = "Aun no empieza"
    if motivo:
        sonar("error")
        mensaje(motivo, titulo)
        time.sleep_ms(1500)
        return
    HECHOS["marcados"].append(ev["id"])
    HECHOS["pendientes"].append({"id": ev["id"], "t": ahora_iso()})
    LOGROS["hoy"] += 1
    LOGROS["total"] += 1
    _guardar_hechos()
    sonar("hecho")
    mensaje("Hecho!", titulo)
    if red.conectado():
        motivo = enviar_hechos()
        if motivo:
            LOGROS["hoy"] = max(0, LOGROS["hoy"] - 1)
            LOGROS["total"] = max(0, LOGROS["total"] - 1)
            _guardar_hechos()
            time.sleep_ms(700)
            sonar("error")
            mensaje("No cuenta:", motivo)
        else:
            mensaje("Hecho! (%d hoy)" % LOGROS["hoy"], titulo)
    else:
        mensaje("Hecho!", "Se confirma luego")
    time.sleep_ms(1500)


# ======================================================================
#  DORMIR (ahorro de batería)
# ======================================================================
def dormir():
    """Apaga pantalla, WiFi y parlante. Despierta con cualquier botón o
    cuando una clase está por empezar."""
    import machine
    print("Durmiendo...")
    leer_bateria()
    # despedida: Wonder descansando según la hora + una melodía corta
    global BARRA
    antes = BARRA
    BARRA = False
    poner_fondo(fondo_del_momento("descanso"), AZUL)
    mostrar()
    BARRA = antes
    sonar("melodia_dormir", momento())
    t0 = time.ticks_ms()
    while sonidos and sonidos.sonando() and time.ticks_diff(time.ticks_ms(), t0) < 2500:
        time.sleep_ms(20)
    time.sleep_ms(800)
    if "grabadora" in sys.modules:
        sys.modules["grabadora"].soltar_mic()
    bl.value(0)
    cmd(0x28)                                   # pantalla apagada
    cmd(0x10)                                   # pantalla en reposo
    if sonidos:
        sonidos.apagar()
    red.apagar_wifi()
    gc.collect()
    por_evento = False
    t_revision = time.ticks_ms()
    botones = (b_izq.p, b_o.p, b_der.p)
    while True:
        if any(p.value() == 0 for p in botones):
            break
        if time.ticks_diff(time.ticks_ms(), t_revision) > 30000:
            t_revision = time.ticks_ms()
            if proximo_evento():
                por_evento = True
                break
        try:
            machine.lightsleep(150)             # el Pico casi no gasta mientras duerme
        except Exception:
            time.sleep_ms(150)
    cmd(0x11)
    time.sleep_ms(120)
    cmd(0x29)
    bl.value(1)
    if sonidos:
        sonidos.reanudar()
    print("Despierto")
    esperar_soltar()
    ACT["t"] = time.ticks_ms()
    T["red"] = 0
    T["bat"] = None
    if por_evento:
        revisar_eventos()
    else:
        sonar("despertar")


# ---------------- Avisos de eventos ----------------
_avisados = set()


def proximo_evento():
    """(evento, minutos_que_faltan) si algo empieza pronto y no se ha avisado."""
    if not datos_cal or not hora_ok():
        return None
    t = time.localtime()
    hoy = "%02d/%02d" % (t[2], t[1])
    ahora_min = t[3] * 60 + t[4]
    for ev in datos_cal.get("eventos", []):
        h = ev.get("hora", "")
        if ev.get("fecha") != hoy or len(h) != 5 or h[2] != ":":
            continue
        try:
            falta = int(h[:2]) * 60 + int(h[3:]) - ahora_min
        except ValueError:
            continue
        clave = hoy + h + ev.get("titulo", "")
        if 0 <= falta <= AVISAR_MIN_ANTES and clave not in _avisados:
            return ev, falta, clave
    return None


def revisar_eventos():
    """Si una clase empieza en los próximos minutos: sonido + aviso en pantalla."""
    p = proximo_evento()
    if not p:
        return False
    ev, falta, clave = p
    _avisados.add(clave)
    sonar("aviso")
    mensaje("En %d min:" % falta if falta else "Empieza ya:", ev.get("titulo", "")[:18])
    fin = time.ticks_add(time.ticks_ms(), 6000)
    while time.ticks_diff(fin, time.ticks_ms()) > 0:
        if "presion" in (b_o.leer(), b_izq.leer(), b_der.leer()):
            break
        time.sleep_ms(20)
    esperar_soltar()
    ACT["t"] = time.ticks_ms()
    return True


def mensaje(l1, l2=""):
    fb.fill(AZUL)
    panel(6, 44, W - 12, 40)
    texto_centro(l1[:18], 54, NAVY)
    texto_centro(l2[:18], 68, GRIS)
    mostrar()


# ======================================================================
#  POMODORO (sigue corriendo aunque salgas al menú)
# ======================================================================
POMO = {"estado": "parado", "fase": "estudio", "sesion": 1, "fin": 0, "resta": 0}
try:
    with open("pomodoro.json") as f:
        POMODORO.update(json.load(f))
except (OSError, ValueError):
    pass


def guardar_pomodoro():
    try:
        with open("pomodoro.json", "w") as f:
            json.dump(POMODORO, f)
    except OSError:
        pass


def pomo_estado():
    return POMO["estado"]


def pomo_resta_s():
    if POMO["estado"] == "corriendo":
        return max(0, time.ticks_diff(POMO["fin"], time.ticks_ms())) // 1000
    if POMO["estado"] == "pausa":
        return POMO["resta"] // 1000
    return POMODORO["estudio"] * 60


def pomo_empezar():
    POMO.update(estado="corriendo", fase="estudio", sesion=1,
                fin=time.ticks_add(time.ticks_ms(), POMODORO["estudio"] * 60000))


def pomo_pausa():
    if POMO["estado"] == "corriendo":
        POMO["resta"] = max(0, time.ticks_diff(POMO["fin"], time.ticks_ms()))
        POMO["estado"] = "pausa"
    elif POMO["estado"] == "pausa":
        POMO["fin"] = time.ticks_add(time.ticks_ms(), POMO["resta"])
        POMO["estado"] = "corriendo"


def pomo_terminar():
    POMO.update(estado="parado", fase="estudio", sesion=1)


def pomo_tick():
    """Cambia de fase cuando se acaba el tiempo. True si cambió algo."""
    if POMO["estado"] != "corriendo" or time.ticks_diff(POMO["fin"], time.ticks_ms()) > 0:
        return False
    ahora = time.ticks_ms()
    if POMO["fase"] == "estudio":
        if POMO["sesion"] >= POMODORO["sesiones"]:
            pomo_terminar()
            sonar("listo")
            print("Pomodoro terminado")
        else:
            POMO.update(fase="descanso", fin=time.ticks_add(ahora, POMODORO["descanso"] * 60000))
            sonar("aviso")
    else:
        POMO.update(fase="estudio", sesion=POMO["sesion"] + 1,
                    fin=time.ticks_add(ahora, POMODORO["estudio"] * 60000))
        sonar("aviso")
    return True


def dibujar_pomodoro():
    est = POMO["estado"]
    descanso = est != "parado" and POMO["fase"] == "descanso"
    poner_fondo(fondo_del_momento("descanso" if descanso else "pomodoro"),
                VERDE if descanso else CLARO)
    # ayuda arriba a la izquierda
    if est == "parado":
        texto_borde("O empezar", 3, 3)
        texto_borde("<> minutos", 3, 14)
    elif est == "corriendo":
        texto_borde("O pausa", 3, 3)
    else:
        texto_borde("O seguir", 3, 3)
        texto_borde("IZQ terminar", 3, 14)
    # panel con el tiempo
    x, y, w, h = 3, 78, 74, 46
    panel(x, y, w, h)
    if est == "parado":
        titulo = "%d / %d" % (POMODORO["estudio"], POMODORO["descanso"])
    elif est == "pausa":
        titulo = "PAUSA"
    else:
        titulo = "DESCANSO" if descanso else "ESTUDIO"
    fb.text(titulo, x + (w - len(titulo) * 8) // 2, y + 4, ROJO if est == "pausa" else NAVY)
    s = pomo_resta_s()
    t = "%02d:%02d" % (s // 60, s % 60)
    chico(t, x + (w - ancho_chico(t, 3)) // 2, y + 15, NAVY, None, 3)
    n = POMODORO["sesiones"]
    x0 = x + (w - (n * 8 - 3)) // 2
    for i in range(n):
        hecho = i < POMO["sesion"] - 1 or (i == POMO["sesion"] - 1 and descanso)
        actual = est != "parado" and i == POMO["sesion"] - 1
        if hecho:
            fb.fill_rect(x0 + i * 8, y + 36, 5, 5, ROJO)
        else:
            fb.rect(x0 + i * 8, y + 36, 5, 5, ROJO if actual else GRIS)
    mostrar()


def pantalla_pomodoro():
    dibujar_pomodoro()
    ultimo_s = pomo_resta_s()
    while True:
        e_izq, e_der, e_o = b_izq.leer(), b_der.leer(), b_o.leer()
        est = POMO["estado"]
        cambio = False
        if e_o == "largo":
            sonar("volver")
            esperar_soltar()
            return "menu"
        if e_o == "corto":
            if est == "parado":
                pomo_empezar()
                sonar("seleccionar")
            else:
                pomo_pausa()
                sonar("tic", 3 if POMO["estado"] == "pausa" else 7)
            cambio = True
        if est == "parado" and "presion" in (e_izq, e_der):
            paso = 5 if e_der == "presion" else -5
            POMODORO["estudio"] = max(5, min(90, POMODORO["estudio"] + paso))
            POMODORO["descanso"] = max(1, POMODORO["estudio"] // 5)
            guardar_pomodoro()
            sonar("mover", 1 if paso > 0 else -1, POMODORO["estudio"] // 5)
            cambio = True
        if est == "pausa" and e_izq == "presion":
            pomo_terminar()
            sonar("volver")
            cambio = True
        if tick():
            cambio = True
        s = pomo_resta_s()
        if s != ultimo_s:
            ultimo_s = s
            cambio = True
        if cambio:
            dibujar_pomodoro()
        time.sleep_ms(15)


# ======================================================================
#  INICIO
# ======================================================================
def pantalla_inicio():
    global BARRA
    BARRA = False
    n_frames = os.stat("inicio.raw")[6] // TAM_PANTALLA if existe("inicio.raw") else 0
    texto = cargar_spr("texto_inicio.spr")
    frame = 0
    t_frame = time.ticks_ms()
    t_parpadeo = time.ticks_ms()
    visible = True
    redibujar = True
    mi_wonder = False
    while True:
        ahora = time.ticks_ms()
        if not mi_wonder and n_frames > 1 and time.ticks_diff(ahora, t_frame) >= 1000 // FPS_INICIO:
            frame = (frame + 1) % n_frames
            t_frame = ahora
            redibujar = True
        if time.ticks_diff(ahora, t_parpadeo) >= (700 if visible else 400):
            visible = not visible
            t_parpadeo = ahora
            redibujar = True
        if redibujar:
            if mi_wonder:
                cargar_pantalla("wonder.raw")
            elif n_frames:
                cargar_pantalla("inicio.raw", frame)
            else:
                fb.fill(AZUL)
                texto_centro("WONDER", 50, BLANCO)
            if visible:
                if texto:
                    pegar(texto, W // 2, TEXTO_INICIO_Y)
                else:
                    texto_borde("Pulsa O", (W - 56) // 2, TEXTO_INICIO_Y - 4)
            mostrar()
            redibujar = False
        e_o = b_o.leer()
        if e_o == "corto":
            sonar("entrar")
            esperar_soltar()
            BARRA = True
            return "menu"
        if e_o == "largo":
            sonar("especial")
            esperar_soltar()
            BARRA = True
            return "configurar"
        e_izq, e_der = b_izq.leer(), b_der.leer()
        if "presion" in (e_izq, e_der):
            if existe("wonder.raw"):
                mi_wonder = not mi_wonder
                redibujar = True
                sonar("mover", 1 if e_der == "presion" else -1, 4 if mi_wonder else 2)
            else:
                sonar("tic", 0)
        tick()
        time.sleep_ms(15)


# ======================================================================
#  MENÚ
# ======================================================================
fondo_menu = bytearray(TAM_PANTALLA)     # reservado al arrancar (antes de que la RAM se fragmente)
_menu_listo = False
iconos = {}
minis = {}
nombres = {}
app_actual = 0


def cargar_menu():
    global _menu_listo
    if not _menu_listo:
        _menu_listo = True
        if existe("fondo_menu.raw"):
            with open("fondo_menu.raw", "rb") as f:
                f.readinto(fondo_menu)
        for app, _ in APPS:
            iconos[app] = cargar_spr("icono_%s.spr" % app)
            minis[app] = cargar_spr("icono_%s_mini.spr" % app)
            nombres[app] = cargar_spr("nombre_%s.spr" % app)


def dibujar_menu(i, dy=0):
    lienzo[:] = fondo_menu
    n = len(APPS)
    pegar(minis[APPS[(i - 1) % n][0]], ICONO_IZQ[0], ICONO_IZQ[1])
    pegar(minis[APPS[(i + 1) % n][0]], ICONO_DER[0], ICONO_DER[1])
    app, texto = APPS[i]
    if iconos[app]:
        s, w, h = iconos[app]
        fb.blit(s, ICONO_SEL[0] - w // 2, ICONO_SEL[1] - h // 2 + dy, CLAVE_FB)
    else:
        fb.fill_rect(ICONO_SEL[0] - 20, ICONO_SEL[1] - 20 + dy, 40, 40, GRIS)
    if nombres[app]:
        pegar(nombres[app], BURBUJA_CENTRO[0], BURBUJA_CENTRO[1], transparente=False)
    else:
        fb.text(texto[:8], BURBUJA_CENTRO[0] - len(texto[:8]) * 4, BURBUJA_CENTRO[1] - 4, NAVY)
    mostrar()


def pantalla_menu():
    global app_actual
    cargar_menu()
    dibujar_menu(app_actual)
    while True:
        e_izq, e_der, e_o = b_izq.leer(), b_der.leer(), b_o.leer()
        paso = -1 if e_izq == "presion" else 1 if e_der == "presion" else 0
        if paso:
            app_actual = (app_actual + paso) % len(APPS)
            sonar("mover", paso, app_actual * 2)
            for dy in (-5, -2, 0):
                dibujar_menu(app_actual, dy)
        if e_o == "corto":
            sonar("seleccionar")
            esperar_soltar()
            return APPS[app_actual][0]
        if e_o == "largo":
            sonar("volver")
            esperar_soltar()
            return "inicio"
        if tick():
            dibujar_menu(app_actual)
        time.sleep_ms(15)


# ======================================================================
#  CALENDARIO
# ======================================================================
POR_PAGINA = 5


def recortar(t, n):
    return t if len(t) <= n else t[:n - 1] + "~"


def esperando_wifi(nombre):
    mensaje("Buscando WiFi...", nombre)


def actualizar_calendario():
    if not red.configurado():
        mensaje("Sin redes WiFi", "Manten O en inicio")
        sonar("error")
        time.sleep(2)
        return
    if not red.conectar_ya(esperando_wifi):
        mensaje("Sin WiFi", "Comparte internet")
        sonar("error")
        time.sleep(2)
        return
    mensaje("Actualizando...", red.red_actual or "")
    if sincronizar():
        T["sync"] = time.ticks_ms()
        sonar("listo")
    else:
        mensaje("Sin Wonder Hub", "Abrelo en el PC")
        sonar("error")
        time.sleep(2)


def ya_termino(ev):
    return hora_ok() and ev.get("fin") and ahora_iso() >= ev["fin"]


def primer_pendiente(eventos):
    for k, ev in enumerate(eventos):
        if not ya_termino(ev):
            return k
    return max(0, len(eventos) - 1)


def chulo(x, y, c):
    """Pequeño visto bueno (check) de 7x6."""
    for px, py in ((0, 3), (1, 4), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (1, 3), (2, 4), (5, 1)):
        fb.pixel(x + px, y + py, c)


def dibujar_calendario(sel):
    datos = datos_cal or {"eventos": []}
    eventos = datos.get("eventos", [])
    sel = max(0, min(sel, len(eventos) - 1))
    pagina = sel // POR_PAGINA
    paginas = max(1, (len(eventos) + POR_PAGINA - 1) // POR_PAGINA)
    poner_fondo("fondo_calendario.raw")
    fb.fill_rect(4, 16, W - 8, H - 29, CLARO)
    for x, y in ((4, 16), (W - 5, 16), (4, H - 14), (W - 5, H - 14)):
        fb.pixel(x, y, AZUL)
    fb.fill_rect(0, 0, W, 13, NAVY)
    fb.text("CALENDARIO", 3, 3, BLANCO)
    if datos_cal is None:
        texto_centro("Sin datos", 56, NAVY)
        texto_centro("Manten DER", 70, GRIS)
    elif not eventos:
        texto_centro("Sin eventos esta", 56, NAVY)
        texto_centro("semana :)", 68, NAVY)
    else:
        y = 18
        for k in range(pagina * POR_PAGINA, min(len(eventos), (pagina + 1) * POR_PAGINA)):
            ev = eventos[k]
            elegido = k == sel
            hecho = es_hecho(ev)
            if elegido:
                fb.fill_rect(5, y - 1, W - 10, 19, AZUL)
            pasado = ya_termino(ev)
            c1 = BLANCO if elegido else GRIS
            c2 = BLANCO if elegido else (GRIS if pasado and not hecho else NAVY)
            fb.text("%s %s %s" % (ev["dia"], ev["fecha"], ev["hora"]), 7, y, c1)
            fb.text(recortar(ev["titulo"], 16 if hecho else 18), 7, y + 9, c2)
            if hecho:
                chulo(W - 16, y + 9, BLANCO if elegido else VERDE)
            y += 19
    if paginas > 1:
        fb.text("%d/%d" % (pagina + 1, paginas), W - 26, H - 10, CLARO)
    fb.text("O Hecho! <O sale", 2, H - 10, CLARO)
    mostrar()
    return sel


def pantalla_calendario():
    if datos_cal is None or time.ticks_diff(time.ticks_ms(), t_datos) > REFRESCO_SEG * 1000:
        if red.conectado() or datos_cal is None:
            actualizar_calendario()
    eventos = (datos_cal or {}).get("eventos", [])
    sel = dibujar_calendario(primer_pendiente(eventos))
    while True:
        e_izq, e_der, e_o = b_izq.leer(), b_der.leer(), b_o.leer()
        n = len((datos_cal or {}).get("eventos", []))
        if e_der == "presion" and n:
            sel = dibujar_calendario((sel + 1) % n)
            sonar("tic", sel + 5)
        if e_izq == "presion" and n:
            sel = dibujar_calendario((sel - 1) % n)
            sonar("tic", sel + 5)
        if e_der == "largo":                            # mantener DER = actualizar ya
            sonar("seleccionar")
            actualizar_calendario()
            esperar_soltar()
            sel = dibujar_calendario(sel)
        if e_o == "corto" and n:
            marcar_hecho(datos_cal["eventos"][sel])
            sel = dibujar_calendario(sel)
        if e_o == "largo":
            sonar("volver")
            esperar_soltar()
            return "menu"
        if tick():
            sel = dibujar_calendario(sel)
        time.sleep_ms(15)


# ======================================================================
#  GRABADORA
# ======================================================================
def dibujar_grabadora(estado_sd, pendientes, nota=""):
    poner_fondo("fondo_grabadora.raw", CLARO)
    texto_borde("O grabar", 3, 3)
    x, y, w, h = 2, 99, 104, 27
    panel(x, y, w, h)
    if not estado_sd:
        fb.text("Sin microSD", x + 4, y + 4, ROJO)
        fb.text(recortar(nota or "O reintentar", 12), x + 4, y + 15, GRIS)
    elif pendientes:
        fb.text("%d por subir" % pendientes, x + 4, y + 4, NAVY)
        fb.text("DER = subir", x + 4, y + 15, GRIS)
    else:
        fb.text("Todo subido", x + 4, y + 4, NAVY)
        if nota:
            fb.text(recortar(nota, 12), x + 4, y + 15, GRIS)
    mostrar()


def pedir_permiso():
    """Antes de grabar: confirmar que se pidió permiso a las personas grabadas."""
    fb.fill(AZUL)
    fb.fill_rect(0, 0, W, 13, NAVY)
    fb.text("PERMISO", 3, 3, BLANCO)
    panel(4, 17, W - 8, 82)
    for k, l in enumerate(("Pediste permiso a", "las personas que", "vas a grabar?", "(profe, companeros)")):
        fb.text(l, 8, 22 + k * 11, NAVY if k < 3 else GRIS)
    fb.fill_rect(8, 70, W - 16, 14, VERDE)
    fb.text("O  Si, ya pedi", 12, 73, BLANCO)
    fb.text("<O No, volver", 12, 90, GRIS)
    fb.text("Grabar sin permiso", 4, 103, BLANCO)
    fb.text("puede ser ilegal", 4, 114, BLANCO)
    mostrar()
    sonar("tic", 4)
    while True:
        e_o, e_izq = b_o.leer(), b_izq.leer()
        b_der.leer()
        if e_o == "corto":
            sonar("seleccionar")
            return True
        if e_o == "largo" or e_izq == "presion":
            sonar("volver")
            esperar_soltar()
            return False
        tick()
        time.sleep_ms(15)


def dibujar_grabando(g):
    poner_fondo("fondo_grabando.raw", AZUL)
    x, y, w, h = 3, 16, 72, 40
    panel(x, y, w, h)
    s = g.segundos()
    if s // 1 % 2 == 0:
        fb.fill_rect(x + 5, y + 5, 6, 6, ROJO)                  # punto que parpadea
    fb.text("REC", x + 14, y + 4, ROJO)
    t = "%02d:%02d" % (s // 60, s % 60)
    chico(t, x + (w - ancho_chico(t, 3)) // 2, y + 15, NAVY, None, 3)
    nivel = min(w - 10, g.nivel * (w - 10) // 12000)
    fb.rect(x + 5, y + 33, w - 10, 4, GRIS)
    fb.fill_rect(x + 5, y + 33, nivel, 4, VERDE if g.nivel < 25000 else AMARILLO)
    texto_borde("O parar", 3, H - 11)
    mostrar()


def subir_pendientes():
    import grabadora
    lista = grabadora.pendientes()
    if not lista:
        return True
    if not red.conectar_ya(esperando_wifi):
        mensaje("Sin WiFi", "Se sube despues")
        sonar("error")
        time.sleep(2)
        return False
    for i, nombre in enumerate(lista):
        def avance(pos, total, i=i):
            mensaje("Subiendo %d/%d" % (i + 1, len(lista)), "%d%%" % (pos * 100 // max(1, total)))
            if b_o.p.value() == 0:
                raise KeyboardInterrupt
        try:
            avance(0, 1)
            red.subir_archivo(grabadora.CARPETA + "/" + nombre, nombre, avance)
            grabadora.marcar_subido(nombre)
        except KeyboardInterrupt:
            mensaje("Pausado", "Sigue despues")
            esperar_soltar()
            time.sleep(1)
            return False
        except Exception as e:
            print("Subida:", e)
            mensaje("No se pudo subir", "Abre Wonder Hub")
            sonar("error")
            time.sleep(2)
            return False
    sonar("listo")
    mensaje("Subido!", "Ve la app")
    time.sleep(1)
    return True


def nota_sd(grabadora, sd):
    if not sd:
        return grabadora.ultimo_error
    mb = grabadora.espacio_libre_mb()
    return ("Libre %d GB" % (mb // 1024)) if mb >= 2048 else ("Libre %d MB" % mb)


def pantalla_grabadora():
    global OCUPADO
    if not pedir_permiso():
        return "menu"
    permiso = True                  # sirve para UNA grabación; la siguiente vuelve a preguntar
    gc.collect()
    import grabadora
    mensaje("Preparando", "microSD...")
    sd = grabadora.montar()
    nota = nota_sd(grabadora, sd)
    dibujar_grabadora(sd, len(grabadora.pendientes()) if sd else 0, nota)
    while True:
        e_izq, e_der, e_o = b_izq.leer(), b_der.leer(), b_o.leer()
        if e_o == "largo":
            sonar("volver")
            esperar_soltar()
            return "menu"
        if e_o == "corto":
            if not sd:
                mensaje("Preparando", "microSD...")
                sd = grabadora.montar()
                nota = nota_sd(grabadora, sd)
                if not sd:
                    sonar("error")
                    dibujar_grabadora(False, 0, nota)
                    continue
            # ---- grabar ----
            if not permiso:
                permiso = pedir_permiso()
                if not permiso:
                    dibujar_grabadora(sd, len(grabadora.pendientes()), nota)
                    continue
            permiso = False
            sonar("seleccionar")
            time.sleep_ms(250)                       # que el sonido no quede en la grabación
            gc.collect()
            try:
                g = grabadora.Grabacion()
            except Exception as e:
                import sys
                sys.print_exception(e)
                mensaje("No se pudo grabar", (str(e) or type(e).__name__)[:18])
                sonar("error")
                time.sleep(2)
                dibujar_grabadora(sd, len(grabadora.pendientes()), nota)
                continue
            OCUPADO = True
            esperar_soltar()
            t_pantalla = 0
            try:
                while True:
                    sigue = g.paso()
                    if b_o.leer() == "corto" or not sigue:
                        break
                    b_izq.leer(); b_der.leer()
                    ahora = time.ticks_ms()
                    if time.ticks_diff(ahora, t_pantalla) > 500:
                        t_pantalla = ahora
                        tick()
                        dibujar_grabando(g)
            finally:
                nombre = g.terminar()
                OCUPADO = False
                gc.collect()
                print("RAM libre tras grabar:", gc.mem_free())
            sonar("guardar")
            mensaje("Guardado", nombre[6:22])
            time.sleep(1)
            if red.conectado():
                subir_pendientes()
            nota = nota_sd(grabadora, sd)
            dibujar_grabadora(sd, len(grabadora.pendientes()), nota)
        if e_der == "presion" and sd and grabadora.pendientes():
            sonar("seleccionar")
            subir_pendientes()
            dibujar_grabadora(sd, len(grabadora.pendientes()), nota)
        if tick():
            dibujar_grabadora(sd, len(grabadora.pendientes()) if sd else 0, nota)
        time.sleep_ms(15)


# ======================================================================
#  MODO CONFIGURAR: el llavero crea su propia red y la app le manda el WiFi
#  Cada red que llega se AGREGA a las que ya tenía (no se borra nada).
# ======================================================================
CABECERAS_CORS = ("Access-Control-Allow-Origin: *\r\n"
                  "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                  "Access-Control-Allow-Headers: Content-Type\r\n"
                  "Access-Control-Allow-Private-Network: true\r\n")

PAGINA_CONFIG = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>Wonder</title><body style="font-family:monospace;background:#dceaff;padding:20px">
<h2>WONDER - agregar red WiFi</h2><p>Redes guardadas: %s</p><form method=post action=/config>
<p>Nombre del WiFi<br><input name=wifi_nombre required>
<p>Clave del WiFi<br><input name=wifi_clave type=password>
<p>Wonder Hub (ej. http://172.20.10.2:8000)<br><input name=servidor value="%s">
<p>Clave del llavero<br><input name=clave value="%s" required>
<p><button>Guardar</button></form>"""


def _descifrar(t):
    t = t.replace("+", " ").split("%")
    b = t[0].encode()
    for parte in t[1:]:
        try:
            b += bytes((int(parte[:2], 16),)) + parte[2:].encode()
        except ValueError:
            b += b"%" + parte.encode()
    return b.decode()


def _responder(cl, cuerpo, tipo="application/json", estado="200 OK"):
    cuerpo = cuerpo.encode()
    cl.sendall(("HTTP/1.1 %s\r\nContent-Type: %s; charset=utf-8\r\nContent-Length: %d\r\n"
                "Connection: close\r\n%s\r\n" % (estado, tipo, len(cuerpo), CABECERAS_CORS)).encode())
    cl.sendall(cuerpo)


def _leer_cuerpo(texto):
    try:
        return json.loads(texto)
    except ValueError:
        c = {}
        for par in texto.split("&"):
            k, _, v = par.partition("=")
            c[_descifrar(k)] = _descifrar(v)
        return c


def _info():
    return json.dumps({"wonder": 2, "configurado": red.configurado(), "redes": red.nombres(),
                       "bateria": BAT["pct"], "usb": BAT["usb"]})


def _atender(cl):
    """Atiende una petición. Devuelve el nombre de la red guardada, o None."""
    cl.settimeout(5)
    datos = b""
    while b"\r\n\r\n" not in datos and len(datos) < 4096:
        trozo = cl.recv(512)
        if not trozo:
            break
        datos += trozo
    cabeza, _, cuerpo = datos.partition(b"\r\n\r\n")
    lineas = cabeza.decode().split("\r\n")
    partes = lineas[0].split(" ")
    if len(partes) < 2:
        return None
    metodo, ruta = partes[0], partes[1].split("?")[0]
    largo = 0
    for l in lineas[1:]:
        if l.lower().startswith("content-length:"):
            largo = int(l.split(":")[1])
    while len(cuerpo) < largo and largo <= 2048:
        trozo = cl.recv(512)
        if not trozo:
            break
        cuerpo += trozo

    if metodo == "OPTIONS":
        _responder(cl, "", estado="204 No Content")
    elif metodo == "GET" and ruta == "/info":
        _responder(cl, _info())
    elif metodo == "GET" and ruta == "/":
        _responder(cl, PAGINA_CONFIG % (", ".join(red.nombres()) or "ninguna",
                                        red.cfg["servidor"], red.cfg["clave"]), "text/html")
    elif metodo == "POST" and ruta == "/config":
        c = _leer_cuerpo(cuerpo.decode())
        nombre = str(c.get("wifi_nombre", "")).strip()
        servidor = str(c.get("servidor", "")).strip()
        clave = str(c.get("clave", "")).strip() or red.cfg["clave"]
        if not nombre or not clave or (servidor and not servidor.startswith("http")):
            _responder(cl, json.dumps({"ok": False, "error": "Faltan datos"}), estado="400 Bad Request")
            return None
        red.agregar_red(nombre, str(c.get("wifi_clave", "")), servidor, clave)
        _responder(cl, json.dumps({"ok": True, "redes": red.nombres()}))
        return nombre
    elif metodo == "POST" and ruta == "/olvidar":
        c = _leer_cuerpo(cuerpo.decode())
        red.olvidar_red(str(c.get("nombre", "")))
        _responder(cl, json.dumps({"ok": True, "redes": red.nombres()}))
        return ""
    else:
        _responder(cl, json.dumps({"ok": False}), estado="404 Not Found")
    return None


def dibujar_configurar(ip, nota=""):
    fb.fill(AZUL)
    fb.fill_rect(0, 0, W, 13, NAVY)
    fb.text("CONFIGURAR", 3, 3, BLANCO)
    panel(4, 17, W - 8, H - 31)
    fb.text("1 Conectate a:", 8, 21, GRIS)
    fb.text(AP_NOMBRE, 8, 31, NAVY)
    fb.text("clave " + AP_CLAVE, 8, 42, NAVY)
    fb.text("2 Vuelve a la app", 8, 56, GRIS)
    fb.text("Redes: %d" % len(red.nombres()), 8, 70, NAVY)
    if nota:
        fb.text(recortar(nota, 17), 8, 82, VERDE if nota.startswith("+") else GRIS)
    fb.text("O = salir", 2, H - 11, CLARO)
    mostrar()


def pantalla_configurar():
    import network
    import socket
    red.apagar_wifi()
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=AP_NOMBRE, password=AP_CLAVE)
    ap.active(True)
    for _ in range(50):
        if ap.active():
            break
        time.sleep_ms(100)
    ip = ap.ifconfig()[0]
    print("Modo configurar:", AP_NOMBRE, ip)
    dibujar_configurar(ip)
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(2)
    s.settimeout(0.2)
    try:
        while True:
            try:
                cl, _ = s.accept()
            except OSError:
                if b_o.leer() == "corto":
                    break
                b_izq.leer(); b_der.leer()
                continue
            try:
                nombre = _atender(cl)
                if nombre:
                    sonar("guardar")
                    dibujar_configurar(ip, "+ " + nombre)
                elif nombre == "":
                    dibujar_configurar(ip, "Red olvidada")
            except Exception as e:
                print("Config:", e)
            finally:
                cl.close()
    finally:
        s.close()
        ap.active(False)
    sonar("volver")
    esperar_soltar()
    return "inicio"


# ======================================================================
#  PROGRAMA
# ======================================================================
ESTADOS = {
    "inicio": pantalla_inicio,
    "menu": pantalla_menu,
    "configurar": pantalla_configurar,
    "calendario": pantalla_calendario,
    "pomodoro": pantalla_pomodoro,
    "grabadora": pantalla_grabadora,
}

init_pantalla()
gc.collect()
print("RAM libre:", gc.mem_free())
leer_bateria()                      # antes de prender el WiFi
if sonidos:
    sonidos.iniciar()
sonar("encender")
cargar_menu()
estado = "inicio" if red.cargar() else "configurar"
while True:
    gc.collect()
    print("->", estado, "| RAM libre:", gc.mem_free())
    try:
        estado = ESTADOS[estado]()
    except Exception as e:          # que un error no deje el llavero colgado
        import sys
        sys.print_exception(e)
        OCUPADO = False
        mensaje("Algo fallo :(", str(e)[:18])
        sonar("error")
        time.sleep(3)
        estado = "menu"
