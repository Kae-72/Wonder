"""
Wonder - manifiesto para las actualizaciones por internet  (Spyder -> F5)

Córrelo ANTES de cada commit en el que cambien archivos de "llavero".
Crea llavero/manifiesto.json con la versión (de llavero/version.txt) y el tamaño y
la huella (sha256) de cada archivo. El llavero lo lee desde GitHub para saber qué
bajar. Si se te olvida correrlo, el llavero simplemente no se actualiza (no se daña).
"""
import hashlib
import json
import os

LLAVERO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "llavero")
# Archivos que NUNCA van (son tuyos o del Pico, no del repo)
FUERA = {"manifiesto.json", "pines.json", "config.json", "wonder_estado.json", "hechos.json",
         "ajustes.json", "hora.json", "pomodoro.json", "cal.json", "wonder.raw", "wonder.ver"}


def main():
    with open(os.path.join(LLAVERO, "version.txt"), encoding="utf-8") as f:
        version = f.read().strip()
    archivos = []
    for n in sorted(os.listdir(LLAVERO)):
        ruta = os.path.join(LLAVERO, n)
        if not os.path.isfile(ruta) or n in FUERA or n.startswith(".") or n.endswith((".nuevo", ".viejo", ".tmp")):
            continue
        with open(ruta, "rb") as f:
            datos = f.read()
        archivos.append({"n": n, "t": len(datos), "h": hashlib.sha256(datos).hexdigest()})
    with open(os.path.join(LLAVERO, "manifiesto.json"), "w", encoding="utf-8") as f:
        json.dump({"version": version, "archivos": archivos}, f, indent=0)
    print(f"manifiesto.json: versión {version}, {len(archivos)} archivos, "
          f"{sum(a['t'] for a in archivos) // 1024} KB")


if __name__ == "__main__":
    main()
