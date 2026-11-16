# Wonder - grabar clases: micrófono INMP441 -> archivo .wav en la microSD
#
# Pines (hoja "Wonder · Pines"):
#   Micrófono: SCK=GP6, WS=GP7, SD=GP8 (L/R a GND = canal izquierdo)
#   MicroSD:   SCK=GP10, MOSI=GP11, MISO=GP12, CS=GP13, MOSFET (gate)=GP28
#
# Formato: WAV 16 kHz, mono, 16 bits (lo que usa Whisper).
# Una clase de 80 min ocupa unos 150 MB.
#
# Lección aprendida: NO se escribe en la memoria del Pico mientras se graba
# (se congelaba). Ahora todo va a la microSD, por trozos pequeños.

from machine import Pin, SPI, I2S
import os
import time
import struct

MIC_SCK, MIC_WS, MIC_SD = 6, 7, 8
SD_SCK, SD_MOSI, SD_MISO, SD_CS = 10, 11, 12, 13
PIN_MOSFET_SD = 28
FREC = 16000
DESPLAZAMIENTO = 12        # ganancia del micrófono: 16 = sin ganancia, 12 = x16, 11 = x32
MIC_CANAL = 0              # 0 = pin L/R del micrófono a GND (izquierdo), 1 = L/R a 3.3V (derecho)
MAX_MINUTOS = 90
CARPETA = "/sd/clases"
DESCARTAR_MS = 300         # el micrófono hace "pop" al arrancar (y vacía lo viejo)

try:
    from rapido import convertir
except Exception as e:     # firmware sin viper: versión lenta
    print("Sin viper (", e, "): grabando a 8 kHz")
    FREC = 8000

    def convertir(origen, destino, n, desplazamiento, paso=2, inicio=0):
        pico = 0
        for i in range(n):
            v = struct.unpack_from("<i", origen, (i * paso + inicio) * 4)[0] >> desplazamiento
            v = 32767 if v > 32767 else -32768 if v < -32768 else v
            struct.pack_into("<h", destino, i * 2, v)
            if abs(v) > pico:
                pico = abs(v)
        return pico

try:
    import vfs
except ImportError:
    vfs = os

_montada = False
# El micrófono y sus búferes se crean UNA vez y se reusan en todas las grabaciones
# (crearlos de nuevo cada vez fragmentaba la RAM: "memory allocation failed").
_mic = None
_crudo = None
_pcm = None
MUESTRAS = 1024                                    # 64 ms a 16 kHz


def _preparar_mic():
    global _mic, _crudo, _pcm
    if _crudo is None:
        _crudo = bytearray(MUESTRAS * 8)           # estéreo: 2 canales x 32 bits
        _pcm = bytearray(MUESTRAS * 2)
    if _mic is None:
        import gc
        gc.collect()
        _mic = I2S(1, sck=Pin(MIC_SCK), ws=Pin(MIC_WS), sd=Pin(MIC_SD), mode=I2S.RX,
                   bits=32, format=I2S.STEREO, rate=FREC, ibuf=32000)
    return _mic


def soltar_mic():
    """Para dormir: apaga el micrófono (se vuelve a crear al grabar)."""
    global _mic
    if _mic is not None:
        try:
            _mic.deinit()
        except Exception:
            pass
        _mic = None
_mosfet = None
ultimo_error = ""          # texto corto del último problema con la microSD (se muestra en pantalla)


def montar():
    """Prende y monta la microSD en /sd. Prueba el MOSFET en los dos sentidos."""
    global _montada, _mosfet, ultimo_error
    if _montada:
        return True
    import sdcard
    ultimo = None
    for valor in ((_mosfet,) if _mosfet is not None else (1, 0)):
        Pin(PIN_MOSFET_SD, Pin.OUT, value=valor)
        time.sleep_ms(300)
        try:
            spi = SPI(1, baudrate=1_000_000, sck=Pin(SD_SCK), mosi=Pin(SD_MOSI), miso=Pin(SD_MISO))
            tarjeta = sdcard.SDCard(spi, Pin(SD_CS, Pin.OUT), baudrate=10_000_000)
            vfs.mount(vfs.VfsFat(tarjeta), "/sd")
        except Exception as e:
            ultimo = e
            continue
        _montada = True
        _mosfet = valor
        ultimo_error = ""
        print("microSD lista (MOSFET=%d)" % valor)
        try:
            os.mkdir(CARPETA)
        except OSError:
            pass
        try:
            reparar()
        except Exception as e:
            print("Reparar:", e)
        return True
    texto = str(ultimo)
    print("microSD:", texto)
    if "no SD" in texto or "timeout" in texto:
        ultimo_error = "No responde"         # sin tarjeta, mal soldada o sin energía
    elif "version" in texto:
        ultimo_error = "Tarjeta rara"
    elif "19" in texto or "ENODEV" in texto or "EINVAL" in texto or "22" in texto:
        ultimo_error = "Usa FAT32"          # la tarjeta no está en FAT32
    else:
        ultimo_error = texto[:12]
    return False


