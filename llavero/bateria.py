# Wonder - nivel de batería
#
# El Pico 2 W mide su propio voltaje de entrada (VSYS) en el canal 3 del ADC.
# En tu placa: batería -> cargador -> diodo Schottky -> VSYS.
#   - Con USB conectado, VSYS sube a ~4.7-5 V  -> se muestra "cargando".
#   - Solo con batería, VSYS = batería - lo que se come el diodo (~0.25 V).
# El porcentaje sale de la curva típica de una LiPo de 3.7 V.

from machine import ADC

FACTOR = 3 * 3.3 / 65535      # VSYS llega al ADC dividido entre 3
CAIDA_DIODO = 0.25            # ajústalo si al medir con multímetro no coincide
UMBRAL_USB = 4.45             # por encima de esto hay USB (la LiPo llega máx. a 4.2)

# (voltaje de la batería, porcentaje)
CURVA = ((4.15, 100), (4.05, 90), (3.97, 80), (3.90, 70), (3.84, 60), (3.79, 50),
         (3.75, 40), (3.71, 30), (3.67, 20), (3.61, 10), (3.50, 5), (3.30, 0))

_adc = None
_historial = []


def vsys():
    global _adc
    if _adc is None:
        _adc = ADC(3)          # canal 3 = VSYS/3 (no se toca el pin 29: lo usa el WiFi)
    s = 0
    for _ in range(8):
        s += _adc.read_u16()
    return s / 8 * FACTOR


def porcentaje(v_bat):
    if v_bat >= CURVA[0][0]:
        return 100
    for (v1, p1), (v2, p2) in zip(CURVA, CURVA[1:]):
        if v_bat >= v2:
            return int(p2 + (p1 - p2) * (v_bat - v2) / (v1 - v2))
    return 0


def leer():
    """Devuelve (porcentaje o None, usb_conectado, voltaje_vsys)."""
    try:
        v = vsys()
    except Exception as e:
        print("Bateria:", e)
        return None, False, 0
    if v >= UMBRAL_USB:
        _historial.clear()
        return None, True, v
    _historial.append(v + CAIDA_DIODO)
    if len(_historial) > 6:
        _historial.pop(0)
    promedio = sum(_historial) / len(_historial)
    return porcentaje(promedio), False, v
