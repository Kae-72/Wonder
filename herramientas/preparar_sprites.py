"""
Wonder - Preparar sprites para el Pico  (se corre en el PC: Spyder -> F5)

Toma los PNG de la carpeta "sprites" y genera en "llavero" los archivos
que van al Pico. Los textos (nombres de las apps y "Pulsa O...") se dibujan con
TU fuente: pon el archivo .ttf u .otf dentro de "sprites".

Archivos que lee de "sprites":
    inicio_01.png, inicio_02.png, ...   pantalla de inicio (1 o varios frames), 160x128 o proporción 5:4
    fondo_menu.png                      fondo del carrusel (el del globo y el cuadro)
    icono_calendario.png                íconos (PNG con transparencia; se ajustan a 48x48)
    icono_pomodoro.png
    icono_grabadora.png
    fondo_calendario.png    (opcional)  fondo de la app de calendario
    tu_fuente.ttf / .otf    (opcional)  la fuente de Wonder

Necesita:  pip install pillow numpy   (en Anaconda ya vienen)
"""
import glob
import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ===== CONFIGURACIÓN =====
_AQUI = os.path.dirname(os.path.abspath(__file__))
ENTRADA = os.path.join(_AQUI, "sprites")                  # herramientas/sprites/
SALIDA = os.path.join(_AQUI, "..", "llavero")             # los .raw/.spr van directo al llavero
W, H = 160, 128                         # pantalla horizontal

APPS = [                                # (id del archivo, texto en el globo)
    ("calendario", "Calendario"),
    ("pomodoro", "Pomodoro"),
    ("grabadora", "Grabadora"),
]
TEXTO_INICIO = "Pulsa O para empezar"

# Medidas sobre el fondo del menú (en píxeles de la pantalla 160x128)
BURBUJA_CENTRO = (39, 17)               # centro del globo de texto
BURBUJA_MAX = (62, 22)                  # tamaño máximo del texto dentro del globo
ICONO_GRANDE = 44                       # ícono seleccionado (más el brillo alrededor)
ICONO_MINI = 22                         # íconos de los lados (no seleccionados)
BRILLO = 3                              # grosor del borde de selección
COLOR_BRILLO = (150, 215, 60)           # color del borde de selección (verde de la antena de Wonder)
COLOR_BRILLO_BORDE = (28, 51, 80)       # contorno fino del borde (para que resalte)
APAGADO = 0.35                          # cuánto se "apagan" los íconos de los lados (0 = nada)
COLOR_APAGADO = (104, 178, 255)         # hacia qué color se apagan (el azul del fondo)
INICIO_TEXTO_MAX = (118, 10)            # "Pulsa O..." más pequeño, va arriba

COLOR_TEXTO = (28, 51, 80)              # azul oscuro (el del contorno de la mascota)
COLOR_TEXTO_INICIO = (255, 255, 255)    # "Pulsa O..." en blanco con borde azul oscuro
# =========================

CLAVE = (255, 0, 255)                   # magenta = transparente (no lo uses en los dibujos)
CLAVE565 = 0xF81F


def a_565(img):
    """Imagen RGB -> bytes RGB565 big-endian (lo que espera la pantalla)."""
    a = np.asarray(img.convert("RGB"), dtype=np.uint16)
    c = ((a[:, :, 0] & 0xF8) << 8) | ((a[:, :, 1] & 0xFC) << 3) | (a[:, :, 2] >> 3)
    return c.astype(">u2").tobytes()


def a_565_con_clave(img_rgba, fondo):
    """RGBA -> RGB565. Los bordes suaves se mezclan con 'fondo'; lo transparente queda magenta."""
    rgba = np.asarray(img_rgba.convert("RGBA"), dtype=np.float32)
    alfa = rgba[:, :, 3:4] / 255.0
    rgb = rgba[:, :, :3] * alfa + np.array(fondo, dtype=np.float32) * (1 - alfa)
    rgb = rgb.round().astype(np.uint16)
    c = ((rgb[:, :, 0] & 0xF8) << 8) | ((rgb[:, :, 1] & 0xFC) << 3) | (rgb[:, :, 2] >> 3)
    c[c == CLAVE565] = CLAVE565 - 1                 # un píxel real nunca debe ser "transparente"
    c[rgba[:, :, 3] < 128] = CLAVE565
    return c.astype(">u2").tobytes()


