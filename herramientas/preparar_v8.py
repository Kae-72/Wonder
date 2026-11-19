"""
Wonder - sprites de la v8  (se corre en el PC: Spyder -> F5)

Genera en la carpeta "llavero":
  - comida_<id>.spr (48x48) y comida_<id>_mini.spr (16x16)   <- sprites_v8/comida_<id>.png
  - icono_ajustes.spr, icono_ajustes_mini.spr, nombre_ajustes.spr  <- sprites_v8/icono_ajustes.png
  - icono_juego_<id>.spr, icono_juego_<id>_mini.spr, nombre_juego_<id>.spr
      El logo de cada juego SALE DEL PROPIO JUEGO: se corre la ROM (juego_<id>.ch8)
      en el intérprete de Wonder y se toma una foto de su pantalla.

Necesita:  pip install pillow numpy
"""
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageOps

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import preparar_sprites as ps                     # noqa: E402  (mismas funciones de siempre)

ENTRADA = os.path.join(_AQUI, "sprites_v8")
LLAVERO = os.path.join(_AQUI, "..", "llavero")
FUENTES = ("arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf")


def _fuente_menu():
    """La misma letra de los nombres del menú que ya están (Arial negrita)."""
    from PIL import ImageFont
    for f in FUENTES:
        try:
            ImageFont.truetype(f, 10)
            return f
        except OSError:
            pass
    return None


FUENTE = _fuente_menu()
ps.SALIDA = LLAVERO

COMIDAS = ("mailo", "arepa", "changua")
FONDO_PANEL = (220, 234, 255)                     # CLARO de main.py (donde se ven las comidas)
NOMBRE_AJUSTES = "Configurar"

# id: (nombre en el menú, color, fondo, cuadro de la foto, recorte x0, y0, x1, y1 en 128x64)
JUEGOS = {
    "br8kout": ("Br8kout", (255, 132, 254), (202, 37, 83), 150, (32, 0, 96, 64)),
    "flightrunner": ("Flight Runner", (255, 204, 0), (0, 0, 255), 99, (0, 0, 64, 64)),
    "piper": ("Piper", (255, 204, 0), (0, 0, 255), 30, (8, 0, 72, 64)),
    "sweetcopter": ("Sw8 Copter", (255, 255, 255), (17, 119, 153), 30, (32, 0, 96, 64)),
}


def color_burbuja():
    """El color exacto del globo del menú (se toma de nombre_wonder.spr)."""
    with open(os.path.join(LLAVERO, "nombre_wonder.spr"), "rb") as f:
        f.read(4)
        v = struct.unpack(">H", f.read(2))[0]
    return (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)


def tam_para(texto, max_w=64, max_h=11):
    for tam in range(10, 5, -1):
        x0, y0, x1, y1 = ps.fuente(FUENTE, tam).getbbox(texto)
        if x1 - x0 + 2 <= max_w and y1 - y0 + 2 <= max_h:
            return tam
    return 6


def icono_menu(original, nombre):
    """Igual que los íconos de siempre: grande con brillo + mini apagado."""
    grande = ps.con_brillo(ImageOps.contain(original, (ps.ICONO_GRANDE, ps.ICONO_GRANDE), Image.LANCZOS))
    ps.guardar_spr(nombre + ".spr", grande.width, grande.height,
                   ps.a_565_con_clave(grande, ps.COLOR_APAGADO))
    mini = ps.apagado(ImageOps.contain(original, (ps.ICONO_MINI, ps.ICONO_MINI), Image.LANCZOS))
    ps.guardar_spr(nombre + "_mini.spr", mini.width, mini.height,
                   ps.a_565_con_clave(mini, ps.COLOR_APAGADO))
    print(f"{nombre}.spr {grande.size}  + mini {mini.size}")


def foto_juego(ident, cuadro, color, fondo):
    """Corre el juego unos segundos (sin tocar nada) y devuelve su pantalla."""
    sys.path.insert(0, LLAVERO)
    import chip8
    with open(os.path.join(LLAVERO, "juego_%s.ch8" % ident), "rb") as f:
        rom = f.read()
    m = chip8.Maquina(rom, 15, 1, 0)
    m.por_cuadro = {"br8kout": 7, "flightrunner": 15, "piper": 200, "sweetcopter": 100}[ident]
    m.sembrar(1234)
    for _ in range(cuadro):
        m.cuadro(0)
    m.pintar()
    a = np.frombuffer(bytes(m.pant), dtype="<u2").reshape(64, 128)
    img = np.zeros((64, 128, 3), np.uint8)
    img[:] = fondo
    img[a == 1] = color
    return Image.fromarray(img)


def main():
    burbuja = color_burbuja()
    # 1) Comidas
    for c in COMIDAS:
        ruta = os.path.join(ENTRADA, "comida_%s.png" % c)
        if not os.path.exists(ruta):
            print("  ! falta", ruta)
            continue
        img = ps.recortar_transparente(Image.open(ruta).convert("RGBA"))
        for nombre, lado in (("comida_%s" % c, 48), ("comida_%s_mini" % c, 16)):
            peq = ImageOps.contain(img, (lado, lado), Image.LANCZOS)
            ps.guardar_spr(nombre + ".spr", peq.width, peq.height, ps.a_565_con_clave(peq, FONDO_PANEL))
            print(f"{nombre}.spr {peq.size}")
    # 2) Configuración
    ruta = os.path.join(ENTRADA, "icono_ajustes.png")
    icono_menu(ps.recortar_transparente(Image.open(ruta).convert("RGBA")), "icono_ajustes")
    ps.texto_spr("nombre_ajustes.spr", NOMBRE_AJUSTES, FUENTE, tam_para(NOMBRE_AJUSTES),
                 ps.COLOR_TEXTO, fondo=burbuja)
    ps.texto_spr("nombre_wonder.spr", "Wonder", FUENTE, tam_para("Wonder"), ps.COLOR_TEXTO, fondo=burbuja)
    # 3) Juegos: el logo sale de la pantalla del propio juego
    for ident, (nombre, color, fondo, cuadro, caja) in JUEGOS.items():
        foto = foto_juego(ident, cuadro, color, fondo).crop(caja)
        foto = foto.resize((40, 40), Image.NEAREST)
        marco = Image.new("RGBA", (42, 42), ps.COLOR_TEXTO + (255,))
        marco.paste(foto, (1, 1))
        icono_menu(marco, "icono_juego_%s" % ident)
        ps.texto_spr("nombre_juego_%s.spr" % ident, nombre, FUENTE, tam_para(nombre),
                     ps.COLOR_TEXTO, fondo=burbuja)
        foto.resize((160, 160), Image.NEAREST).save(os.path.join(_AQUI, "sprites_v8", "logo_%s.png" % ident))
    print("\nListo. Sube al Pico los .spr nuevos.")


if __name__ == "__main__":
    main()
