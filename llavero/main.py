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
#   Wonder:      IZQ / DER = elegir (comidas, accesorios, racha),  O = dar / poner / quitar,
#                mantener O = volver
#   Juegos:      O = jugar (desde 25 % de energía),  IZQ / DER = ver los otros juegos,
#                dentro del juego: mantener IZQ + DER 1 s = salir
#   Configuración: IZQ / DER = elegir,  O = cambiar,  mantener O = volver
#   En cualquier pantalla: mantener IZQ + DER 2,5 s = APAGAR (pantalla, WiFi y parlante).
#                          Para prender: mantener O 2 s (vuelve a la pantalla de inicio).
#
# Archivos en el Pico: los .raw y .spr de las pantallas, sonidos.py, red.py,
# bateria.py, grabadora.py, rapido.py, sdcard.py, juegos.py, chip8.py, ajustes.py,
# ota.py, version.txt y los juegos juego_*.ch8.
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

APPS = [("calendario", "Calendario"), ("pomodoro", "Pomodoro"), ("grabadora", "Grabadora"),
        ("wonder", "Wonder"), ("juegos", "Juegos"), ("ajustes", "Configuracion")]
GUARDAR_HORA_MIN = 30       # cada cuánto se guarda la hora (por si el Pico se reinicia)
NTP_CADA_H = 6              # cada cuánto se corrige la hora con internet (si no hay hub)
BURBUJA_CENTRO = (39, 17)
ICONO_SEL = (114, 62)
ICONO_IZQ = (75, 62)
ICONO_DER = (151, 62)
TEXTO_INICIO_Y = 9
# ===================================================

try:
    with open("version.txt") as _f:
        VERSION = _f.read().strip()
except OSError:
    VERSION = "8.0"

W, H = 160, 128
TAM_PANTALLA = W * H * 2


class VolverInicio(Exception):
    """Después de un apagado con IZQ + DER: se vuelve a la pantalla "Pulsa O"."""
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


def poner_fondo(nombre, respaldo=AZUL):
    """Carga un fondo .raw directo al lienzo (sin copia en RAM, para ahorrar memoria).
    Si no existe el archivo, pinta un color (placeholder)."""
    if existe(nombre):
        with open(nombre, "rb") as f:
            f.readinto(lienzo)
    else:
        fb.fill(respaldo)


# ---------------- Botones ----------------
PINES = {"izq": 15, "o": 14, "der": 16}   # izquierdo GP15, centro GP14, derecho GP16
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
T = {"red": 0, "bat": None, "sync": None, "ev": 0, "sync_ok": True, "hora_guardada": 0,
     "ntp": None, "racha": 0, "aviso_mudo": False}
OCUPADO = False              # True mientras graba: no sincroniza (no interrumpir)
_barra_dibujada = None


# ---------------- Reloj ----------------
# El reloj del Pico sigue andando dormido (no gasta más). Solo se pierde si el Pico
# se REINICIA (al conectarlo a Thonny, si se cuelga o si se acaba la batería).
# Por eso: la hora se pone sola con el hub o con internet, se guarda cada 30 min en
# hora.json, y si un día arranca sin hora NO supone que es de día: usa el último
# momento (día / tarde / noche) que conoció.
ARCH_HORA = "hora.json"
RELOJ = {"mom": None}
try:
    with open(ARCH_HORA) as _f:
        RELOJ.update(json.load(_f))
except (OSError, ValueError):
    pass


def hora_ok():
    return time.localtime()[0] >= 2025


def guardar_hora():
    if not hora_ok():
        return
    RELOJ["mom"] = momento()
    RELOJ["t"] = time.time()
    try:
        with open(ARCH_HORA, "w") as f:
            json.dump(RELOJ, f)
    except OSError:
        pass


def hora_puesta():
    """Llamar cada vez que la hora llega del hub o de internet."""
    T["ntp"] = time.ticks_ms()
    revisar_racha()
    guardar_hora()


def texto_hora():
    t = time.localtime()
    return "%02d:%02d" % (t[3], t[4]) if hora_ok() else "--:--"


def firma_barra():
    return (texto_hora(), BAT["pct"], BAT["usb"], red.conectado(),
            pomo_estado() if pomo_estado() != "parado" else None,
            pomo_resta_s() // 60 if pomo_estado() != "parado" else None,
            EST_W.get("racha", 0), silenciado())


def barra_cambio():
    return BARRA and firma_barra() != _barra_dibujada


def silenciado():
    return bool(sonidos) and (not sonidos.activo or sonidos.bloqueado)


