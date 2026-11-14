# Calendario Wonder en la pantalla - Pico 2 W (MicroPython)
# Pide los eventos al PC (calendar_backend.py --servir) por WiFi y los muestra en la pantalla.
#
# Botones: IZQUIERDA / DERECHA = página anterior / siguiente   SELECCIONAR = actualizar ahora
# Pines: los mismos de siempre (pantalla GP0,1,2,5,18,19 · botones GP14, GP15, GP17)

from machine import Pin, SPI
import framebuf
import network
import time
import json

try:
    import requests
except ImportError:
    import urequests as requests

# ===== CONFIGURACIÓN (no subas este archivo a GitHub con tu clave de WiFi) =====
WIFI_NOMBRE = "iphone de paula"
WIFI_CLAVE = "gh9sbpthp3bv"
SERVIDOR = "http://192.168.1.50:8000/eventos"   # la IP que imprime calendar_backend.py
CLAVE = "123456789"                      # la misma CLAVE del backend
REFRESCO_SEG = 300
HORIZONTAL = 0x60       # si se ve de cabeza: 0xA0
# ===============================================================================

# ---------- Pantalla ----------
spi = SPI(0, baudrate=20_000_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
cs = Pin(0, Pin.OUT, value=1)
dc = Pin(1, Pin.OUT, value=0)
rst = Pin(2, Pin.OUT, value=1)
bl = Pin(5, Pin.OUT, value=1)

W, H = 160, 128
lienzo = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(lienzo, W, H, framebuf.RGB565)


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
    cmd(0x2A, bytes((0, 0, 0, W - 1)))
    cmd(0x2B, bytes((0, 0, 0, H - 1)))
    cmd(0x2C)
    cs.value(0); dc.value(1)
    spi.write(lienzo)
    cs.value(1)


def color(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


# Paleta Wonder
FONDO = color(30, 57, 79)
BARRA = color(18, 40, 60)
CLARO = color(220, 235, 250)
ACENTO = color(120, 190, 255)
GRIS = color(130, 160, 185)


def mensaje(titulo, linea2=""):
    fb.fill(FONDO)
    fb.text(titulo[:20], 4, 52, CLARO)
    fb.text(linea2[:20], 4, 66, GRIS)
    mostrar()


# ---------- WiFi y datos ----------
wlan = network.WLAN(network.STA_IF)


def conectar_wifi():
    if wlan.isconnected():
        return True
    wlan.active(True)
    wlan.connect(WIFI_NOMBRE, WIFI_CLAVE)
    for i in range(20):
        if wlan.isconnected():
            print("WiFi OK:", wlan.ifconfig()[0])
            return True
        mensaje("Conectando WiFi" + "." * (i % 4), WIFI_NOMBRE)
        time.sleep(1)
    return False


def pedir_eventos():
    r = requests.get(SERVIDOR, headers={"X-Wonder-Key": CLAVE})
    try:
        if r.status_code != 200:
            raise ValueError("HTTP %d" % r.status_code)
        return json.loads(r.text)
    finally:
        r.close()


# ---------- Dibujo del calendario ----------
POR_PAGINA = 5          # cada evento ocupa 2 líneas


def partir(texto, ancho):
    return texto[:ancho] if len(texto) <= ancho else texto[:ancho - 1] + "~"


def dibujar(datos, pagina):
    eventos = datos.get("eventos", [])
    paginas = max(1, (len(eventos) + POR_PAGINA - 1) // POR_PAGINA)
    pagina = min(pagina, paginas - 1)

    fb.fill(FONDO)
    fb.fill_rect(0, 0, W, 14, BARRA)
    fb.text("MI CALENDARIO", 3, 3, CLARO)
    fb.text(datos.get("hora", ""), W - 42, 3, ACENTO)

    if not eventos:
        fb.text("Sin eventos esta", 8, 52, CLARO)
        fb.text("semana :)", 8, 64, CLARO)
    else:
        y = 18
        for ev in eventos[pagina * POR_PAGINA:(pagina + 1) * POR_PAGINA]:
            fb.text("%s %s %s" % (ev["dia"], ev["fecha"], ev["hora"]), 3, y, ACENTO)
            fb.text(partir(ev["titulo"], 19), 3, y + 10, CLARO)
            y += 21

    fb.text("%d/%d" % (pagina + 1, paginas), W - 26, H - 9, GRIS)
    mostrar()
    return pagina


# ---------- Botones ----------
btn_izq = Pin(14, Pin.IN, Pin.PULL_UP)
btn_sel = Pin(15, Pin.IN, Pin.PULL_UP)
btn_der = Pin(17, Pin.IN, Pin.PULL_UP)
ultimo = {14: 1, 15: 1, 17: 1}


def presionado(boton, num):
    v = boton.value()
    nuevo = v == 0 and ultimo[num] == 1
    ultimo[num] = v
    return nuevo


# ---------- Programa ----------
init_pantalla()
datos = {"eventos": [], "hora": ""}
pagina = 0
t_ultimo = -REFRESCO_SEG * 1000
forzar = True

while True:
    if forzar or time.ticks_diff(time.ticks_ms(), t_ultimo) > REFRESCO_SEG * 1000:
        forzar = False
        t_ultimo = time.ticks_ms()
        if not conectar_wifi():
            mensaje("Sin WiFi", "Revisa nombre/clave")
        else:
            try:
                mensaje("Actualizando...", "")
                datos = pedir_eventos()
                print("Eventos recibidos:", len(datos.get("eventos", [])))
            except Exception as e:
                print("Error pidiendo eventos:", e)
                mensaje("Sin conexion al PC", "Corre --servir")
                time.sleep(2)
        pagina = dibujar(datos, pagina)

    if presionado(btn_der, 17):
        pagina = dibujar(datos, pagina + 1)
    if presionado(btn_izq, 14):
        pagina = dibujar(datos, max(0, pagina - 1))
    if presionado(btn_sel, 15):
        forzar = True
    time.sleep_ms(30)
