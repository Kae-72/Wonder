# Wonder - sonidos estilo Game Boy (por el amplificador MAX98357A + parlante)
#
# Cómo suena un Game Boy: ondas "cuadradas" con distinto ancho de pulso
# (12.5 %, 25 %, 50 %: de más chillón a más redondo), notas que suben o bajan
# de golpe (barridos), volumen que se apaga rápido, arpegios muy rápidos en vez
# de acordes, y un canal de ruido para golpes.
# Todo está en la escala pentatónica de Do (Do Re Mi Sol La): siempre suena musical.
#
# Los sonidos se tocan SIN DETENER el programa, y uno nuevo corta al anterior.
#
# Uso:
#   import sonidos
#   sonidos.iniciar()
#   sonidos.mover(+1, posicion)   sonidos.seleccionar()   sonidos.volver() ...
#
# Cada sonido es una lista de notas:
#   (frecuencia, ms, pulso, volumen_inicio, volumen_fin, frecuencia_final)
#   frecuencia 0 = silencio, frecuencia RUIDO = ruido (golpe / chasquido)
#   pulso: P12 (chillón), P25, P50 (redondo)
#   volumen de 0.0 a 1.0; frecuencia_final = None si no hay barrido

from machine import Pin, I2S
import struct
import time

# --- Pines del amplificador (hoja "Wonder · Pines") ---
PIN_BCLK = 20
PIN_LRC = 21          # tiene que ser BCLK + 1
PIN_DIN = 22
PIN_SD = 26           # encender / apagar el amplificador

VOLUMEN = 80          # TOPE general 0 a 100. Con 8 ohm 0.5 W: 100 da ~0.2 W (seguro). Con GAIN a GND, máx. 80.

# Volumen de cada tipo de sonido (0 a 100 % del tope). Se cambian en el menú Configuración.
#   notif   = avisos que importan (clase por empezar, fin de pomodoro, ¡Hecho!, errores)
#   efectos = botones, menús, juegos
#   musica  = melodías (al prender y al dormir)
VOL = {"notif": 100, "efectos": 100, "musica": 100}
FREC_MUESTREO = 11025   # suficiente para sonidos de 8 bits y usa menos RAM
MAX_MS = 1500           # el sonido más largo (melodías de dormir) dura ~1.4 s

P12, P25, P50 = 0.125, 0.25, 0.5
RUIDO = -1

# Notas (Hz)
C4, D4, E4, G4, A4 = 262, 294, 330, 392, 440
C5, D5, E5, G5, A5 = 523, 587, 659, 784, 880
C6, D6, E6, G6, A6 = 1047, 1175, 1319, 1568, 1760
C7, D7, E7, G7 = 2093, 2349, 2637, 3136

ESCALA = (C5, D5, E5, G5, A5, C6, D6, E6, G6, A6, C7)

