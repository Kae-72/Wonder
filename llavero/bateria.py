# Wonder - nivel de batería
#
# El Pico 2 W mide su propio voltaje de entrada (VSYS) en el canal 3 del ADC.
# En tu placa: batería -> cargador -> diodo Schottky -> VSYS.
#   - Con USB conectado, VSYS sube a ~4.7-5 V  -> se muestra "cargando".
#   - Solo con batería, VSYS = batería - lo que se come el diodo (~0.25 V).
# El porcentaje sale de la curva típica de una LiPo de 3.7 V.

from machine import ADC, Pin
import time

FACTOR = 3 * 3.3 / 65535      # VSYS llega al ADC dividido entre 3
CAIDA_DIODO = 0.25            # ajústalo si al medir con multímetro no coincide
UMBRAL_USB = 4.45             # por encima de esto hay USB (la LiPo llega máx. a 4.2)

# (voltaje de la batería, porcentaje)
CURVA = ((4.15, 100), (4.05, 90), (3.97, 80), (3.90, 70), (3.84, 60), (3.79, 50),
         (3.75, 40), (3.71, 30), (3.67, 20), (3.61, 10), (3.50, 5), (3.30, 0))

_adc = None
_historial = []


def vsys(wlan=None):
    """Voltaje de VSYS. El pin 29 lo comparte el chip WiFi, así que si el WiFi
    está prendido se apaga un instante para medir. Devuelve (voltaje, apago_wifi)."""
    global _adc
    apago = False
    if wlan is not None:
        try:
            if wlan.active():
                wlan.active(False)
                apago = True
                time.sleep_ms(30)
        except Exception:
            pass
    try:
        Pin(25, Pin.OUT, value=1)          # aparta al chip WiFi del pin 29
        Pin(29, Pin.IN, pull=None)
        _adc = ADC(Pin(29))
        s = 0
        for _ in range(16):
            s += _adc.read_u16()
        v = s / 16 * FACTOR
    finally:
        if apago:
            wlan.active(True)              # el driver del WiFi vuelve a tomar el pin 29
    return v, apago


def porcentaje(v_bat):
    if v_bat >= CURVA[0][0]:
        return 100
    for (v1, p1), (v2, p2) in zip(CURVA, CURVA[1:]):
        if v_bat >= v2:
            return int(p2 + (p1 - p2) * (v_bat - v2) / (v1 - v2))
    return 0


def leer(wlan=None):
    """Devuelve (porcentaje o None, usb_conectado, voltaje_vsys o 0 si la lectura no sirve, apago_wifi)."""
    try:
        v, apago = vsys(wlan)
    except Exception as e:
        print("Bateria:", e)
        return None, False, 0, False
    print("VSYS = %.2f V" % v)
    if not 2.5 < v < 5.8:                  # lectura imposible: se ignora
        return None, False, 0, apago
    if v >= UMBRAL_USB:
        _historial.clear()
        return None, True, v, apago
    _historial.append(v + CAIDA_DIODO)
    if len(_historial) > 6:
        _historial.pop(0)
    promedio = sum(_historial) / len(_historial)
    return porcentaje(promedio), False, v, apago
