# Wonder - menú Configuración
#
#   IZQ / DER = subir / bajar en la lista,  O = cambiar,  mantener O = volver
#   En un volumen: O para editar, IZQ / DER = menos / más, O = listo.
#
# Opciones: volumen de notificaciones, efectos y música · silenciar todo ·
# reactivar el parlante (si la protección lo cortó) · redes WiFi ·
# buscar actualización · borrar todo (restablecer de fábrica).
#
# "Borrar todo" NUNCA borra pines.json (los botones son los que son).

import time
import os
import gc
import __main__ as M

# Lo que se borra al restablecer de fábrica (pines.json NO está: nunca se borra)
DE_FABRICA = ("config.json", "hechos.json", "wonder_estado.json", "pomodoro.json", "cal.json",
              "wonder.raw", "wonder.ver", "wonder.tmp", "ajustes.json", "hora.json")

VOLS = (("notif", "Notific."), ("efectos", "Efectos"), ("musica", "Musica"))


def opciones():
    ops = [("vol", k, n) for k, n in VOLS]
    ops.append(("mudo", None, "Silenciar todo"))
    if M.sonidos and M.sonidos.bloqueado:
        ops.append(("parlante", None, "Reactivar parlante"))
    ops += [("redes", None, "Redes WiFi"), ("ota", None, "Actualizar"), ("borrar", None, "Borrar todo")]
    return ops


def dibujar(sel, editando=False):
    fb = M.fb
    fb.fill(M.AZUL)
    fb.fill_rect(0, 0, M.W, 13, M.NAVY)
    fb.text("CONFIG.", 3, 3, M.BLANCO)
    ops = opciones()
    M.panel(3, 16, M.W - 6, len(ops) * 11 + 4)
    for k, (tipo, clave, nombre) in enumerate(ops):
        y = 19 + k * 11
        elegido = k == sel
        if elegido:
            fb.fill_rect(4, y - 1, M.W - 8, 10, M.VERDE if editando else M.AZUL)
        c = M.BLANCO if elegido else (M.ROJO if tipo == "borrar" else M.NAVY)
        if tipo == "vol":
            fb.text(nombre[:9], 7, y, c)
            v = M.AJ["vol"].get(clave, 100)
            for k2 in range(10):                     # 10 rayitas de volumen, cada vez más altas
                alto = 2 + k2 // 2
                lleno = k2 < v // 10
                fb.fill_rect(84 + k2 * 5, y + 7 - alto, 3, alto,
                             (M.BLANCO if elegido else M.NAVY) if lleno else M.GRIS)
            if M.AJ["mudo"]:
                fb.text("x", 140, y, M.ROJO)
        elif tipo == "mudo":
            fb.text(nombre, 7, y, c)
            fb.text("SI" if M.AJ["mudo"] else "NO", 134, y, M.ROJO if M.AJ["mudo"] else c)
        else:
            fb.text(nombre, 7, y, c)
    ayuda = "< > cambiar  O listo" if editando else "< > mover  O elegir"
    fb.text(ayuda, 2, 108, M.CLARO)
    fb.text("Wonder v" + M.VERSION, 2, 119, M.GRIS)
    M.mostrar()


def probar_volumen(clave):
    nombre = {"notif": "aviso", "efectos": "seleccionar", "musica": "despertar"}[clave]
    if clave == "musica":
        M.sonar("melodia_dormir", M.momento())
    else:
        M.sonar(nombre)


def pantalla():
    M.esperar_soltar()
    sel = 0
    editando = False
    ops = opciones()
    dibujar(sel)
    while True:
        e_izq, e_der, e_o = M.b_izq.leer(), M.b_der.leer(), M.b_o.leer()
        sel = min(sel, len(ops) - 1)
        tipo, clave, _ = ops[sel]
        if e_o == "largo":
            M.sonar("volver")
            M.esperar_soltar()
            return "menu"
        paso = -1 if e_izq == "presion" else 1 if e_der == "presion" else 0
        if paso and editando:
            v = max(0, min(100, M.AJ["vol"].get(clave, 100) + paso * 10))
            M.AJ["vol"][clave] = v
            M.guardar_ajustes()
            probar_volumen(clave)
            dibujar(sel, True)
        elif paso:
            sel = (sel + paso) % len(ops)
            M.sonar("tic", sel + 3)
            dibujar(sel)
        if e_o == "corto":
            if tipo == "vol":
                editando = not editando
                if not editando:
                    M.sonar("guardar")
                dibujar(sel, editando)
            elif tipo == "mudo":
                M.AJ["mudo"] = not M.AJ["mudo"]
                M.guardar_ajustes()
                if not M.AJ["mudo"]:
                    M.sonar("seleccionar")
                dibujar(sel)
            elif tipo == "parlante":
                M.sonidos.desbloquear()
                M.T["aviso_mudo"] = False
                M.sonar("despertar")
                ops = opciones()
                dibujar(sel)
            elif tipo == "redes":
                M.sonar("especial")
                M.esperar_soltar()
                return "configurar"
            elif tipo == "ota":
                M.sonar("seleccionar")
                actualizar()
                dibujar(sel)
            elif tipo == "borrar":
                if borrar_todo():
                    return "configurar"
                dibujar(sel)
        if M.tick():
            ops = opciones()
            dibujar(sel, editando)
        time.sleep_ms(15)