def espacio_libre_mb():
    try:
        st = os.statvfs("/sd")
        return st[0] * st[3] // (1024 * 1024)
    except OSError:
        return 0


def _cabecera(bytes_audio):
    return (b"RIFF" + struct.pack("<I", 36 + bytes_audio) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, 1, FREC, FREC * 2, 2, 16) +
            b"data" + struct.pack("<I", bytes_audio))


def reparar():
    """Si el llavero se apagó grabando, arregla la cabecera del .wav."""
    for nombre in pendientes(incluir_subidos=True):
        ruta = CARPETA + "/" + nombre
        tam = os.stat(ruta)[6]
        with open(ruta, "rb") as f:
            cab = f.read(44)
        if len(cab) == 44 and struct.unpack("<I", cab[40:44])[0] != tam - 44:
            with open(ruta, "r+b") as f:
                f.write(_cabecera(tam - 44))
            print("Reparado", nombre)


def pendientes(incluir_subidos=False):
    """Grabaciones en la SD que aún no se han subido al hub."""
    try:
        todos = os.listdir(CARPETA)
    except OSError:
        return []
    return sorted(n for n in todos if n.endswith(".wav") and
                  (incluir_subidos or n + ".ok" not in todos))


def marcar_subido(nombre):
    with open(CARPETA + "/" + nombre + ".ok", "w") as f:
        f.write("1")


def nombre_nuevo():
    t = time.localtime()
    if t[0] >= 2025:
        base = "clase_%04d-%02d-%02d_%02d-%02d-%02d" % t[:6]
    else:
        base = "clase_sin_hora_%03d" % (len(pendientes(incluir_subidos=True)) + 1)
    nombre, k = base + ".wav", 2
    while _existe(CARPETA + "/" + nombre):            # nunca pisar una grabación
        nombre = "%s_%d.wav" % (base, k)
        k += 1
    return nombre


def _existe(ruta):
    try:
        os.stat(ruta)
        return True
    except OSError:
        return False


class Grabacion:
    def __init__(self):
        if not montar():
            raise OSError("Sin microSD")
        self.nombre = nombre_nuevo()
        self.ruta = CARPETA + "/" + self.nombre
        self.f = open(self.ruta, "wb")
        self.f.write(_cabecera(0))
        self.bytes = 0
        self.nivel = 0
        self.t0 = time.ticks_ms()
        self.t_flush = self.t0
        self.mic = _preparar_mic()
        self.crudo = _crudo
        self.pcm = _pcm
        self.n = 0
        fin = time.ticks_add(time.ticks_ms(), DESCARTAR_MS)
        while time.ticks_diff(fin, time.ticks_ms()) > 0:
            self.mic.readinto(self.crudo)

    def segundos(self):
        return self.bytes // (FREC * 2)

    def paso(self):
        """Lee un trozo del micrófono y lo guarda (tarda ~64 ms). Devuelve False al llegar al tope."""
        n = self.mic.readinto(self.crudo) // 8
        self.n = n
        if n:
            self.nivel = convertir(self.crudo, self.pcm, n, DESPLAZAMIENTO, 2, MIC_CANAL)
            self.f.write(memoryview(self.pcm)[:n * 2])
            self.bytes += n * 2
        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, self.t_flush) > 5000:     # cada 5 s: asegura lo grabado
            self.f.flush()
            self.t_flush = ahora
        return self.segundos() < MAX_MINUTOS * 60

    def terminar(self):
        self.f.seek(0)
        self.f.write(_cabecera(self.bytes))
        self.f.close()
        print("Grabado", self.nombre, self.segundos(), "s")
        return self.nombre
