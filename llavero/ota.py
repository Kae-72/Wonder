# Wonder - actualizaciones por internet (desde GitHub)
#
# El llavero descarga los archivos nuevos directo del repositorio PÚBLICO de GitHub
# (no hace falta el hub ni el computador prendido):
#   https://raw.githubusercontent.com/Kae-72/Wonder/main/llavero/
#
# En el repo, llavero/manifiesto.json dice la versión y el tamaño + huella (sha256)
# de cada archivo. Se crea con herramientas/hacer_manifiesto.py ANTES de cada commit.
#
# Es seguro:
#   1. Primero baja TODO a archivos temporales (*.nuevo) y revisa tamaño y huella.
#   2. Solo si todo llegó bien, cambia los archivos (el viejo queda como *.viejo
#      hasta el final, para poder volver atrás si algo falla).
#   3. NUNCA toca tus datos: botones, redes, Wonder, ¡Hecho!, ajustes, hora...

import os
import json
import gc

try:
    import requests
except ImportError:
    import urequests as requests

BASE = "https://raw.githubusercontent.com/Kae-72/Wonder/main/llavero/"
PROTEGIDOS = ("pines.json", "config.json", "wonder_estado.json", "hechos.json", "ajustes.json",
              "hora.json", "pomodoro.json", "cal.json", "wonder.raw", "wonder.ver", "main_viejo.py")


def _existe(n):
    try:
        os.stat(n)
        return True
    except OSError:
        return False


def _tam(n):
    try:
        return os.stat(n)[6]
    except OSError:
        return -1


def _borrar(n):
    try:
        os.remove(n)
    except OSError:
        pass


def huella(nombre):
    """sha256 del archivo en texto hexadecimal (None si el Pico no sabe calcularla)."""
    try:
        import hashlib
        import binascii
    except ImportError:
        return None
    h = hashlib.sha256()
    trozo = bytearray(1024)
    vista = memoryview(trozo)
    with open(nombre, "rb") as f:
        while True:
            n = f.readinto(trozo)
            if not n:
                break
            h.update(vista[:n])
    return binascii.hexlify(h.digest()).decode()


def version_local():
    try:
        with open("version.txt") as f:
            return f.read().strip()
    except OSError:
        return "?"


def _necesita(a):
    if _tam(a["n"]) != a["t"]:
        return True
    hl = huella(a["n"])
    return hl is not None and hl != a.get("h")


def buscar():
    """(versión_en_GitHub, [archivos que cambiaron]). Lanza OSError si no hay internet."""
    gc.collect()
    r = requests.get(BASE + "manifiesto.json", timeout=15)
    try:
        if r.status_code != 200:
            raise OSError("GitHub %d" % r.status_code)
        man = json.loads(r.text)
    finally:
        r.close()
    cambios = [a for a in man.get("archivos", [])
               if a["n"] not in PROTEGIDOS and "/" not in a["n"] and _necesita(a)]
    return str(man.get("version", "?")), cambios


def _descargar(a, al_avanzar):
    gc.collect()
    r = requests.get(BASE + a["n"], timeout=20)
    falta = a["t"]
    try:
        if r.status_code != 200:
            raise OSError("%s: %d" % (a["n"], r.status_code))
        trozo = bytearray(1024)
        vista = memoryview(trozo)
        with open(a["n"] + ".nuevo", "wb") as f:
            while falta > 0:
                n = r.raw.readinto(trozo)
                if not n:
                    break
                f.write(vista[:min(n, falta)])
                falta -= n
                if al_avanzar:
                    al_avanzar(a["t"] - max(falta, 0))
    finally:
        r.close()
    if _tam(a["n"] + ".nuevo") != a["t"]:
        raise OSError("Incompleto: " + a["n"])
    hl = huella(a["n"] + ".nuevo")
    if hl is not None and a.get("h") and hl != a["h"]:
        raise OSError("Huella: " + a["n"])


def espacio_libre():
    s = os.statvfs("/")
    return s[0] * s[3]


def actualizar(cambios, al_avanzar=None):
    """Baja y cambia los archivos. al_avanzar(k, total, nombre, bytes) para la pantalla.
    Si algo falla, deja todo como estaba y lanza OSError."""
    total = sum(a["t"] for a in cambios)
    if espacio_libre() < total + 30000:
        raise OSError("Falta espacio")
    try:
        for k, a in enumerate(cambios):
            if al_avanzar:
                al_avanzar(k, len(cambios), a["n"], 0)
            _descargar(a, (lambda b, k=k, a=a: al_avanzar(k, len(cambios), a["n"], b))
                       if al_avanzar else None)
    except Exception:
        for a in cambios:
            _borrar(a["n"] + ".nuevo")
        raise
    # todo llegó bien: ahora sí se cambian los archivos
    hechos = []
    try:
        for a in cambios:
            if _existe(a["n"]):
                _borrar(a["n"] + ".viejo")
                os.rename(a["n"], a["n"] + ".viejo")
            os.rename(a["n"] + ".nuevo", a["n"])
            hechos.append(a["n"])
    except Exception:
        for a in cambios:                             # volver atrás: todo como estaba
            n = a["n"]
            if n in hechos:
                _borrar(n)
            if not _existe(n) and _existe(n + ".viejo"):
                os.rename(n + ".viejo", n)
            _borrar(n + ".nuevo")
        raise
    for a in cambios:
        _borrar(a["n"] + ".viejo")
