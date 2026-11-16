"""
Wonder - prepara las imágenes del inventario (menú "Wonder") y los fondos de la grabadora.
Solo cambia tamaño, formato y junta capas: no redibuja ni recolorea.

Uso (en el PC):  python preparar_inventario.py CARPETA_EMOCIONES CARPETA_CHAPITAS CARPETA_TIEMPOS ACCESORIOS
  CARPETA_EMOCIONES: Fondo_inventario.png, Wonde_base_lowres.png, Wonder_happpy_lowres.png,
                     Wonder_sad_lowres.png, Wonder_enojado_lowres.png
  CARPETA_CHAPITAS:  Blanco_translucido.png, Wonder_Escuchando_suelto/atardecer/noche.png
  CARPETA_TIEMPOS:   Dia_xp.png, Atardecer.png, Noche.png
  ACCESORIOS:        gafas_1600.png, bufanda_1600.png (ya ubicadas sobre el Wonder de 1600x1280)
Escribe en ../llavero/ y muestra las posiciones (x, y) que usa main.py.
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageOps

W, H = 160, 128
CLAVE565 = 0xF81F
AQUI = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(AQUI, "..", "llavero")


def a_565(img):
    a = np.asarray(img.convert("RGB"), dtype=np.uint16)
    c = ((a[:, :, 0] & 0xF8) << 8) | ((a[:, :, 1] & 0xFC) << 3) | (a[:, :, 2] >> 3)
    return c.astype(">u2").tobytes()


def a_565_con_clave(rgba_img, borde=(205, 225, 240)):
    rgba = np.asarray(rgba_img.convert("RGBA"), dtype=np.float32)
    alfa = rgba[:, :, 3:4] / 255.0
    rgb = (rgba[:, :, :3] * alfa + np.array(borde, np.float32) * (1 - alfa)).round().astype(np.uint16)
    c = ((rgb[:, :, 0] & 0xF8) << 8) | ((rgb[:, :, 1] & 0xFC) << 3) | (rgb[:, :, 2] >> 3)
    c[c == CLAVE565] = CLAVE565 - 1
    c[rgba[:, :, 3] < 110] = CLAVE565
    return c.astype(">u2").tobytes()


def pantalla(img):
    return ImageOps.fit(img.convert("RGBA"), (W, H), Image.LANCZOS)


def guardar_raw(img, nombre):
    with open(os.path.join(SALIDA, nombre), "wb") as f:
        f.write(a_565(pantalla(img)))
    print(nombre)


def guardar_spr(img_1600, nombre):
    """Recorta lo visible de una capa 1600x1280 ya reducida a 160x128. Devuelve (x, y)."""
    p = pantalla(img_1600)
    a = np.asarray(p)[:, :, 3]
    ys, xs = np.nonzero(a >= 110)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    trozo = p.crop((x0, y0, x1, y1))
    with open(os.path.join(SALIDA, nombre), "wb") as f:
        f.write(struct.pack(">HH", x1 - x0, y1 - y0) + a_565_con_clave(trozo))
    print(nombre, "pos", (int(x0), int(y0)), "tam", (int(x1 - x0), int(y1 - y0)))
    return int(x0), int(y0)


def abrir(*partes):
    return Image.open(os.path.join(*partes)).convert("RGBA")


if __name__ == "__main__":
    emo, chap, tiempos, acc = sys.argv[1:5]
    guardar_raw(abrir(emo, "Fondo_inventario.png"), "fondo_inventario.raw")
    for archivo, nombre in (("Wonde_base_lowres.png", "base"), ("Wonder_happpy_lowres.png", "feliz"),
                            ("Wonder_sad_lowres.png", "triste"), ("Wonder_enojado_lowres.png", "enojado")):
        guardar_spr(abrir(emo, archivo), "wonder_%s.spr" % nombre)
    guardar_spr(abrir(acc, "gafas_1600.png"), "acc_gafas.spr")
    guardar_spr(abrir(acc, "bufanda_1600.png"), "acc_bufanda.spr")
    blanco = abrir(chap, "Blanco_translucido.png")
    for cielo, wonder, momento in (("Dia_xp.png", "Wonder_Escuchando_suelto.png", "dia"),
                                   ("Atardecer.png", "Wonder_Escuchando_atardecer.png", "tarde"),
                                   ("Noche.png", "Wonder_Escuchando_noche.png", "noche")):
        capa = abrir(tiempos, cielo)
        capa.alpha_composite(blanco.resize(capa.size))
        capa.alpha_composite(abrir(chap, wonder).resize(capa.size))
        guardar_raw(capa, "fondo_grabadora_%s.raw" % momento)
