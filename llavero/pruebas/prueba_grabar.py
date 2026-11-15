# Wonder - PRUEBA DE LA GRABADORA (microSD + micrófono), sin el resto del llavero
#
# Antes: grabadora.py, sdcard.py y rapido.py tienen que estar en el Pico.
# Abre este archivo en Thonny y pulsa Run. Todo sale en el Shell, paso por paso.
# Cuando diga "HABLA AHORA", habla normal a unos 30 cm del llavero.

import time
import gc
import os

print()
print("=== 1. MICROSD ===")
gc.collect()
print("RAM libre:", gc.mem_free())
import grabadora

if not grabadora.montar():
    print("FALLO la microSD:", grabadora.ultimo_error)
    print("Revisa: tarjeta puesta, formateada en FAT32 (32 GB o menos es lo más seguro),")
    print("y los cables SCK=GP10, MOSI=GP11, MISO=GP12, CS=GP13, VCC y GND del módulo.")
    raise SystemExit
print("OK microSD. Libre:", grabadora.espacio_libre_mb(), "MB")
with open("/sd/prueba.txt", "w") as f:
    f.write("hola wonder")
with open("/sd/prueba.txt") as f:
    print("Escribir y leer:", "OK" if f.read() == "hola wonder" else "FALLO")
os.remove("/sd/prueba.txt")

print()
print("=== 2. MICRÓFONO (5 segundos) ===")
gc.collect()
try:
    g = grabadora.Grabacion()
except Exception as e:
    print("FALLO al abrir el micrófono:", e)
    raise
print("HABLA AHORA...")
otro = 1 - grabadora.MIC_CANAL
basura = bytearray(len(g.pcm))
picos, picos_otro = [], []
crudo_todo_cero = True
crudo_todo_uno = True
t_print = time.ticks_ms()
p1 = p2 = 0
while g.segundos() < 5:
    g.paso()
    p1 = max(p1, g.nivel)
    p2 = max(p2, grabadora.convertir(g.crudo, basura, g.n, grabadora.DESPLAZAMIENTO, 2, otro))
    if any(g.crudo[:64]):
        crudo_todo_cero = False
    if any(b != 0xFF for b in g.crudo[:64]):
        crudo_todo_uno = False
    if time.ticks_diff(time.ticks_ms(), t_print) > 500:
        t_print = time.ticks_ms()
        print("  nivel %5d %-30s (otro canal %5d)" % (p1, "#" * min(30, p1 * 30 // 32767), p2))
        picos.append(p1)
        picos_otro.append(p2)
        p1 = p2 = 0
nombre = g.terminar()
print("Guardado en la microSD:", grabadora.CARPETA + "/" + nombre)

print()
print("=== RESULTADO ===")
maximo = max(picos) if picos else 0
maximo_otro = max(picos_otro) if picos_otro else 0
if maximo == 0 and maximo_otro > 0:
    print("El micrófono SÍ funciona, pero manda el sonido por el OTRO canal.")
    print("En grabadora.py cambia MIC_CANAL = %d   (o conecta L/R del micrófono a %s)."
          % (otro, "3.3V" if otro else "GND"))
elif maximo == 0:
    if crudo_todo_cero:
        print("El micrófono no manda nada: la línea de datos está siempre en 0.")
        print("Revisa: SD del micrófono -> GP8, VDD a 3.3V, GND, y que SCK=GP6 y WS=GP7.")
    elif crudo_todo_uno:
        print("La línea de datos está siempre en 1: el pin SD del micrófono está suelto o al aire.")
        print("Revisa la soldadura de SD -> GP8.")
    else:
        print("Llegan datos pero sin sonido: revisa que SCK y WS no estén invertidos (GP6 y GP7).")
elif maximo >= 32000:
    print("Suena saturado. En grabadora.py sube DESPLAZAMIENTO en 1 (ahora es %d)." % grabadora.DESPLAZAMIENTO)
elif maximo < 2000:
    print("Suena muy bajito. En grabadora.py baja DESPLAZAMIENTO en 1 (ahora es %d)." % grabadora.DESPLAZAMIENTO)
else:
    print("El nivel está bien. La grabadora funciona.")
print("Frecuencia:", grabadora.FREC, "Hz  (8000 = falta viper; 16000 = normal)")
