"""
Wonder Hub - Pantalla "Mi Wonder" para el llavero

Arma una imagen de 160x128 con el Wonder personalizado (emocion + accesorios)
sobre el fondo oficial y la entrega en el mismo formato de los .raw del Pico:
RGB565, 2 bytes por pixel, byte alto primero (igual que inicio.raw).

Las imagenes salen de hub/recursos/ (son los PNG originales, sin modificar).
"""

import os

RECURSOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos")
W, H = 160, 128

EMOCIONES = ("base", "feliz", "enojado", "preocupado")
ACCESORIOS = ("bufanda", "gafas")          # en el orden en que se dibujan

ALTO_WONDER = 124                          # alto del lienzo del personaje en la pantalla
CENTRO_X = 80


def componer(emocion, accesorios):
    """Devuelve una imagen PIL RGB de 160x128."""
    from PIL import Image

    if emocion not in EMOCIONES:
        emocion = "base"
    fondo = Image.open(os.path.join(RECURSOS, "fondo_wonder.png")).convert("RGB").resize((W, H), Image.LANCZOS)
    capas = [emocion] + [a for a in ACCESORIOS if a in accesorios]
    personaje = None
    for capa in capas:
        img = Image.open(os.path.join(RECURSOS, f"wonder_{capa}.png")).convert("RGBA")
        personaje = img if personaje is None else Image.alpha_composite(personaje, img)
    personaje = personaje.resize((ALTO_WONDER, ALTO_WONDER), Image.LANCZOS)
    fondo.paste(personaje, (CENTRO_X - ALTO_WONDER // 2, H - ALTO_WONDER - 1), personaje)
    return fondo


def a_rgb565(imagen):
    """Imagen RGB -> bytes RGB565 (byte alto primero), listos para el framebuffer del Pico."""
    salida = bytearray(W * H * 2)
    i = 0
    for r, g, b in imagen.getdata():
        c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        salida[i] = c >> 8
        salida[i + 1] = c & 0xFF
        i += 2
    return bytes(salida)


def wonder_raw(emocion, accesorios):
    return a_rgb565(componer(emocion, accesorios))