def guardar_spr(nombre, w, h, datos):
    """Formato .spr: ancho y alto (2 bytes cada uno) + píxeles."""
    with open(os.path.join(SALIDA, nombre), "wb") as f:
        f.write(struct.pack(">HH", w, h))
        f.write(datos)
    return 4 + len(datos)


def recortar_transparente(img):
    """Quita el margen transparente que sobra alrededor del ícono."""
    caja = img.getchannel("A").point(lambda a: 255 if a > 20 else 0).getbbox()
    return img.crop(caja) if caja else img


def con_brillo(img):
    """Agrega un borde de selección que sigue la forma del ícono."""
    from PIL import ImageFilter
    m = BRILLO + 1
    lienzo = Image.new("RGBA", (img.width + 2 * m, img.height + 2 * m), (0, 0, 0, 0))
    alfa = Image.new("L", lienzo.size, 0)
    alfa.paste(img.getchannel("A"), (m, m))
    alfa = alfa.point(lambda a: 255 if a >= 128 else 0)
    exterior = alfa.filter(ImageFilter.MaxFilter(2 * m + 1))          # contorno fino oscuro
    medio = alfa.filter(ImageFilter.MaxFilter(2 * BRILLO + 1))        # brillo claro
    lienzo.paste(Image.new("RGBA", lienzo.size, COLOR_BRILLO_BORDE + (255,)), (0, 0), exterior)
    lienzo.paste(Image.new("RGBA", lienzo.size, COLOR_BRILLO + (255,)), (0, 0), medio)
    lienzo.alpha_composite(img, (m, m))
    return lienzo


def apagado(img):
    """Íconos no seleccionados: más pálidos, mezclados con el azul del fondo."""
    rgb = np.asarray(img, dtype=np.float32)
    rgb[:, :, :3] = rgb[:, :, :3] * (1 - APAGADO) + np.array(COLOR_APAGADO, dtype=np.float32) * APAGADO
    return Image.fromarray(rgb.round().astype(np.uint8), "RGBA")


def pantalla(ruta):
    img = Image.open(ruta).convert("RGB")
    if img.size != (W, H):
        img = ImageOps.fit(img, (W, H), Image.LANCZOS)
    return img


def buscar_fuente():
    propias = sorted(glob.glob(os.path.join(ENTRADA, "*.ttf")) + glob.glob(os.path.join(ENTRADA, "*.otf")))
    if propias:
        print("Fuente:", os.path.basename(propias[0]))
        return propias[0]
    for f in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            ImageFont.truetype(f, 10)
            print("Fuente: no encontré una .ttf/.otf en 'sprites', uso", f, "(provisional)")
            return f
        except OSError:
            pass
    print("Fuente: uso la básica de Pillow (provisional)")
    return None


def fuente(ruta, tam):
    if ruta is None:
        return ImageFont.load_default(size=tam)
    return ImageFont.truetype(ruta, tam)


def tam_que_cabe(ruta, textos, max_w, max_h, borde=0):
    for tam in range(40, 5, -1):
        f = fuente(ruta, tam)
        ok = True
        for t in textos:
            x0, y0, x1, y1 = f.getbbox(t, stroke_width=borde)
            if x1 - x0 > max_w or y1 - y0 > max_h:
                ok = False
                break
        if ok:
            return tam
    return 6


