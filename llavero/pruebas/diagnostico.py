# Wonder - DIAGNÓSTICO de botones y parlante
# Ábrelo en Thonny y pulsa Run. Mira la pantalla del llavero y el Shell de Thonny.
#
# Parte 1 (30 segundos): pulsa VARIAS VECES el botón del centro y el de la derecha.
#   Se muestra cualquier pin que cambie, aunque no sea un pin "de botón".
# Parte 2: suenan 7 tonos, de grave a agudo. Anota cuáles oyes.

from machine import Pin, SPI
import framebuf
import time

W, H = 160, 128

# Todos los pines que se pueden leer sin molestar a la pantalla ni al WiFi
PINES = (3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21, 22, 26, 27, 28)

spi = SPI(0, baudrate=20_000_000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(19))
cs = Pin(0, Pin.OUT, value=1)
dc = Pin(1, Pin.OUT, value=0)
rst = Pin(2, Pin.OUT, value=1)
bl = Pin(5, Pin.OUT, value=1)
buf = bytearray(W * H * 2)
fb = framebuf.FrameBuffer(buf, W, H, framebuf.RGB565)


def cmd(c, data=None):
    cs.value(0); dc.value(0)
    spi.write(bytes((c,)))
    if data:
        dc.value(1)
        spi.write(data)
    cs.value(1)


def iniciar_pantalla():
    rst.value(0); time.sleep_ms(50)
    rst.value(1); time.sleep_ms(150)
    cmd(0x01); time.sleep_ms(150)
    cmd(0x11); time.sleep_ms(255)
    cmd(0xB1, b"\x01\x2C\x2D"); cmd(0xB2, b"\x01\x2C\x2D"); cmd(0xB3, b"\x01\x2C\x2D\x01\x2C\x2D")
    cmd(0xB4, b"\x07"); cmd(0xC0, b"\xA2\x02\x84"); cmd(0xC1, b"\xC5"); cmd(0xC2, b"\x0A\x00")
    cmd(0xC3, b"\x8A\x2A"); cmd(0xC4, b"\x8A\xEE"); cmd(0xC5, b"\x0E")
    cmd(0x20); cmd(0x3A, b"\x05"); cmd(0x36, b"\x60")
    cmd(0x13); cmd(0x29); time.sleep_ms(100)


def mostrar():
    cmd(0x2A, bytes((0, 0, 0, W - 1)))
    cmd(0x2B, bytes((0, 0, 0, H - 1)))
    cmd(0x2C)
    cs.value(0); dc.value(1)
    spi.write(buf)
    cs.value(1)


def color(r, g, b):
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


AZUL, NAVY = color(104, 178, 255), color(28, 51, 80)
BLANCO, AMARILLO = color(255, 255, 255), color(255, 220, 0)


def pantalla(titulo, *lineas):
    fb.fill(AZUL)
    fb.fill_rect(0, 0, W, 14, NAVY)
    fb.text(titulo, 3, 3, BLANCO)
    y = 22
    for l in lineas:
        fb.text(l, 4, y, NAVY)
        y += 12
    mostrar()


iniciar_pantalla()

# ---------------- Parte 1: pines ----------------
p = {n: Pin(n, Pin.IN, Pin.PULL_UP) for n in PINES}
time.sleep_ms(50)
en_cero = [n for n in PINES if p[n].value() == 0]
print()
print("PARTE 1 - Pines que están en 0 SIN pulsar nada:", ["GP%d" % n for n in en_cero] or "ninguno")
print("Ahora pulsa varias veces el CENTRO y la DERECHA (30 segundos)...")

antes = {n: p[n].value() for n in PINES}
cambios = {}
ultimo = "nada aun"
fin = time.ticks_add(time.ticks_ms(), 30000)
t_dibujo = 0
while time.ticks_diff(fin, time.ticks_ms()) > 0:
    for n in PINES:
        v = p[n].value()
        if v != antes[n]:
            antes[n] = v
            if v == 0:
                cambios[n] = cambios.get(n, 0) + 1
                ultimo = "GP%d" % n
                print("  GP%d se activó (%d veces)" % (n, cambios[n]))
    if time.ticks_diff(time.ticks_ms(), t_dibujo) > 300:
        t_dibujo = time.ticks_ms()
        seg = time.ticks_diff(fin, time.ticks_ms()) // 1000
        pantalla("1/2 BOTONES  %ds" % seg,
                 "Pulsa CENTRO y",
                 "DERECHA varias",
                 "veces.",
                 "",
                 "Ultimo: " + ultimo,
                 "En 0: " + (",".join(str(n) for n in en_cero) or "-"))
    time.sleep_ms(5)

print()
print("RESUMEN PARTE 1")
print("  Siempre en 0:", ["GP%d" % n for n in en_cero] or "ninguno")
print("  Se activaron:", {"GP%d" % n: c for n, c in cambios.items()} or "ninguno")

# ---------------- Parte 2: tonos ----------------
import sonidos
sonidos.iniciar()
TONOS = (("1 Do grave", sonidos.C4), ("2 Sol grave", sonidos.G4), ("3 Do medio", sonidos.C5),
         ("4 Sol medio", sonidos.G5), ("5 Do agudo", sonidos.C6), ("6 Sol agudo", sonidos.G6),
         ("7 Do muy agudo", sonidos.C7))
print()
print("PARTE 2 - Escucha y anota hasta qué número oyes")
for vuelta in range(2):
    for nombre, f in TONOS:
        print("  Tono", nombre, "(%d Hz)" % f)
        pantalla("2/2 PARLANTE", "Sonando:", "", nombre, "(%d Hz)" % f)
        sonidos.tocar([(f, 700, sonidos.P50, .9, .9)])
        sonidos.esperar()
        time.sleep_ms(400)
pantalla("LISTO", "Mandale a Claude", "lo que salio en", "Thonny")
print()
print("Listo. Copia todo lo que salió desde PARTE 1.")
