# Wonder - conversión rápida del micrófono (código "viper": casi tan rápido como C)
# Va en un archivo aparte: si el firmware no soporta viper, grabadora.py usa
# una versión lenta en Python y graba a menor calidad, en vez de fallar.

import micropython


@micropython.viper
def convertir(origen, destino, n: int, desplazamiento: int, paso: int, inicio: int) -> int:
    """Muestras de 32 bits del INMP441 -> 16 bits con ganancia.
    El I2S llega en estéreo (izq, der, izq, der...): 'paso' = 2 e 'inicio' = canal.
    Devuelve el pico (volumen máximo) del trozo, para el medidor."""
    s = ptr32(origen)
    d = ptr16(destino)
    pico = 0
    for i in range(n):
        v = s[i * paso + inicio] >> desplazamiento
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        d[i] = v
        if v < 0:
            v = 0 - v
        if v > pico:
            pico = v
    return pico
