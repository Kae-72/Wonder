# Wonder - batería
#
# En el Pico 2 W el pin que mide VSYS (GP29) lo usa el chip WiFi desde que el Pico
# arranca: tocarlo deja el WiFi colgado (timeouts). Por eso el llavero NO lo toca.
#
# Lo que sí se puede saber siempre: si hay USB conectado (el chip WiFi lo dice
# por su pin WL_GPIO2). La barra muestra el rayo con USB y "?" sin USB.
#
# Para ver el PORCENTAJE hace falta un arreglo de hardware de 2 resistencias:
#   Batería + (salida OUT+ del cargador) --[100k]--+--[100k]-- GND
#                                                  |
#                                                GP27 (patita 32)
# y poner PIN_BATERIA = 27 abajo. (GP27 está libre si no usan el sensor de vibración.)

from machine import ADC, Pin

PIN_BATERIA = None            # 27 si se hace el divisor de arriba
DIVISOR = 2.0                 # 100k / 100k divide entre 2
FACTOR = 3.3 / 65535

CURVA = ((4.15, 100), (4.05, 90), (3.97, 80), (3.90, 70), (3.84, 60), (3.79, 50),
         (3.75, 40), (3.71, 30), (3.67, 20), (3.61, 10), (3.50, 5), (3.30, 0))

_historial = []


def porcentaje(v_bat):
    if v_bat >= CURVA[0][0]:
        return 100
    for (v1, p1), (v2, p2) in zip(CURVA, CURVA[1:]):
        if v_bat >= v2:
            return int(p2 + (p1 - p2) * (v_bat - v2) / (v1 - v2))
    return 0


def usb_conectado():
    """True/False si hay USB; None si no se puede saber."""
    try:
        return Pin("WL_GPIO2", Pin.IN).value() == 1
    except Exception:
        return None


def leer():
    """Devuelve (porcentaje o None, usb_conectado, voltaje o 0)."""
    usb = bool(usb_conectado())
    if PIN_BATERIA is None:
        return None, usb, 0
    try:
        adc = ADC(Pin(PIN_BATERIA))
        s = 0
        for _ in range(16):
            s += adc.read_u16()
        v = s / 16 * FACTOR * DIVISOR
    except Exception as e:
        print("Bateria:", e)
        return None, usb, 0
    _historial.append(v)
    if len(_historial) > 6:
        _historial.pop(0)
    return porcentaje(sum(_historial) / len(_historial)), usb, v