# ---------------- Actualizar por internet ----------------
def actualizar():
    import ota
    red = M.red
    if not red.configurado() or not red.conectar_ya(M.esperando_wifi):
        M.sonar("error")
        M.mensaje("Sin WiFi", "Hace falta internet")
        M.esperar_boton(2500)
        return
    M.mensaje("Buscando version", "nueva en GitHub...")
    try:
        remota, cambios = ota.buscar()
    except Exception as e:
        print("OTA:", e)
        M.sonar("error")
        M.mensaje("No se pudo revisar", str(e)[:18])
        M.esperar_boton(3000)
        return
    if not cambios:
        M.sonar("listo")
        M.mensaje("Ya esta al dia", "Version " + M.VERSION)
        M.esperar_boton(2500)
        return
    total = sum(a["t"] for a in cambios)
    M.fb.fill(M.AZUL)
    M.panel(6, 18, M.W - 12, 88)
    M.texto_centro("Hay version " + remota[:6], 24, M.NAVY)
    M.texto_centro("%d archivos" % len(cambios), 38, M.GRIS)
    M.texto_centro("%d KB" % (total // 1024 + 1), 50, M.GRIS)
    puede = M.BAT["usb"] or (M.BAT["pct"] is not None and M.BAT["pct"] >= 50)
    if puede:
        M.texto_centro("O = actualizar", 70, M.VERDE)
        M.texto_centro("<O = ahora no", 84, M.GRIS)
    else:
        M.texto_centro("Conecta el", 70, M.ROJO)
        M.texto_centro("cargador primero", 84, M.ROJO)
    M.mostrar()
    M.esperar_soltar()
    while True:
        e_o, e_izq = M.b_o.leer(), M.b_izq.leer()
        M.b_der.leer()
        if e_o == "corto" and puede:
            break
        if e_o == "largo" or e_izq == "presion" or (e_o == "corto" and not puede):
            M.sonar("volver")
            M.esperar_soltar()
            return
        time.sleep_ms(15)

    def avance(k, n, nombre, b):
        M.fb.fill(M.AZUL)
        M.panel(6, 30, M.W - 12, 60)
        M.texto_centro("Actualizando %d/%d" % (k + 1, n), 38, M.NAVY)
        M.texto_centro(nombre[:16], 52, M.GRIS)
        M.fb.rect(14, 68, M.W - 28, 8, M.NAVY)
        M.fb.fill_rect(15, 69, (M.W - 30) * (k + 1) // n, 6, M.VERDE)
        M.texto_centro("No lo apagues", 100, M.BLANCO)
        M.mostrar()

    gc.collect()
    try:
        ota.actualizar(cambios, avance)
    except Exception as e:
        print("OTA:", e)
        M.sonar("error")
        M.mensaje("No se actualizo", str(e)[:18])
        M.esperar_boton(3000)
        M.mensaje("Todo quedo", "como estaba")
        M.esperar_boton(2000)
        return
    M.sonar("hecho")
    M.mensaje("Listo! Version " + remota[:4], "Reiniciando...")
    time.sleep(2)
    import machine
    machine.reset()


# ---------------- Restablecer de fábrica ----------------
def borrar_todo():
    fb = M.fb
    fb.fill(M.AZUL)
    fb.fill_rect(0, 0, M.W, 13, M.ROJO)
    fb.text("BORRAR", 3, 3, M.BLANCO)
    M.panel(4, 17, M.W - 8, 92)
    for k, l in enumerate(("Se borran: redes,", "logros, comida,", "energia, racha,",
                           "juego y Mi Wonder.", "Los botones NO.")):
        fb.text(l, 8, 21 + k * 11, M.NAVY if k < 4 else M.VERDE)
    fb.text("Manten O 3 seg", 8, 80, M.ROJO)
    fb.text("para borrar", 8, 91, M.ROJO)
    fb.text("IZQ = cancelar", 2, 115, M.CLARO)
    M.mostrar()
    M.sonar("aviso")
    M.esperar_soltar()
    t_o = None
    while True:
        if M.b_izq.p.value() == 0 or M.b_der.p.value() == 0:
            M.sonar("volver")
            M.esperar_soltar()
            return False
        if M.b_o.p.value() == 0:
            if t_o is None:
                t_o = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), t_o) > 3000:
                break
        else:
            t_o = None
        time.sleep_ms(20)
    M.mensaje("Borrando...", "")
    if M.red.conectado():
        try:
            M.red.enviar("/pico/reinicio", {"motivo": "fabrica"}, timeout=4)   # el hub guarda copia
        except Exception:
            pass
    for n in DE_FABRICA:
        try:
            os.remove(n)
        except OSError:
            pass
    M.sonar("guardar")
    M.mensaje("Listo. Wonder", "empieza de cero")
    time.sleep(2)
    import machine
    machine.reset()
    return True
