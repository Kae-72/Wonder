# Wonder - PRUEBA 2: encontrar los botones y probar el parlante
#
# Antes: sube sonidos.py al Pico (la prueba lo usa).
# Después: abre este archivo en Thonny y pulsa Run (F5).
#
# La prueba te guía en la pantalla:
#   1. PARLANTE: suena el arranque de Wonder (si no suena, ver abajo en Thonny).
#   2. BOTONES: te pide pulsar IZQ, CENTRO y DER, y averigua a qué pin va cada uno.
#   3. SONIDOS: guarda lo encontrado en pines.json y te deja jugar con los botones.
#      (mantener IZQ + DER a la vez = tocar todos los sonidos)
# main.py lee pines.json solo.

from machine import Pin, SPI
import framebuf
import time
import json
import sonidos

W, H = 160, 128
HORIZONTAL = 0x60

# Pines donde PODRÍA haber un botón (no se tocan los de la pantalla ni los internos del WiFi)
CANDIDATOS_BOTON = (3, 4, 9, 10, 11, 12, 13, 14, 15, 16, 17, 27, 28)

# ---------------- Pantalla ----------------
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
    cmd(0x20); cmd(0x3A, b"\x05"); cmd(0x36, bytes((HORIZONTAL,)))
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


AZUL = color(104, 178, 255)
NAVY = color(28, 51, 80)
BLANCO = color(255, 255, 255)
AMARILLO = color(255, 220, 0)


def pantalla(titulo, *lineas, grande=None):
    fb.fill(AZUL)
    fb.fill_rect(0, 0, W, 14, NAVY)
    fb.text(titulo, 3, 3, BLANCO)
    y = 24
    for l in lineas:
        fb.text(l, 4, y, NAVY)
        y += 12
    if grande:
        fb.fill_rect(10, 88, W - 20, 26, NAVY)
        fb.text(grande, (W - len(grande) * 8) // 2, 97, AMARILLO)
    mostrar()


# ---------------- 1. Botones ----------------
def leer_todos(pines):
    return {n: p.value() for n, p in pines.items()}


def esperar_boton(pines, ignorar, segundos):
    """Devuelve el número de GP que bajó a 0 (y se mantuvo 40 ms), o None."""
    base = leer_todos(pines)
    fin = time.ticks_add(time.ticks_ms(), segundos * 1000)
    while time.ticks_diff(fin, time.ticks_ms()) > 0:
        for n, p in pines.items():
            if n in ignorar or base[n] == 0:
                continue
            if p.value() == 0:
                time.sleep_ms(40)
                if p.value() == 0:
                    return n
        time.sleep_ms(5)
    return None


def esperar_soltar(pines):
    while any(p.value() == 0 for p in pines.values()):
        time.sleep_ms(10)
    time.sleep_ms(80)


def buscar_botones():
    pines = {n: Pin(n, Pin.IN, Pin.PULL_UP) for n in CANDIDATOS_BOTON}
    time.sleep_ms(50)
    pegados = [n for n, v in leer_todos(pines).items() if v == 0]
    if pegados:
        print("Ojo: estos pines ya estaban en 0 (se ignoran):", pegados)
    encontrados = {}
    for clave, nombre in (("izq", "IZQUIERDA"), ("o", "CENTRO (O)"), ("der", "DERECHA")):
        pantalla("1/3 BOTONES", "Pulsa el boton", "de la", nombre, "(tienes 15 seg)")
        print("Pulsa:", nombre)
        n = esperar_boton(pines, encontrados.values(), 15)
        if n is None:
            print("  ->", nombre, "NO respondió en ningún pin")
            pantalla("1/3 BOTONES", nombre, "no respondio", "", "Revisa su soldadura", grande="SIN SENAL")
            time.sleep(2)
        else:
            encontrados[clave] = n
            print("  ->", nombre, "= GP%d" % n)
            pantalla("1/3 BOTONES", nombre, "esta en el pin", "", "", grande="GP%d" % n)
            esperar_soltar(pines)
            time.sleep_ms(600)
    return encontrados


# ---------------- 3. Jugar con los sonidos ----------------
def jugar(botones):
    sonidos.encender()
    b = {k: Pin(n, Pin.IN, Pin.PULL_UP) for k, n in botones.items()}
    antes = {k: 1 for k in b}
    t0 = {k: 0 for k in b}
    largo = {k: False for k in b}
    pos = 0
    pantalla("3/3 SONIDOS", "IZQ/DER: moverse", "O: seleccionar", "mantener O: volver", grande="pos %d" % pos)
    print("Juega con los botones. Stop en Thonny para salir.")
    while True:
        ahora = time.ticks_ms()
        if "izq" in b and "der" in b and b["izq"].value() == 0 and b["der"].value() == 0:
            pantalla("3/3 SONIDOS", "Tocando todos", "los sonidos...", "(mira Thonny)")
            sonidos.demo()
            pantalla("3/3 SONIDOS", "IZQ/DER: moverse", "O: seleccionar", "mantener O: volver", grande="pos %d" % pos)
        for k, p in b.items():
            v = p.value()
            if v == 0 and antes[k] == 1:
                t0[k] = ahora
                largo[k] = False
                if k in ("izq", "der"):
                    paso = -1 if k == "izq" else 1
                    pos += paso
                    sonidos.mover(paso, pos)
                    pantalla("3/3 SONIDOS", "IZQ/DER: moverse", "O: seleccionar", "mantener O: volver",
                             grande="pos %d" % pos)
            elif v == 0 and k == "o" and not largo[k] and time.ticks_diff(ahora, t0[k]) > 700:
                largo[k] = True
                sonidos.volver()
                pantalla("3/3 SONIDOS", "", "", "", grande="VOLVER")
            elif v == 1 and antes[k] == 0 and k == "o" and not largo[k]:
                sonidos.seleccionar()
                pantalla("3/3 SONIDOS", "", "", "", grande="SELECCIONAR")
            antes[k] = v
        time.sleep_ms(10)


# ---------------- Programa ----------------
iniciar_pantalla()
sonidos.iniciar()
pantalla("PARLANTE", "Deberia sonar", "el arranque", "de Wonder...")
print("Si no suena: revisa el parlante en la bornera del amplificador,")
print("y que el amplificador tenga VSYS y GND. Puedes subir VOLUMEN en sonidos.py.")
sonidos.encender()
sonidos.esperar()
time.sleep(1)

botones = buscar_botones()
resultado = {"izq": botones.get("izq"), "o": botones.get("o"), "der": botones.get("der")}
with open("pines.json", "w") as f:
    json.dump(resultado, f)

print()
print("=========== RESULTADO (guardado en pines.json) ===========")
for k, nombre in (("izq", "Botón IZQUIERDA"), ("o", "Botón CENTRO   "), ("der", "Botón DERECHA  ")):
    v = resultado[k]
    print(nombre, ":", "GP%d" % v if v is not None else "NO ENCONTRADO")
print("===========================================================")

pantalla("RESULTADO",
         "IZQ : " + ("GP%d" % resultado["izq"] if resultado["izq"] is not None else "--"),
         "O   : " + ("GP%d" % resultado["o"] if resultado["o"] is not None else "--"),
         "DER : " + ("GP%d" % resultado["der"] if resultado["der"] is not None else "--"))
time.sleep(3)

if botones:
    jugar(botones)
else:
    print("Ningún botón respondió; toco todos los sonidos.")
    sonidos.demo()