FUEGO = ((3, 0), (2, 1), (3, 1), (2, 2), (3, 2), (4, 2), (1, 3), (2, 3), (3, 3), (4, 3), (5, 3),
         (1, 4), (2, 4), (4, 4), (5, 4), (1, 5), (2, 5), (4, 5), (5, 5), (2, 6), (3, 6), (4, 6))
FUEGO_DENTRO = ((3, 4), (3, 5))


def fuego(x, y):
    """Fueguito de la racha (7x7)."""
    for px, py in FUEGO:
        fb.pixel(x + px, y + py, ROJO)
    for px, py in FUEGO_DENTRO:
        fb.pixel(x + px, y + py, AMARILLO)


def parlante(x, y, mudo):
    """Parlante de 7x7: con ondas si suena, con una X roja si está silenciado."""
    for px, py in ((0, 2), (0, 3), (0, 4), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5),
                   (3, 0), (3, 1), (3, 2), (3, 3), (3, 4), (3, 5), (3, 6)):
        fb.pixel(x + px, y + py, BLANCO)
    if mudo:
        for k in range(3):
            fb.pixel(x + 4 + k, y + 2 + k, ROJO)
            fb.pixel(x + 6 - k, y + 2 + k, ROJO)
    else:
        for px, py in ((5, 2), (5, 3), (5, 4), (6, 1), (6, 5)):
            fb.pixel(x + px, y + py, BLANCO)


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
    fb.fill_rect(x - 1, 2, ancho_chico(h) + 2, 7, NAVY)
    chico(h, x, 3)
    # WiFi: tres rayitas
    if red.conectado():
        x -= 8
        fb.fill_rect(x - 1, 2, 7, 8, NAVY)
        fb.fill_rect(x, 7, 1, 2, BLANCO)
        fb.fill_rect(x + 2, 5, 1, 4, BLANCO)
        fb.fill_rect(x + 4, 3, 1, 6, BLANCO)
    # parlante (con X si está silenciado)
    x -= 9
    fb.fill_rect(x - 1, 1, 9, 9, NAVY)
    parlante(x, 2, silenciado())
    # racha de estudio: fueguito + días
    racha = EST_W.get("racha", 0)
    if racha:
        n = "%d" % racha
        x -= ancho_chico(n) + 11
        fb.fill_rect(x - 1, 1, ancho_chico(n) + 11, 9, NAVY)
        fuego(x, 2)
        chico(n, x + 9, 3, AMARILLO)
    # pomodoro corriendo: punto rojo + minutos
    if pomo_estado() != "parado":
        m = "%d" % (pomo_resta_s() // 60)
        x -= ancho_chico(m) + 8
        fb.fill_rect(x - 1, 2, 5, 7, NAVY)
        fb.fill_rect(x, 4, 3, 3, ROJO if POMO["fase"] == "estudio" else VERDE)
        chico(m, x + 5, 3)


def momento():
    """'dia' (6-17 h), 'tarde' (17-19 h) o 'noche' (19-6 h).
    Sin hora: el último momento que se conoció (no supone que es de día)."""
    if not hora_ok():
        return RELOJ.get("mom") or "dia"
    h = time.localtime()[3]
    return "dia" if 6 <= h < 17 else "tarde" if 17 <= h < 19 else "noche"


def fondo_del_momento(base):
    """fondo_<base>_<momento>.raw si existe; si no, el fondo de siempre."""
    n = "fondo_%s_%s.raw" % (base, momento())
    return n if existe(n) else "fondo_%s.raw" % base


def leer_bateria():
    """USB sí/no siempre; el porcentaje solo si se instaló el divisor (ver bateria.py)."""
    pct, usb, v = bateria.leer()
    BAT["usb"] = usb
    if pct is not None:
        BAT["pct"] = pct


def tick():
    """Llamar en cada vuelta de cualquier pantalla. Devuelve True si hay que redibujar."""
    ahora = time.ticks_ms()
    redibujar = False
    if time.ticks_diff(ahora, T["red"]) > 1000:
        T["red"] = ahora
        red.mantener()
    if T["bat"] is None or time.ticks_diff(ahora, T["bat"]) > 10000:
        T["bat"] = ahora                         # cada 10 s: USB y (si hay divisor) batería
        leer_bateria()
    if sonidos:
        sonidos.revisar()                        # que el sonido nunca se quede "mudo"
        if sonidos.bloqueado and not T["aviso_mudo"]:
            T["aviso_mudo"] = True               # la protección cortó el parlante: avisar una vez
            mensaje("Parlante silenciado", "por seguridad")
            time.sleep(2)
            redibujar = True
    if b_izq.p.value() == 0 and b_der.p.value() == 0 and not OCUPADO:
        if T.get("combo") is None:
            T["combo"] = ahora
        elif time.ticks_diff(ahora, T["combo"]) > 2500:   # IZQ + DER 2,5 s = apagar
            T["combo"] = None
            mensaje("Apagando...", "Mantener O = prender")
            esperar_soltar()
            time.sleep_ms(600)
            dormir(apagado=True)
            raise VolverInicio()
    else:
        T["combo"] = None
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
    if (red.conectado() and not OCUPADO and not T["sync_ok"]
            and (T["ntp"] is None or time.ticks_diff(ahora, T["ntp"]) > NTP_CADA_H * 3600000)):
        T["ntp"] = ahora                         # sin hub: la hora de internet, cada pocas horas
        if red.hora_de_internet():
            hora_puesta()
            redibujar = True
    if time.ticks_diff(ahora, T["hora_guardada"]) > GUARDAR_HORA_MIN * 60000:
        T["hora_guardada"] = ahora
        guardar_hora()
    if not OCUPADO and time.ticks_diff(ahora, T["racha"]) > 60000:
        T["racha"] = ahora                       # cada minuto: ¿cambió el día? ¿se perdió la racha?
        if revisar_racha():
            redibujar = True
    if (not BAT["usb"] and pomo_estado() == "parado" and not OCUPADO
            and time.ticks_diff(ahora, ACT["t"]) > APAGAR_MIN * 60000):
        dormir()
        return True
    if not OCUPADO and time.ticks_diff(ahora, T["ev"]) > 30000:
        T["ev"] = ahora
        if revisar_eventos():
            redibujar = True
    if PEND and not OCUPADO:
        mostrar_pendientes()                     # comida nueva, racha perdida...
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
    com = EST_W.get("comida", {})
    q = ("/pico/estado?v=%s&bat=%s&usb=%d&red=%s&redes=%s&racha=%d&energia=%d&comida=%d,%d,%d"
         "&juego=%s&version=%s") % (
        tengo, "" if BAT["pct"] is None else BAT["pct"], 1 if BAT["usb"] else 0,
        red.citar(red.red_actual or ""), red.citar("|".join(red.nombres())),
        EST_W.get("racha", 0), EST_W.get("energia", 0),
        com.get("mailo", 0), com.get("arepa", 0), com.get("changua", 0),
        EST_W.get("juego", ""), red.citar(VERSION))
    codigo, d = red.pedir(q, timeout=3)
    if codigo != 200 or not d:
        print("Sin hub (", codigo, ")")
        if not hora_ok() and red.hora_de_internet():
            hora_puesta()
        return False
    if d.get("ahora") and red.poner_hora(d["ahora"]):
        hora_puesta()
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
            LOGROS["fecha"] = hoy_str()
        datos_cal = d
        t_datos = time.ticks_ms()
        if d.get("ahora") and red.poner_hora(d["ahora"]):
            hora_puesta()
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


def hoy_str():
    t = time.localtime()
    return "%04d-%02d-%02d" % t[:3]


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
    if LOGROS.get("fecha") != hoy_str():
        LOGROS["hoy"], LOGROS["fecha"] = 0, hoy_str()
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
def dormir(apagado=False):
    """Apaga pantalla, WiFi y parlante. Despierta con cualquier botón o
    cuando una clase está por empezar.
    apagado=True ("apagar" a mano): solo despierta manteniendo O 2 segundos."""
    import machine
    print("Apagando..." if apagado else "Durmiendo...")
    guardar_hora()
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
    t_o = None
    while True:
        if apagado:
            if b_o.p.value() == 0:                  # mantener O 2 s para prender
                if t_o is None:
                    t_o = time.ticks_ms()
                elif time.ticks_diff(time.ticks_ms(), t_o) > 2000:
                    break
            else:
                t_o = None
        elif any(p.value() == 0 for p in botones):
            break
        if not apagado and time.ticks_diff(time.ticks_ms(), t_revision) > 30000:
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
        PEND.append(("sesion", registrar_sesion()))    # racha y comida (se muestra enseguida)
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
    racha = EST_W.get("racha", 0)                      # la racha, también aquí
    fb.fill_rect(2, 25, 11, 9, NAVY)
    fuego(4, 26)
    texto_borde(("%d dia" if racha == 1 else "%d dias") % racha, 15, 26, AMARILLO)
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
#  WONDER: racha, comida, energía, ánimo e inventario
#
#  RACHA: días de semana (lunes a viernes) seguidos con al menos un pomodoro
#  terminado (cualquiera, hasta el más corto). Sábado y domingo NO cuentan ni la
#  rompen; estudiar ese día no suma nada.
#  COMIDA: desde 2 días de racha, cada pomodoro te da una comida al azar que se
#  guarda. Tú decides cuándo dársela a Wonder:
#      Básica  Mailo    +20 % energía  (sale 60 de cada 100 veces)
#      Rara    Arepa    +27 %          (30 de 100)
#      Nicho   Changua  +35 %          (10 de 100)
#  ENERGÍA: solo sube comiendo y NUNCA baja sola. Para jugar hace falta 25 %.
#  Si pierdes la racha (de 2 días o más), el juego del menú cambia al azar.
#  El ÁNIMO sale de la energía, los ¡Hecho!, la racha y lo que se pasó sin marcar.
# ======================================================================
ARCH_WONDER = "wonder_estado.json"
MORADO = color(175, 95, 235)
# (id, nombre, rareza, energía, probabilidad de 100)
COMIDAS = (("mailo", "Mailo", "basica", 20, 60), ("arepa", "Arepa", "rara", 27, 30),
           ("changua", "Changua", "nicho", 35, 10))
RAREZAS = {"basica": ("BASICA", BLANCO), "rara": ("RARA", AZUL), "nicho": ("NICHO", MORADO)}
# (id, nombre). Los detalles de cada juego están en juegos.py.
JUEGOS = (("br8kout", "Br8kout"), ("flightrunner", "Flight Runner"), ("piper", "Piper"),
          ("sweetcopter", "Sw8 Copter"))
ENERGIA_JUGAR = 25
ENERGIA_CAMBIAR = 50
# (id, nombre, ¡Hecho! necesarios para desbloquear). Los "???" esperan sus sprites.
COSMETICOS = (("gafas", "Gafas", 0), ("bufanda", "Bufanda", 0), ("nuevo1", "???", 10),
              ("nuevo2", "???", 25), ("nuevo3", "???", 50))
POS_CAPA = {"wonder_base": (54, 10), "wonder_feliz": (54, 10), "wonder_triste": (55, 22),
            "wonder_enojado": (54, 10), "acc_gafas": (62, 58), "acc_bufanda": (74, 78)}
EST_W = {"puestos": ["gafas"], "visita": "", "racha": 0, "ult_dia": "", "energia": 0,
         "comida": {"mailo": 0, "arepa": 0, "changua": 0}, "juego": "", "sin_fecha": 0,
         "vio_racha": False}
try:
    with open(ARCH_WONDER) as f:
        EST_W.update(json.load(f))
except (OSError, ValueError):
    pass
for _k in ("fecha", "min_estudio"):          # lo de la v7 (barra de estudio) ya no se usa
    EST_W.pop(_k, None)
PEND = []                                    # avisos por mostrar: comida nueva, racha perdida...


def guardar_wonder():
    try:
        with open(ARCH_WONDER, "w") as f:
            json.dump(EST_W, f)
    except OSError:
        pass


def _azar(n):
    import random
    return random.getrandbits(16) % n


def juego_actual():
    ids = [j[0] for j in JUEGOS]
    if EST_W.get("juego") not in ids:
        EST_W["juego"] = ids[_azar(len(ids))]
        guardar_wonder()
    return EST_W["juego"]


def nombre_juego(ident):
    for j, n in JUEGOS:
        if j == ident:
            return n
    return ident


def cambiar_juego(nuevo=None):
    """Pone otro juego en el menú (al azar si no se dice cuál)."""
    actual = juego_actual()
    if nuevo is None:
        otros = [j[0] for j in JUEGOS if j[0] != actual]
        nuevo = otros[_azar(len(otros))]
    EST_W["juego"] = nuevo
    guardar_wonder()
    recargar_icono_juegos()
    return nuevo


def _fecha(t):
    return "%04d-%02d-%02d" % time.localtime(t)[:3]


def dia_habil_anterior():
    """El último día de semana (lunes a viernes) ANTES de hoy, como 'AAAA-MM-DD'."""
    t = time.time() - 86400
    while time.localtime(t)[6] >= 5:          # 5 = sábado, 6 = domingo
        t -= 86400
    return _fecha(t)


def es_finde():
    return hora_ok() and time.localtime()[6] >= 5


def sortear_comida():
    r = _azar(100)
    for ident, _, _, _, prob in COMIDAS:
        if r < prob:
            return ident
        r -= prob
    return COMIDAS[0][0]


def datos_comida(ident):
    for c in COMIDAS:
        if c[0] == ident:
            return c
    return COMIDAS[0]


def registrar_sesion():
    """Un pomodoro de estudio terminó. Devuelve la comida ganada, "finde", "sin_hora" o None."""
    if not hora_ok():
        EST_W["sin_fecha"] = EST_W.get("sin_fecha", 0) + 1     # cuenta para hoy cuando vuelva la hora
        guardar_wonder()
        return "sin_hora"
    if es_finde():
        return "finde"
    revisar_racha()                            # por si se perdió y aún no se había revisado
    hoy = hoy_str()
    if EST_W["ult_dia"] != hoy:
        if EST_W["ult_dia"] and EST_W["ult_dia"] >= dia_habil_anterior():
            EST_W["racha"] += 1
        else:
            EST_W["racha"] = 1
        EST_W["ult_dia"] = hoy
    premio = None
    if EST_W["racha"] >= 2:
        premio = sortear_comida()
        EST_W["comida"][premio] = EST_W["comida"].get(premio, 0) + 1
    guardar_wonder()
    return premio


def revisar_racha():
    """Con la hora puesta: suma las sesiones que terminaron sin hora y revisa si se
    perdió la racha (un día de semana sin estudiar). True si cambió algo."""
    if not hora_ok():
        return False
    cambio = False
    n = EST_W.get("sin_fecha", 0)
    if n:
        EST_W["sin_fecha"] = 0
        for _ in range(n):
            PEND.append(("sesion", registrar_sesion()))
        cambio = True
    r = EST_W.get("racha", 0)
    if r and EST_W["ult_dia"] < dia_habil_anterior():
        EST_W["racha"] = 0
        if r >= 2:
            PEND.append(("racha_perdida", cambiar_juego()))
        guardar_wonder()
        cambio = True
    return cambio


def mostrar_pendientes():
    """Muestra los avisos guardados en PEND (comida nueva, fin de semana, racha perdida)."""
    while PEND:
        tipo, dato = PEND.pop(0)
        if tipo == "sesion":
            if dato == "finde":
                sonar("listo")
                mensaje("Fin de semana :)", "No suma a la racha")
                esperar_boton(2500)
            elif dato == "sin_hora":
                sonar("listo")
                mensaje("Pomodoro listo!", "Cuenta con la hora")
                esperar_boton(2000)
            elif dato:
                pantalla_comida_nueva(dato)
        elif tipo == "racha_perdida":
            sonar("racha_perdida")
            mensaje("Perdiste la racha", "Juego: " + nombre_juego(dato))
            esperar_boton(3500)


def esperar_boton(ms):
    fin = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(fin, time.ticks_ms()) > 0:
        if "presion" in (b_o.leer(), b_izq.leer(), b_der.leer()):
            break
        time.sleep_ms(20)
    esperar_soltar()
    ACT["t"] = time.ticks_ms()


def pantalla_comida_nueva(ident):
    _, nombre, rareza, energia, _ = datos_comida(ident)
    titulo, c = RAREZAS[rareza]
    fb.fill(NAVY)
    panel(8, 8, W - 16, H - 16)
    fb.fill_rect(9, 9, W - 18, 13, c if rareza != "basica" else GRIS)
    t = "Comida " + titulo + "!"
    fb.text(t, (W - len(t) * 8) // 2, 12, BLANCO)
    spr = cargar_spr("comida_%s.spr" % ident)
    if spr:
        pegar(spr, W // 2, 52)
    else:
        fb.fill_rect(W // 2 - 20, 32, 40, 40, c)
    texto_centro(nombre, 82, NAVY)
    texto_centro("+%d%% energia" % energia, 94, VERDE)
    texto_centro("Dasela en Wonder", 106, GRIS)
    mostrar()
    sonar("comida", rareza)
    esperar_boton(4000)
    del spr
    gc.collect()


def hechos_hoy():
    return LOGROS.get("hoy", 0) if LOGROS.get("fecha") == hoy_str() else 0


def vencidos():
    """Tareas o clases de las últimas 24 h que ya terminaron y no se marcaron."""
    if not datos_cal or not hora_ok():
        return 0
    ahora = ahora_iso()
    t = time.localtime(time.time() - 86400)
    ayer = "%04d-%02d-%02dT%02d:%02d" % t[:5]
    return sum(1 for ev in datos_cal.get("eventos", [])
               if ev.get("fin") and ayer <= ev["fin"] <= ahora and not es_hecho(ev))


def medidores():
    """(ánimo, energía, vencidos). Ánimo y energía de 0 a 100."""
    venc = vencidos()
    energia = max(0, min(100, EST_W.get("energia", 0)))
    animo = (45 + energia * 30 // 100 + 10 * min(hechos_hoy(), 3) + 3 * min(EST_W.get("racha", 0), 5)
             - 15 * min(venc, 3) + (5 if EST_W["visita"] == hoy_str() else 0))
    return max(0, min(100, animo)), energia, venc


def emocion(animo, venc):
    if venc >= 2:
        return "enojado"
    if animo < 40:
        return "triste"
    if animo >= 70:
        return "feliz"
    return "base"


FRASES = {
    "feliz": ("Bien hecho!", "Vamos genial", "Me encanta|estudiar contigo", "Que buen dia"),
    "base": ("Que hacemos|hoy?", "Un pomodoro?", "Aqui estoy", "Marca lo que|cumplas"),
    "triste": ("Te extrane...", "Hacemos una|tarea juntos?", "Un pomodoro|me animaria"),
    "enojado": ("Se te pasaron|tareas!", "Marca lo que|hiciste", "Hmph."),
}


def frase(emo, energia):
    if BAT["pct"] is not None and BAT["pct"] < 15:
        return "Cargame|porfa"
    if es_finde() and _azar(3) == 0:
        return "Finde: la racha|descansa :)"
    if energia < ENERGIA_JUGAR and emo != "enojado":
        return ("Tengo hambre...", "Un pomodoro y|me das comida?")[_azar(2)]
    opciones = FRASES[emo]
    return opciones[_azar(len(opciones))]


_spr_cache = {}


def capa(nombre):
    if nombre not in _spr_cache:
        if len(_spr_cache) > 5:
            _spr_cache.clear()
            gc.collect()
        _spr_cache[nombre] = cargar_spr(nombre + ".spr")
    return _spr_cache[nombre]


def pegar_capa(nombre):
    s = capa(nombre)
    if s:
        x, y = POS_CAPA.get(nombre, (0, 0))
        fb.blit(s[0], x, y, CLAVE_FB)


def icono_medidor(tipo, x, y, c):
    figuras = {"animo": ((1, 0), (2, 0), (4, 0), (5, 0), (0, 1), (3, 1), (6, 1), (0, 2), (6, 2),
                         (1, 3), (5, 3), (2, 4), (4, 4), (3, 5)),
               "energia": ((3, 0), (2, 1), (1, 2), (2, 2), (3, 2), (4, 2), (3, 3), (2, 4), (1, 5))}
    for px, py in figuras[tipo]:
        fb.pixel(x + px, y + py, c)


def items_wonder():
    """Lo que se elige abajo con IZQ / DER: comidas, accesorios y la ayuda de la racha."""
    return ([("comida", c[0]) for c in COMIDAS] + [("acc", k) for k in range(len(COSMETICOS))]
            + [("racha", None)])


def dibujar_wonder(sel, texto, comiendo=None):
    animo, energia, venc = medidores()
    emo = emocion(animo, venc)
    poner_fondo("fondo_inventario.raw", CLARO)
    pegar_capa("wonder_" + emo)
    for acc in EST_W["puestos"]:
        pegar_capa("acc_" + acc)
    texto_borde("WONDER", 3, 3)
    for k, linea in enumerate(texto.split("|")):
        texto_borde(linea, 3, 16 + k * 10, AMARILLO)
    x, y = 111, 16
    panel(x, y, 47, 34)
    for k, (tipo, v) in enumerate((("animo", animo), ("energia", energia))):
        yy = y + 4 + k * 10
        icono_medidor(tipo, x + 3, yy, ROJO if tipo == "animo" else NAVY)
        fb.rect(x + 12, yy, 32, 6, NAVY)
        if tipo == "animo":
            relleno = VERDE if v >= 60 else AMARILLO if v >= 30 else ROJO
        else:
            relleno = AMARILLO if v >= ENERGIA_JUGAR else GRIS
        fb.fill_rect(x + 13, yy + 1, 30 * v // 100, 4, relleno)
    fuego(x + 3, y + 24)
    chico("%d" % EST_W.get("racha", 0), x + 13, y + 25, NAVY, None)
    chico("%d%%" % energia, x + 44 - ancho_chico("%d%%" % energia), y + 25, GRIS, None)
    if comiendo:
        pegar(capa("comida_" + comiendo), 134, 80)
    tipo, dato = items_wonder()[sel]
    panel(2, 108, 156, 18)
    fb.text("<", 5, 113, GRIS)
    fb.text(">", 147, 113, GRIS)
    if tipo == "comida":
        ident, nombre, rareza, _, _ = datos_comida(dato)
        n = EST_W["comida"].get(ident, 0)
        mini = capa("comida_%s_mini" % ident)
        if mini:
            fb.blit(mini[0], 15, 117 - mini[2] // 2, CLAVE_FB)
        fb.fill_rect(15, 124, 16, 1, RAREZAS[rareza][1] if rareza != "basica" else GRIS)
        fb.text("%s x%d" % (nombre, n), 34, 113, NAVY if n else GRIS)
        if n:
            fb.text("O dar", 102, 113, VERDE)
    elif tipo == "acc":
        ident, nombre, necesita = COSMETICOS[dato]
        if LOGROS.get("total", 0) < necesita:
            fb.text(nombre, 16, 113, GRIS)
            fb.text("%d Hecho!" % necesita, 72, 113, GRIS)
        else:
            fb.text(nombre[:9], 16, 113, NAVY)
            puesto = ident in EST_W["puestos"]
            fb.text("Puesto" if puesto else "O poner", 90, 113, VERDE if puesto else GRIS)
    else:
        fuego(16, 113)
        fb.text("Racha?  O ver", 28, 113, NAVY)
    mostrar()
    return emo


def pantalla_ayuda_racha():
    """El aviso de cómo funciona la racha (y que el fin de semana no cuenta)."""
    fb.fill(AZUL)
    fb.fill_rect(0, 0, W, 13, NAVY)
    fuego(3, 3)
    fb.text("LA RACHA", 13, 3, BLANCO)
    panel(3, 16, W - 6, H - 19)
    lineas = (("Haz 1 pomodoro al", NAVY), ("dia (lunes a", NAVY), ("viernes).", NAVY),
              ("Desde 2 dias, cada", NAVY), ("pomodoro te da una", NAVY), ("comida al azar.", NAVY),
              ("Sab y dom NO", ROJO), ("cuentan ni rompen.", ROJO), ("Jugar: 25% energia", GRIS))
    for k, (l, c) in enumerate(lineas):
        fb.text(l, 7, 20 + k * 11, c)
    mostrar()
    EST_W["vio_racha"] = True
    guardar_wonder()
    esperar_soltar()
    while True:
        if "presion" in (b_o.leer(), b_izq.leer(), b_der.leer()):
            break
        tick()
        time.sleep_ms(20)
    esperar_soltar()


def dar_comida(ident):
    """Wonder se come una comida guardada. Devuelve el texto que dice Wonder."""
    _, nombre, _, sube, _ = datos_comida(ident)
    if EST_W["comida"].get(ident, 0) <= 0:
        sonar("error")
        return "No tienes|" + nombre
    if EST_W.get("energia", 0) >= 100:
        sonar("error")
        return "Estoy lleno!"
    EST_W["comida"][ident] -= 1
    EST_W["energia"] = min(100, EST_W.get("energia", 0) + sube)
    guardar_wonder()
    sonar("comer")
    return "Rico! +%d%%" % sube


def pantalla_wonder():
    if EST_W["visita"] != hoy_str() and hora_ok():
        EST_W["visita"] = hoy_str()             # visitar a Wonder una vez al día lo alegra un poco
        guardar_wonder()
    if not EST_W.get("vio_racha"):
        pantalla_ayuda_racha()                  # la primera vez: cómo funciona la racha
    items = items_wonder()
    sel = 0
    for k, (tipo, dato) in enumerate(items):   # empieza en la primera comida que tengas
        if tipo == "comida" and EST_W["comida"].get(dato, 0):
            sel = k
            break
    animo, energia, venc = medidores()
    emo = emocion(animo, venc)
    texto = frase(emo, energia)
    dibujar_wonder(sel, texto)
    sonar({"feliz": "hecho", "triste": "volver", "enojado": "error"}.get(emo, "seleccionar"))
    while True:
        e_izq, e_der, e_o = b_izq.leer(), b_der.leer(), b_o.leer()
        if e_o == "largo":
            sonar("volver")
            esperar_soltar()
            _spr_cache.clear()
            gc.collect()
            return "menu"
        paso = -1 if e_izq == "presion" else 1 if e_der == "presion" else 0
        if paso:
            sel = (sel + paso) % len(items)
            sonar("mover", paso, sel)
            dibujar_wonder(sel, texto)
        if e_o == "corto":
            tipo, dato = items[sel]
            if tipo == "comida":
                texto = dar_comida(dato)
                if texto.startswith("Rico"):
                    dibujar_wonder(sel, texto, comiendo=dato)
                    time.sleep_ms(900)
            elif tipo == "racha":
                sonar("seleccionar")
                pantalla_ayuda_racha()
            else:
                ident, nombre, necesita = COSMETICOS[dato]
                if LOGROS.get("total", 0) < necesita:
                    sonar("error")
                    texto = "Necesitas|%d Hecho!" % necesita
                elif not existe("acc_%s.spr" % ident):
                    sonar("error")
                    texto = "Pronto..."
                elif ident in EST_W["puestos"]:
                    EST_W["puestos"].remove(ident)
                    sonar("volver")
                else:
                    EST_W["puestos"].append(ident)
                    sonar("guardar")
                    texto = "Me queda|bien?"
                guardar_wonder()
            dibujar_wonder(sel, texto)
        if tick():
            dibujar_wonder(sel, texto)
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
            if app == "juegos":
                recargar_icono_juegos()
                continue
            iconos[app] = cargar_spr("icono_%s.spr" % app)
            minis[app] = cargar_spr("icono_%s_mini.spr" % app)
            nombres[app] = cargar_spr("nombre_%s.spr" % app)


def recargar_icono_juegos():
    """El ícono y el nombre de "Juegos" en el menú son los del juego que te tocó."""
    j = juego_actual()
    iconos["juegos"] = minis["juegos"] = nombres["juegos"] = None
    gc.collect()
    iconos["juegos"] = cargar_spr("icono_juego_%s.spr" % j)
    minis["juegos"] = cargar_spr("icono_juego_%s_mini.spr" % j)
    nombres["juegos"] = cargar_spr("nombre_juego_%s.spr" % j)


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
        if app == "juegos":
            texto = nombre_juego(juego_actual())
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
    ok = sincronizar()
    if not ok:
        mensaje("Buscando el hub", "en esta red...")
        if red.escanear_hub():                 # plan C: probar las direcciones de la red
            ok = sincronizar()
    T["sync_ok"] = ok
    if ok:
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
    poner_fondo(fondo_del_momento("grabadora"), CLARO)
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
                try:
                    g = grabadora.Grabacion()
                except OSError:
                    mensaje("Reintentando", "microSD...")
                    grabadora.remontar()               # error 5: se reinicia la tarjeta y otra vez
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
            if g.error:
                sonar("error")
                mensaje("microSD fallo", "Se guardo una parte")
                time.sleep(2)
                grabadora.remontar()
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
                       "bateria": BAT["pct"], "usb": BAT["usb"], "version": VERSION})


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
#  JUEGOS y CONFIGURACIÓN (cada uno en su archivo: se cargan solo al abrirlos)
# ======================================================================
def pantalla_juegos():
    gc.collect()
    import juegos
    try:
        return juegos.pantalla()
    finally:
        del sys.modules["juegos"]               # libera la RAM del juego al salir
        gc.collect()


def pantalla_ajustes():
    gc.collect()
    import ajustes
    try:
        return ajustes.pantalla()
    finally:
        del sys.modules["ajustes"]
        gc.collect()


ARCH_AJUSTES = "ajustes.json"
AJ = {"vol": {"notif": 100, "efectos": 100, "musica": 100}, "mudo": False}
try:
    with open(ARCH_AJUSTES) as _f:
        _a = json.load(_f)
    AJ["vol"].update(_a.get("vol", {}))
    AJ["mudo"] = bool(_a.get("mudo", False))
except (OSError, ValueError):
    pass


def guardar_ajustes():
    try:
        with open(ARCH_AJUSTES, "w") as f:
            json.dump(AJ, f)
    except OSError:
        pass
    if sonidos:
        sonidos.ajustar(AJ["vol"], AJ["mudo"])


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
    "wonder": pantalla_wonder,
    "juegos": pantalla_juegos,
    "ajustes": pantalla_ajustes,
}

init_pantalla()
gc.collect()
print("RAM libre:", gc.mem_free())
leer_bateria()                      # antes de prender el WiFi
if sonidos:
    sonidos.ajustar(AJ["vol"], AJ["mudo"])
    sonidos.iniciar()
sonar("encender")
print("Wonder", VERSION, "| hora guardada:", RELOJ.get("mom"))
cargar_menu()
estado = "inicio" if red.cargar() else "configurar"
while True:
    gc.collect()
    print("->", estado, "| RAM libre:", gc.mem_free())
    try:
        estado = ESTADOS[estado]()
    except VolverInicio:            # se apagó con IZQ + DER: al prender, "Pulsa O"
        OCUPADO = False
        estado = "inicio"
    except Exception as e:          # que un error no deje el llavero colgado
        import sys
        sys.print_exception(e)
        OCUPADO = False
        mensaje("Algo fallo :(", str(e)[:18])
        sonar("error")
        time.sleep(3)
        estado = "menu"
