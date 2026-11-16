"""Uso: python juntar_capas.py cielo.png pomodoro_ventana_transparente.png ../llavero/fondo_pomodoro_dia.raw
       python juntar_capas.py Wonder_dia.png ../llavero/fondo_descanso_dia.raw
"""
# Junta capas (cielo detrás + pomodoro con ventana transparente) y convierte a .raw 160x128 RGB565.
# Solo superpone y cambia tamaño/formato: no redibuja ni recolorea.
import sys, numpy as np
from PIL import Image, ImageOps
W, H = 160, 128
def a_565(img):
    a = np.asarray(img.convert("RGB")).astype(np.uint16)
    c = ((a[:, :, 0] >> 3) << 11) | ((a[:, :, 1] >> 2) << 5) | (a[:, :, 2] >> 3)
    return c.astype(">u2").tobytes()
def guardar(img, destino):
    img = ImageOps.fit(img.convert("RGB"), (W, H), Image.LANCZOS)
    open(destino, "wb").write(a_565(img)); img.save(destino + ".png")
if __name__ == "__main__":
    # uso: capas.py fondo.png encima.png salida.raw   |  capas.py imagen.png salida.raw
    if len(sys.argv) == 4:
        fondo = Image.open(sys.argv[1]).convert("RGBA")
        encima = Image.open(sys.argv[2]).convert("RGBA").resize(fondo.size, Image.LANCZOS)
        fondo.alpha_composite(encima)
        guardar(fondo, sys.argv[3])
    else:
        guardar(Image.open(sys.argv[1]).convert("RGBA"), sys.argv[2])
