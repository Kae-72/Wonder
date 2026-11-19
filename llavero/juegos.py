# Wonder - menú Juegos
#
# Los juegos son de CHIP-8 (una consola de 1977) y salen del archivo chip8Archive
# (github.com/JohnEarnest/chip8Archive). Todo ese archivo está en DOMINIO PÚBLICO
# (licencia CC0): se pueden usar, cambiar y compartir libremente. Igual damos
# crédito a sus autores en la pantalla de cada juego.
#
# Reglas de Wonder:
#   - Jugar NO gasta energía, pero hace falta tener al menos 25 %.
#   - Tienes UN juego a la vez (el del menú). Cambia al azar cuando pierdes la racha.
#   - Con la energía al 100 % puedes pagar 50 % para cambiarlo por otro.
#
# Botones en la pantalla del juego:  O = jugar,  IZQ / DER = ver los otros juegos,
# mantener O = volver.  Dentro del juego: mantener IZQ + DER 1 segundo = salir.

import time
import gc
import sys
import __main__ as M

# Teclas CHIP-8: el teclado original tiene 16 (0-F). Estos juegos usan:
#   5 arriba, 7 izquierda, 8 abajo, 9 derecha, 6 acción  (como W A S D E en Octo)
# id: (nombre, autores, instrucciones por cuadro, teclas IZQ/O/DER, color, fondo, ayuda)
INFO = {
    "br8kout": ("Br8kout", "SharpenedSpoon", 7, (7, 6, 9), (255, 132, 254), (202, 37, 83),
                ("IZQ / DER: mover", "Rompe todos los", "ladrillos!")),
    "flightrunner": ("Flight Runner", "TodPunk", 15, (7, 6, 9), (255, 204, 0), (0, 0, 255),
                     ("IZQ / DER: subir", "y bajar la nave.", "No choques!")),
    "piper": ("Piper", "Aeris, Mecom, Wang", 200, (7, 6, 9), (255, 204, 0), (0, 0, 255),
              ("IZQ / DER: caminar", "O + IZQ: subir", "O + DER: bajar", "O: esconderse")),
    "sweetcopter": ("Sw8 Copter", "John Earnest", 100, (6, 6, 6), (255, 255, 255), (17, 119, 153),
                    ("Cualquier boton:", "cambia de lado", "el helicoptero")),
}
ZONA = (16, 36)              # dónde va la pantalla del juego (128x64) en la de Wonder
SALIR_MS = 1000


def _color(rgb):
    return M.color(*rgb)


def _ventana(x, y, w, h, datos):
    """Manda solo un pedazo de la pantalla (mucho más rápido que toda)."""
    M.cmd(0x2A, bytes((0, x, 0, x + w - 1)))
    M.cmd(0x2B, bytes((0, y, 0, y + h - 1)))
    M.cmd(0x2C)
    M.cs.value(0)
    M.dc.value(1)
    M.spi.write(datos)
    M.cs.value(1)