def texto_spr(nombre, texto, ruta, tam, color, fondo=None, borde=0, color_borde=None):
    f = fuente(ruta, tam)
    x0, y0, x1, y1 = f.getbbox(texto, stroke_width=borde)
    w, h = x1 - x0 + 2, y1 - y0 + 2
    if fondo is not None:                      # texto sobre un color liso (el globo): bordes suaves perfectos
        img = Image.new("RGB", (w, h), fondo)
        ImageDraw.Draw(img).text((1 - x0, 1 - y0), texto, font=f, fill=color)
        return guardar_spr(nombre, w, h, a_565(img)), (w, h)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))   # texto sobre la imagen: fondo transparente
    ImageDraw.Draw(img).text((1 - x0, 1 - y0), texto, font=f, fill=color + (255,),
                             stroke_width=borde, stroke_fill=color_borde + (255,))
    return guardar_spr(nombre, w, h, a_565_con_clave(img, color_borde)), (w, h)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(SALIDA, exist_ok=True)
    total = 0

    # 1) Inicio (uno o varios frames)
    frames = sorted(glob.glob(os.path.join(ENTRADA, "inicio*.png")))
    if not frames:
        raise SystemExit("Falta al menos sprites/inicio_01.png")
    with open(os.path.join(SALIDA, "inicio.raw"), "wb") as f:
        for r in frames:
            f.write(a_565(pantalla(r)))
    total += len(frames) * W * H * 2
    print(f"inicio.raw: {len(frames)} frame(s)")

    # 2) Fondo del menú
    menu = pantalla(os.path.join(ENTRADA, "fondo_menu.png"))
    with open(os.path.join(SALIDA, "fondo_menu.raw"), "wb") as f:
        f.write(a_565(menu))
    total += W * H * 2
    color_burbuja = menu.getpixel(BURBUJA_CENTRO)
    print("fondo_menu.raw  (color globo %s)" % (color_burbuja,))

    # 3) Fondo del calendario (opcional)
    ruta_cal = os.path.join(ENTRADA, "fondo_calendario.png")
    if os.path.exists(ruta_cal):
        with open(os.path.join(SALIDA, "fondo_calendario.raw"), "wb") as f:
            f.write(a_565(pantalla(ruta_cal)))
        total += W * H * 2
        print("fondo_calendario.raw")

    # 4) Íconos: grande con brillo (seleccionado) y mini apagado (a los lados)
    for app, _ in APPS:
        ruta = os.path.join(ENTRADA, f"icono_{app}.png")
        if not os.path.exists(ruta):
            print(f"  ! falta {ruta} (en el Pico se verá un cuadro de relleno)")
            continue
        original = recortar_transparente(Image.open(ruta).convert("RGBA"))

        grande = con_brillo(ImageOps.contain(original, (ICONO_GRANDE, ICONO_GRANDE), Image.LANCZOS))
        total += guardar_spr(f"icono_{app}.spr", grande.width, grande.height,
                             a_565_con_clave(grande, COLOR_APAGADO))

        mini = apagado(ImageOps.contain(original, (ICONO_MINI, ICONO_MINI), Image.LANCZOS))
        total += guardar_spr(f"icono_{app}_mini.spr", mini.width, mini.height,
                             a_565_con_clave(mini, COLOR_APAGADO))
        print(f"icono_{app}.spr {grande.width}x{grande.height}  +  icono_{app}_mini.spr {mini.width}x{mini.height}")

    # 5) Textos con la fuente
    ruta_f = buscar_fuente()
    tam = tam_que_cabe(ruta_f, [t for _, t in APPS], *BURBUJA_MAX)
    for app, texto in APPS:
        n, (w, h) = texto_spr(f"nombre_{app}.spr", texto, ruta_f, tam, COLOR_TEXTO, fondo=color_burbuja)
        total += n
        print(f"nombre_{app}.spr  '{texto}' {w}x{h} (tamaño {tam})")
    tam_i = tam_que_cabe(ruta_f, [TEXTO_INICIO], *INICIO_TEXTO_MAX, borde=1)
    n, (w, h) = texto_spr("texto_inicio.spr", TEXTO_INICIO, ruta_f, tam_i, COLOR_TEXTO_INICIO,
                          borde=1, color_borde=COLOR_TEXTO)
    total += n
    print(f"texto_inicio.spr  {w}x{h}")

    print(f"\nListo: {total // 1024} KB en la carpeta '{SALIDA}'. Sube TODO su contenido al Pico.")


if __name__ == "__main__":
    main()