_audio = None
_sd = None
_buf = None
_pos = 0
_ocupado = False
_CEROS = bytes(512)
_BUF = bytearray(MAX_MS * FREC_MUESTREO // 1000 * 2)   # UN solo búfer, reservado al arrancar
activo = True         # False = silencio total (Configuración -> Silenciar)
bloqueado = False     # True = la protección cortó el parlante (hasta reiniciar o reactivarlo)
_amp = False          # el amplificador está prendido ahora
_t_amp = 0            # desde cuándo
_silencios = 0        # trozos de silencio seguidos (para apagar el amplificador)
TROZO = 512
_COLA_SILENCIO = 20   # ms de silencio al final


# ---------------- Sintetizador ----------------
def _render(notas, cat="efectos"):
    total_ms = min(MAX_MS, sum(n[1] for n in notas) + _COLA_SILENCIO)
    buf = _BUF
    limite = total_ms * FREC_MUESTREO // 1000
    mv = memoryview(buf)
    for i in range(0, limite * 2, len(_CEROS)):          # borra lo anterior, por trozos
        k = min(len(_CEROS), limite * 2 - i)
        mv[i:i + k] = _CEROS[:k]
    base = 9000 * VOLUMEN / 100 * VOL.get(cat, 100) / 100
    pack = struct.pack
    pos = 0
    lfsr = 0x7FFF
    for n in notas:
        f, ms, duty, v0, v1, f1 = tuple(n) + (0, 0, P50, 1.0, 1.0, None)[len(n):]
        largo = ms * FREC_MUESTREO // 1000
        fin = min(pos + largo, limite)
        if pos >= limite:
            break
        if f == 0 or largo == 0:
            pos = fin
            continue
        if f1 is None:
            f1 = f
        k = pos                                   # dónde empezó la nota
        if f == RUIDO:                            # ruido tipo Game Boy (registro LFSR)
            paso = FREC_MUESTREO // 6000 + 1
            while pos < fin:
                t = (pos - k) / largo
                a = int(base * (v0 + (v1 - v0) * t))
                bit = (lfsr ^ (lfsr >> 1)) & 1
                lfsr = (lfsr >> 1) | (bit << 14)
                c = min(paso, fin - pos)
                buf[pos * 2:(pos + c) * 2] = pack("<h", a if lfsr & 1 else -a) * c
                pos += c
            continue
        acc = float(pos)
        while pos < fin:
            t = (pos - k) / largo
            fr = f + (f1 - f) * t
            periodo = FREC_MUESTREO / fr
            a = base * (v0 + (v1 - v0) * t)
            alto = int(a * 2 * (1 - duty))        # centrado en cero (sin zumbido de fondo)
            bajo = -int(a * 2 * duty)
            for valor, parte in ((alto, duty), (bajo, 1 - duty)):
                acc += periodo * parte
                c = min(int(acc) - pos, fin - pos)
                if c > 0:
                    v = max(-32767, min(32767, valor))
                    buf[pos * 2:(pos + c) * 2] = pack("<h", v) * c
                    pos += c
        pos = fin
    return limite * 2


# ---------------- Reproductor ----------------
_SILENCIO = memoryview(bytearray(TROZO))
_detenido = False


_t_cadena = 0


def _alimentar(_arg):
    # El I2S recibe datos SIEMPRE (silencio cuando no hay sonido): así cada sonido
    # arranca al instante. Pero el AMPLIFICADOR solo se prende mientras suena algo
    # (pin SD): si el Pico se llegara a colgar en silencio, el parlante queda mudo.
    # Cada trozo pide el siguiente: es una "cadena". Si el Pico está muy ocupado y se
    # pierde un eslabón, revisar() la vuelve a enganchar.
    global _pos, _ocupado, _t_cadena, _silencios
    if _detenido or _audio is None:
        return
    _t_cadena = time.ticks_ms()
    try:
        if _buf is not None and _pos < len(_buf):
            trozo = _buf[_pos:_pos + TROZO]
            _pos += len(trozo)
            _silencios = 0
            _audio.write(trozo)
        else:
            _ocupado = False
            _silencios += 1
            if _amp and _silencios > 6:          # ~0,3 s después de terminar: amplificador apagado
                _amp_apagar()
            _audio.write(_SILENCIO)
    except Exception as e:
        print("Sonido (cadena):", e)


# ---------------- Protección del parlante ----------------
# El "grito": si el Pico se cuelga mientras suena algo, el I2S puede quedarse
# repitiendo el último pedacito para siempre. Un vigilante revisa 4 veces por
# segundo (con una interrupción de reloj, que funciona aunque el programa esté
# trabado): si el amplificador lleva prendido demasiado tiempo o la cadena dejó de
# avanzar, lo APAGA y deja el sonido bloqueado hasta reiniciar (o reactivarlo en
# Configuración). El llavero muestra "Parlante silenciado".
def _amp_prender():
    global _amp, _t_amp
    if bloqueado or _sd is None:
        return
    _t_amp = time.ticks_ms()
    if not _amp:
        _sd.value(1)
        _amp = True


def _amp_apagar():
    global _amp
    if _sd is not None:
        _sd.value(0)
    _amp = False


def _vigilar(_t):
    # Solo APAGA el amplificador (el sonido que se quedó pegado se corta). Ya NO deja el
    # llavero silenciado: el siguiente sonido vuelve a funcionar normal. (En la v8 se
    # disparaba por error cuando el Pico estaba ocupado y dejaba todo muteado.)
    global _amp
    if not _amp:
        return
    if time.ticks_diff(time.ticks_ms(), _t_amp) > MAX_MS + 2500:
        _sd.value(0)
        _amp = False


_vigilante = None


def _poner_vigilante():
    global _vigilante
    if _vigilante is not None:
        return
    from machine import Timer
    try:
        _vigilante = Timer(period=250, mode=Timer.PERIODIC, callback=_vigilar, hard=True)
    except (TypeError, ValueError):
        _vigilante = Timer(period=250, mode=Timer.PERIODIC, callback=_vigilar)


def desbloquear():
    """Vuelve a permitir sonido después de que la protección lo cortó."""
    global bloqueado
    bloqueado = False


def ajustar(vol=None, mudo=None):
    """Aplica lo guardado en Configuración: vol = {"notif": 0-100, ...}, mudo = True/False."""
    global activo
    if vol:
        for k in VOL:
            if isinstance(vol.get(k), int):
                VOL[k] = max(0, min(100, vol[k]))
    if mudo is not None:
        activo = not mudo


def revisar():
    """Llamar seguido. Si la cadena de audio se cortó (más de 0,4 s sin pedir datos) la
    reengancha. Si ya no suena nada, DETIENE el audio por completo (sin reloj de audio
    no hay pitido de fondo): el próximo sonido lo vuelve a arrancar solo."""
    if _audio is None or _detenido:
        return
    if not _ocupado and not _amp:
        _cerrar_i2s()
        return
    if time.ticks_diff(time.ticks_ms(), _t_cadena) > 400:
        print("Sonido: cadena reenganchada")
        _alimentar(None)


def _abrir_i2s():
    global _audio
    _audio = I2S(0, sck=Pin(PIN_BCLK), ws=Pin(PIN_LRC), sd=Pin(PIN_DIN), mode=I2S.TX,
                 bits=16, format=I2S.MONO, rate=FREC_MUESTREO, ibuf=3072)
    _audio.irq(_alimentar)                        # modo sin bloqueo
    _alimentar(None)


def _cerrar_i2s():
    global _audio
    a = _audio
    _audio = None
    if a is not None:
        try:
            a.deinit()
        except Exception:
            pass
    # las patas del audio quedan quietas en 0 (nada de señal hacia el amplificador)
    for n in (PIN_BCLK, PIN_LRC, PIN_DIN):
        Pin(n, Pin.OUT, value=0)


def iniciar():
    global _sd, _detenido
    _sd = Pin(PIN_SD, Pin.OUT, value=0)           # amplificador apagado hasta que suene algo
    _detenido = False
    _cerrar_i2s()                                 # el audio arranca solo cuando hay un sonido
    _poner_vigilante()


def apagar():
    """Apaga el amplificador (para ahorrar batería en reposo)."""
    global _detenido, _ocupado
    global _audio, _buf, _vigilante
    _detenido = True
    if _vigilante is not None:        # el vigilante no hace falta dormido (y así no despierta al Pico)
        try:
            _vigilante.deinit()
        except Exception:
            pass
        _vigilante = None
    _ocupado = False
    _buf = None
    _amp_apagar()
    _cerrar_i2s()                     # se suelta el I2S: así nada queda corriendo al dormir


def reanudar():
    """Vuelve a prender el amplificador después de apagar()."""
    if _detenido:
        iniciar()


def tocar(notas, clave=None, cat="efectos"):
    """Toca una lista de notas. Interrumpe lo que esté sonando.
    cat = "notif", "efectos" o "musica" (cada uno con su volumen)."""
    global _buf, _pos, _ocupado
    if _detenido or not activo or bloqueado or VOL.get(cat, 100) <= 0:
        return
    _buf = None                      # mientras se prepara, el amplificador recibe silencio
    n = _render(notas, cat)
    _buf = memoryview(_BUF)[:n]
    _pos = 0
    _ocupado = True
    if _audio is None:
        _abrir_i2s()                 # el audio estaba detenido: se arranca para este sonido
    _amp_prender()


def sonando():
    return _ocupado


def esperar(max_ms=3000):
    fin = time.ticks_add(time.ticks_ms(), max_ms)
    while _ocupado and time.ticks_diff(fin, time.ticks_ms()) > 0:
        revisar()
        time.sleep_ms(5)


# ---------------- Los sonidos de Wonder ----------------
# ---------------- Variedad ----------------
# Los sonidos de navegación cambian un poco cada vez (otra variante, otro timbre,
# una notita de adorno) para que el llavero no suene repetitivo. Siempre con las
# mismas notas de la escala, así nunca suena "mal".
# Los AVISOS (aviso, error) NO cambian: tienen que reconocerse al instante.

import random

_ultima = {}


def _elegir(nombre, variantes):
    """Elige una variante distinta a la anterior."""
    n = len(variantes)
    k = random.getrandbits(8) % n
    if n > 1 and k == _ultima.get(nombre):
        k = (k + 1) % n
    _ultima[nombre] = k
    return variantes[k]


def _azar(n):
    return random.getrandbits(8) % n


# ---------------- Los sonidos de Wonder ----------------
def encender():
    """Al prender el llavero: un jingle corto, distinto cada vez."""
    tocar(_elegir("encender", (
        [(C5, 55, P25, .8, .7), (E5, 55, P25, .8, .7), (G5, 55, P25, .8, .7),
         (C6, 55, P25, .8, .7), (0, 30), (G6, 60, P12, .9, .8), (C7, 380, P50, .9, 0.0)],
        [(C5, 35, P12, .7, .7), (D5, 35, P12, .7, .7), (E5, 35, P12, .7, .7), (G5, 35, P12, .7, .7),
         (A5, 35, P12, .7, .7), (C6, 35, P12, .8, .7), (0, 40), (E6, 70, P25, .8, .7),
         (G6, 70, P25, .8, .7), (C7, 300, P50, .9, 0.0)],
        [(G5, 60, P50, .8, .7), (E5, 60, P50, .8, .7), (C5, 80, P50, .8, .6), (0, 50),
         (C6, 45, P25, .8, .7), (E6, 45, P25, .8, .7), (G6, 45, P25, .8, .7), (C7, 320, P25, .9, 0.0)],
        [(C6, 22, P12, .7, .7), (E6, 22, P12, .7, .7), (G6, 22, P12, .7, .7)] * 4 +
        [(A6, 120, P25, .8, .7), (0, 30), (C7, 300, P50, .9, 0.0)],
    )), cat="musica")


def entrar():
    """Inicio -> menú (empezar la sesión): arpegio cortito, con variantes."""
    tocar(_elegir("entrar", (
        [(C6, 28, P25, .8, .7), (E6, 28, P25, .8, .7), (G6, 28, P25, .8, .7), (C7, 110, P25, .8, 0.0)],
        [(G5, 30, P50, .8, .7), (C6, 30, P50, .8, .7), (E6, 30, P50, .8, .7), (G6, 120, P12, .8, 0.0)],
        [(A5, 25, P12, .7, .7), (C6, 25, P12, .7, .7), (D6, 25, P12, .7, .7), (E6, 25, P12, .7, .7),
         (G6, 15, P25, .8, .8), (A6, 15, P25, .8, .8), (G6, 15, P25, .8, .8), (A6, 15, P25, .8, .8),
         (G6, 90, P25, .8, 0.0)],
        [(E6, 35, P25, .8, .7), (C6, 35, P25, .8, .7), (G6, 35, P25, .8, .7), (C7, 35, P25, .8, .7),
         (0, 25), (C7, 80, P12, .6, 0.0)],
    )))


def mover(direccion, posicion=0):
    """IZQ / DER: un "blip" corto. Cada posición tiene su nota, así que
    recorrer el menú toca una melodía. Derecha sube, izquierda baja.
    El timbre cambia un poco cada vez, y a veces lleva una notita de adorno."""
    i = posicion % (len(ESCALA) - 2)
    a, b = ESCALA[i], ESCALA[i + 2]
    if direccion < 0:
        a, b = b, a
    pulso = (P25, P12, P25, P50)[_azar(4)]
    if _azar(5) == 0:                                  # adorno de vez en cuando
        tocar([(a, 14, pulso, .7, .6), (b, 14, pulso, .6, .6), (a, 14, pulso, .6, .5),
               (b, 34, pulso, .6, 0.0)])
    else:
        tocar([(a, 18, pulso, .7, .6), (b, 42, pulso, .6, 0.0)])


def tic(posicion=0):
    """Cambio pequeño (pasar página): golpecito seco."""
    f = ESCALA[posicion % len(ESCALA)] * 2
    tocar([(f, 28, (P12, P25)[_azar(2)], .6, 0.0)])


def seleccionar():
    """O corto: confirmación que sube (3 variantes)."""
    tocar(_elegir("seleccionar", (
        [(G6, 30, P50, .8, .7), (C7, 90, P50, .8, 0.0)],
        [(E6, 25, P25, .8, .7), (G6, 25, P25, .8, .7), (C7, 80, P25, .8, 0.0)],
        [(C7, 20, P12, .7, .6), (G6, 20, P12, .7, .6), (C7, 90, P50, .8, 0.0)],
    )))


def volver():
    """Mantener O: algo que baja (2 variantes)."""
    tocar(_elegir("volver", (
        [(C7, 110, P25, .8, 0.1, G5)],
        [(G6, 30, P50, .8, .7), (E6, 30, P50, .8, .7), (C6, 30, P50, .8, .7), (G5, 70, P50, .7, 0.0)],
    )))


def listo():
    """Algo salió bien (2 variantes)."""
    tocar(_elegir("listo", (
        [(C6, 45, P50, .7, .6), (D6, 45, P50, .7, .6), (E6, 45, P50, .7, .6),
         (G6, 45, P50, .7, .6), (0, 25), (C7, 70, P25, .9, .8), (C7, 260, P12, .8, 0.0)],
        [(G5, 40, P25, .7, .6), (C6, 40, P25, .7, .6), (E6, 40, P25, .7, .6), (0, 20),
         (G6, 60, P50, .8, .7), (C7, 280, P50, .8, 0.0)],
    )), cat="notif")


def error():
    """Algo falló: golpe de ruido y dos notas graves que caen."""
    tocar([(RUIDO, 40, P50, .7, .2), (E4, 110, P50, .8, .6, D4), (0, 35),
           (C4, 260, P50, .8, 0.0, 200)], "error", cat="notif")


def aviso():
    """Llamar la atención (fin de pomodoro, evento): arpegio rápido repetido."""
    arpegio = []
    for _ in range(2):
        for f in (C6, E6, G6, C7, G6, E6):
            arpegio.append((f, 30, P25, .8, .7))
        arpegio.append((0, 60))
    arpegio.append((C7, 300, P50, .9, 0.0))
    tocar(arpegio, "aviso", cat="notif")


def especial():
    """Entrar a configurar: trino chiptune (arpegio muy rápido, como un acorde)."""
    notas = []
    for i in range(12):
        notas.append(((C6, E6, G6)[i % 3], 20, P12, .8 - i * .05, .8 - i * .05))
    notas.append((C7, 180, P25, .7, 0.0, E7))
    tocar(notas, "especial")


def guardar():
    """Algo se guardó: chasquido + nota corta."""
    tocar([(RUIDO, 25, P50, .6, 0.0), (0, 15), (E6, 35, P50, .7, .5), (A6, 90, P50, .7, 0.0)], "guardar")


def dormir():
    """El llavero se va a dormir: bostezo que baja despacio."""
    tocar([(G5, 120, P50, .6, .5, E5), (0, 40), (E5, 160, P50, .5, .3, C5), (0, 40),
           (C5, 260, P50, .4, 0.0, G4)])


def despertar():
    """Al despertar: tres notas rápidas que suben."""
    tocar([(C6, 40, P25, .7, .6), (E6, 40, P25, .7, .6), (G6, 90, P25, .8, 0.0)])


def hecho():
    """¡Hecho!: pequeña fanfarria (como subir de nivel, pero nuestra). 2 variantes."""
    tocar(_elegir("hecho", (
        [(G5, 60, P50, .8, .7), (C6, 60, P50, .8, .7), (E6, 60, P50, .8, .7), (0, 30),
         (G6, 50, P25, .9, .8), (E6, 50, P25, .8, .7), (G6, 50, P25, .9, .8), (C7, 260, P12, .9, 0.0)],
        [(C6, 40, P25, .8, .7), (E6, 40, P25, .8, .7), (G6, 40, P25, .8, .7), (C7, 40, P25, .9, .8),
         (0, 30), (A6, 50, P50, .8, .7), (C7, 60, P50, .9, .8), (E7, 240, P12, .9, 0.0)],
    )), cat="notif")


def melodia_dormir(momento="dia"):
    """Antes de apagarse: melodía corta según la hora, distinta cada vez.
    Día: brillante y hacia arriba. Tarde: cálida, bajando. Noche: suave, como canción de cuna."""
    if momento == "noche":
        n = 140
        opciones = (
            [(E5, n, P50, .5, .4), (G5, n, P50, .5, .4), (A5, n, P50, .5, .4), (G5, n, P50, .5, .4),
             (E5, n, P50, .5, .4), (D5, n, P50, .4, .3), (C5, 450, P50, .4, 0.0)],
            [(C5, 160, P50, .5, .4), (E5, 160, P50, .5, .4), (G5, 160, P50, .5, .4), (E5, 160, P50, .5, .4),
             (D5, 160, P50, .4, .3), (C5, 500, P50, .4, 0.0)],
            [(G5, 180, P50, .5, .4), (E5, 180, P50, .5, .4), (C5, 180, P50, .4, .4), (0, 60),
             (D5, 180, P50, .4, .3), (C5, 550, P50, .4, 0.0)],
        )
    elif momento == "tarde":
        n = 110
        opciones = (
            [(E6, n, P50, .6, .5), (D6, n, P50, .6, .5), (C6, n, P50, .6, .5), (A5, n, P50, .6, .5),
             (G5, n, P50, .6, .5), (0, 40), (C6, 380, P25, .6, 0.0)],
            [(G6, n, P25, .6, .5), (E6, n, P25, .6, .5), (D6, n, P25, .6, .5), (E6, n, P25, .6, .5),
             (C6, n, P25, .6, .5), (A5, n, P25, .5, .4), (C6, 400, P50, .6, 0.0)],
            [(A5, 120, P50, .6, .5), (C6, 120, P50, .6, .5), (D6, 120, P50, .6, .5), (C6, 120, P50, .6, .5),
             (A5, 120, P50, .5, .4), (G5, 450, P50, .5, 0.0)],
        )
    else:
        n = 80
        opciones = (
            [(C6, n, P25, .7, .6), (E6, n, P25, .7, .6), (G6, n, P25, .7, .6), (A6, n, P25, .7, .6),
             (G6, n, P25, .7, .6), (E6, n, P25, .7, .6), (G6, n, P25, .7, .6), (C7, 300, P12, .8, 0.0)],
            [(G5, n, P12, .7, .6), (A5, n, P12, .7, .6), (C6, n, P12, .7, .6), (D6, n, P12, .7, .6),
             (E6, n, P12, .7, .6), (G6, n, P12, .7, .6), (E6, n, P12, .7, .6), (C6, 280, P25, .7, 0.0)],
            [(E6, 70, P25, .7, .6), (G6, 70, P25, .7, .6), (C7, 70, P25, .8, .7), (0, 40),
             (D7, 90, P50, .7, .6), (C7, 90, P50, .7, .6), (A6, 90, P50, .7, .6), (G6, 320, P50, .7, 0.0)],
        )
    tocar(_elegir("dormir_" + momento, opciones), cat="musica")


# ---------------- Sonidos nuevos (v8) ----------------
def comida(rareza="basica"):
    """Te tocó una comida. Básica: dos notas. Rara: arpegio. Nicho: fanfarria brillante."""
    if rareza == "nicho":
        notas = [(C6, 45, P12, .8, .7), (E6, 45, P12, .8, .7), (G6, 45, P12, .8, .7), (C7, 45, P12, .9, .8),
                 (0, 30), (G6, 45, P25, .8, .7), (C7, 45, P25, .9, .8), (E7, 45, P25, .9, .8), (0, 30),
                 (G7, 60, P12, .9, .8), (E7, 60, P12, .8, .7), (G7, 360, P50, .9, 0.0)]
    elif rareza == "rara":
        notas = [(G5, 50, P25, .8, .7), (C6, 50, P25, .8, .7), (E6, 50, P25, .8, .7), (0, 25),
                 (G6, 60, P50, .8, .7), (C7, 300, P50, .8, 0.0)]
    else:
        notas = [(E6, 60, P50, .7, .6), (0, 20), (G6, 220, P50, .7, 0.0)]
    tocar(notas, cat="notif")


def comer():
    """Wonder come: tres mordiscos (ruido corto) y un 'mmm' que sube."""
    tocar([(RUIDO, 30, P50, .6, 0.0), (0, 60), (RUIDO, 30, P50, .6, 0.0), (0, 60),
           (RUIDO, 30, P50, .6, 0.0), (0, 80), (E5, 120, P50, .6, .5, G5), (C6, 200, P50, .6, 0.0)])


def racha_perdida():
    """Se perdió la racha: tres notas que bajan despacio."""
    tocar([(G5, 160, P50, .6, .5), (E5, 160, P50, .6, .5), (C5, 420, P50, .6, 0.0, G4)], cat="notif")


def pitido(ms=100):
    """El "buzzer" de los juegos CHIP-8: un tono cuadrado simple."""
    tocar([(A5, max(20, min(ms, 1200)), P50, .6, .6)])


TODOS = ("encender", "entrar", "mover", "tic", "seleccionar", "volver", "listo", "error", "aviso", "especial", "guardar",
         "dormir", "despertar", "hecho", "comida", "comer", "racha_perdida", "pitido")


def demo():
    """Toca todos, uno tras otro (para probar)."""
    import time
    for nombre in TODOS:
        print("Sonido:", nombre)
        if nombre == "mover":
            for p in range(5):
                mover(1, p)
                esperar()
            for p in range(4, -1, -1):
                mover(-1, p)
                esperar()
        else:
            globals()[nombre]()
            esperar()
        time.sleep_ms(350)