def _barra_energia(x, y, w, energia):
    M.fb.rect(x, y, w, 7, M.NAVY)
    c = M.AMARILLO if energia >= M.ENERGIA_JUGAR else M.GRIS
    M.fb.fill_rect(x + 1, y + 1, (w - 2) * energia // 100, 5, c)
    marca = x + 1 + (w - 2) * M.ENERGIA_JUGAR // 100      # la rayita del 25 %
    M.fb.fill_rect(marca, y - 1, 1, 9, M.ROJO)


def dibujar(sel, nota=""):
    fb = M.fb
    actual = M.juego_actual()
    ident = M.JUEGOS[sel][0]
    nombre, autores, _, _, _, _, _ = INFO[ident]
    energia = M.EST_W.get("energia", 0)
    fb.fill(M.AZUL)
    fb.fill_rect(0, 0, M.W, 13, M.NAVY)
    fb.text("JUEGOS", 3, 3, M.BLANCO)
    M.panel(3, 16, M.W - 6, 92)
    ico = M.cargar_spr("icono_juego_%s.spr" % ident)
    if ico:
        M.pegar(ico, 31, 45)
        del ico
    else:
        fb.fill_rect(9, 22, 44, 44, M.GRIS)
    fb.text(nombre[:12], 58, 21, M.NAVY)
    fb.text("por", 58, 32, M.GRIS)
    fb.text(autores[:12], 58, 42, M.GRIS)
    if ident == actual:
        fb.fill_rect(58, 53, 72, 11, M.VERDE)
        fb.text("Tu juego", 62, 55, M.BLANCO)
    else:
        fb.text("Otro juego", 58, 55, M.GRIS)
    fb.text("Energia", 8, 72, M.NAVY)
    _barra_energia(66, 72, 86, energia)
    M.chico("%d%%" % energia, 8, 83, M.NAVY, None)
    if nota:
        fb.text(nota[:18], 8, 94, M.ROJO)
    elif ident == actual:
        if energia >= M.ENERGIA_JUGAR:
            fb.text("O = jugar", 8, 94, M.VERDE)
        else:
            fb.text("Necesitas 25%", 8, 94, M.ROJO)
    elif energia >= 100:
        fb.text("O = cambiar (-50%)", 8, 94, M.VERDE)
    else:
        fb.text("Cambiar: con 100%", 8, 94, M.GRIS)
    fb.text("< >  otros juegos", 8, 113, M.CLARO)
    M.mostrar()


def pantalla():
    M.esperar_soltar()
    ids = [j[0] for j in M.JUEGOS]
    sel = ids.index(M.juego_actual())
    dibujar(sel)
    while True:
        e_izq, e_der, e_o = M.b_izq.leer(), M.b_der.leer(), M.b_o.leer()
        if e_o == "largo":
            M.sonar("volver")
            M.esperar_soltar()
            return "menu"
        paso = -1 if e_izq == "presion" else 1 if e_der == "presion" else 0
        if paso:
            sel = (sel + paso) % len(ids)
            M.sonar("mover", paso, sel)
            dibujar(sel)
        if e_o == "corto":
            ident = ids[sel]
            energia = M.EST_W.get("energia", 0)
            if ident == M.juego_actual():
                if energia >= M.ENERGIA_JUGAR:
                    M.sonar("entrar")
                    jugar(ident)
                    dibujar(sel)
                else:
                    M.sonar("error")
                    M.mensaje("Necesitas 25%", "Haz un pomodoro!")
                    M.esperar_boton(2500)
                    dibujar(sel)
            elif energia >= 100:
                if confirmar(INFO[ident][0]):
                    M.EST_W["energia"] = energia - M.ENERGIA_CAMBIAR
                    M.cambiar_juego(ident)
                    M.sonar("hecho")
                    dibujar(sel, "")
                else:
                    dibujar(sel)
            else:
                M.sonar("error")
                dibujar(sel, "Necesitas 100%")
        if M.tick():
            dibujar(sel)
        time.sleep_ms(15)


def confirmar(nombre):
    M.fb.fill(M.AZUL)
    M.panel(6, 30, M.W - 12, 66)
    M.texto_centro("Cambiar a", 38, M.NAVY)
    M.texto_centro(nombre[:16], 50, M.NAVY)
    M.texto_centro("por 50% energia?", 62, M.GRIS)
    M.fb.text("O si   <O no", 30, 80, M.VERDE)
    M.mostrar()
    M.esperar_soltar()
    while True:
        e_o, e_izq = M.b_o.leer(), M.b_izq.leer()
        M.b_der.leer()
        if e_o == "corto":
            return True
        if e_o == "largo" or e_izq == "presion":
            M.sonar("volver")
            M.esperar_soltar()
            return False
        time.sleep_ms(15)


def _marco(ident):
    """Lo que rodea la pantalla del juego: nombre arriba y ayuda abajo."""
    nombre, autores, _, _, color, fondo, _ = INFO[ident]
    fb = M.fb
    fb.fill(M.NAVY)
    fb.text(nombre[:14], 3, 15, M.BLANCO)
    fb.rect(ZONA[0] - 2, ZONA[1] - 2, 132, 68, _color(color))
    fb.fill_rect(ZONA[0], ZONA[1], 128, 64, _color(fondo))
    M.texto_centro("Salir: IZQ + DER", 108, M.GRIS)
    M.texto_centro("por " + autores[:14], 118, M.GRIS)
    M.mostrar()


def _ayuda(ident):
    nombre, _, _, _, _, _, ayuda = INFO[ident]
    M.fb.fill(M.AZUL)
    M.fb.fill_rect(0, 0, M.W, 13, M.NAVY)
    M.fb.text(nombre[:18], 3, 3, M.BLANCO)
    M.panel(4, 18, M.W - 8, 84)
    for k, l in enumerate(ayuda):
        M.fb.text(l, 9, 24 + k * 12, M.NAVY)
    M.fb.text("Salir:", 9, 76, M.GRIS)
    M.fb.text("mantener IZQ+DER", 9, 87, M.GRIS)
    M.texto_centro("O = empezar", 110, M.BLANCO)
    M.mostrar()
    M.esperar_soltar()
    while True:
        e_o, e_izq, e_der = M.b_o.leer(), M.b_izq.leer(), M.b_der.leer()
        if e_o == "corto":
            return True
        if e_o == "largo":
            M.esperar_soltar()
            return False
        time.sleep_ms(15)


def _teclas(ident, izq, o, der):
    """Convierte los 3 botones de Wonder en teclas CHIP-8 (un bit por tecla)."""
    t_izq, t_o, t_der = INFO[ident][3]
    if ident == "piper":                  # Piper se mueve en 4 direcciones
        if o:
            if izq:
                return 1 << 5             # arriba
            if der:
                return 1 << 8             # abajo
            return 1 << 6                 # esconderse en la arena
        return (izq << 7) | (der << 9)
    return (izq << t_izq) | (o << t_o) | (der << t_der)


def jugar(ident):
    if not _ayuda(ident):
        return
    gc.collect()
    import chip8
    nombre, _, por_cuadro, _, color, fondo, _ = INFO[ident]
    try:
        with open("juego_%s.ch8" % ident, "rb") as f:
            rom = f.read()
    except OSError:
        M.sonar("error")
        M.mensaje("Falta el juego", "juego_%s.ch8" % ident)
        M.esperar_boton(2500)
        return
    maq = chip8.Maquina(rom, por_cuadro, _color(color), _color(fondo))
    maq.sembrar(time.ticks_us())
    del rom
    antes = M.BARRA
    M.BARRA = False
    _marco(ident)
    p_izq, p_o, p_der = M.b_izq.p, M.b_o.p, M.b_der.p
    t_salir = None
    t_tick = time.ticks_ms()
    cuadro = 0
    sonaba = 0
    forzar = True
    siguiente = time.ticks_us()
    try:
        while True:
            izq, o, der = 1 - p_izq.value(), 1 - p_o.value(), 1 - p_der.value()
            ahora = time.ticks_ms()
            if izq or o or der:
                M.ACT["t"] = ahora                     # jugando no se duerme
            if izq and der:
                if t_salir is None:
                    t_salir = ahora
                elif time.ticks_diff(ahora, t_salir) > SALIR_MS:
                    break
                izq = der = 0
            else:
                t_salir = None
            estado = maq.cuadro(_teclas(ident, izq, o, der))
            if estado == 1 or estado == 3:            # el juego terminó (o una instrucción rara)
                break
            st = maq.sonido()
            if st and not sonaba:
                M.sonar("pitido", st * 1000 // 60)
            sonaba = st
            cuadro += 1
            if (cuadro & 1 or forzar) and (maq.cambio() or forzar):
                _ventana(ZONA[0], ZONA[1], 128, 64, maq.pintar())
                forzar = False
            if time.ticks_diff(ahora, t_tick) > 500:
                t_tick = ahora
                if M.tick():                          # algo pasó (aviso, comida...): redibujar
                    M.BARRA = False
                    _marco(ident)
                    forzar = True
            siguiente = time.ticks_add(siguiente, 16667)
            espera = time.ticks_diff(siguiente, time.ticks_us())
            if espera > 0:
                time.sleep_us(espera)
            elif espera < -100000:                    # muy atrasado: no intentar alcanzar
                siguiente = time.ticks_us()
    finally:
        M.BARRA = antes
        del maq
        if "chip8" in sys.modules:
            del sys.modules["chip8"]
        gc.collect()
    M.sonar("volver")
    M.esperar_soltar()
