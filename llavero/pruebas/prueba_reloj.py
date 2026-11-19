# Wonder - prueba del reloj (se abre en Thonny y se corre con ▶; no se sube al Pico)
#
# Revisa que la hora del Pico siga andando mientras el llavero duerme.
# 1. Conecta el llavero a internet (corre main.py un rato o deja que sincronice), o
#    escribe la hora a mano abajo en HORA_A_MANO.
# 2. Corre esta prueba: duerme 60 segundos y compara.
# Si "avanzó" dice ~60 s, el reloj funciona dormido y no hace falta el módulo DS3231.

import time
import machine

HORA_A_MANO = None          # ej. (2026, 11, 19, 3, 21, 30, 0, 0) = año, mes, día, día_semana(0=lunes), h, min, s, 0

if HORA_A_MANO:
    machine.RTC().datetime(HORA_A_MANO)

def ver(t):
    return "%04d-%02d-%02d %02d:%02d:%02d" % t[:6]

antes = time.time()
print("Hora ahora:      ", ver(time.localtime()))
if time.localtime()[0] < 2025:
    print("El Pico NO tiene hora (se reinició). Ponla con HORA_A_MANO o deja que se conecte.")
print("Durmiendo 60 s (lightsleep, como cuando el llavero se duerme)...")
time.sleep_ms(200)
for _ in range(400):
    machine.lightsleep(150)
despues = time.time()
print("Hora al despertar:", ver(time.localtime()))
print("Avanzó: %d s  (debería ser ~60)" % (despues - antes))
if abs((despues - antes) - 60) <= 3:
    print("OK: el reloj sigue andando dormido.")
else:
    print("OJO: el reloj no anduvo bien dormido. Cuéntale a Claude este resultado.")
