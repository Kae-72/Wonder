"""Convierte imágenes grandes (p. ej. 1600x1280) a pantallas .raw de 160x128 en RGB565.
Solo cambia tamaño y formato: no redibuja ni recolorea.

Uso:  python convertir_fondos.py imagen1.png salida1.raw [imagen2.png salida2.raw ...]
Ej.:  python convertir_fondos.py Pomodoro.png ../llavero/fondo_pomodoro.raw
"""
import sys, numpy as np
from PIL import Image, ImageOps
W, H = 160, 128
def a_565(img):
    a = np.asarray(img.convert("RGB")).astype(np.uint16)
    c = ((a[:, :, 0] >> 3) << 11) | ((a[:, :, 1] >> 2) << 5) | (a[:, :, 2] >> 3)
    return c.astype(">u2").tobytes()
for origen, destino in zip(sys.argv[1::2], sys.argv[2::2]):
    img = Image.open(origen).convert("RGBA")
    fondo = Image.new("RGBA", img.size, (255, 255, 255, 255)); fondo.alpha_composite(img)
    img = ImageOps.fit(fondo.convert("RGB"), (W, H), Image.LANCZOS)
    open(destino, "wb").write(a_565(img)); img.save(destino + ".png")
    print(destino, len(open(destino, "rb").read()))
