"""
Wonder - "¡Hecho!": marcar tareas y clases cumplidas, con reglas para que no haya trampa.

El llavero manda el id del evento de Google Calendar y la hora en que se marcó.
El hub lo revisa contra Google (no se le cree al llavero) y lo guarda en datos/logros.json.

Reglas:
  1. Tiene que ser un evento real del calendario (no cancelado).
  2. Un evento se marca una sola vez.
  3. Solo desde que empieza hasta 12 horas después de que termina
     (no se puede marcar algo que todavía no ha pasado).
  4. El evento tiene que existir en el calendario desde ANTES de empezar
     (no vale crear un evento "en el pasado" y marcarlo).
  5. Máximo MAX_POR_DIA marcados por día.
"""

import json
import os
import threading
from datetime import datetime, timedelta

import calendario

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
ARCHIVO = os.path.join(CARPETA, "logros.json")
MAX_POR_DIA = 8
PLAZO_DESPUES = timedelta(hours=12)
TOLERANCIA_RELOJ = timedelta(minutes=5)

_candado = threading.Lock()


class Rechazado(Exception):
    """El evento no cumple una regla. El mensaje es corto para la pantalla del llavero."""


def _leer():
    try:
        with open(ARCHIVO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"hechos": {}}


def _escribir(datos):
    os.makedirs(CARPETA, exist_ok=True)
    tmp = ARCHIVO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(tmp, ARCHIVO)


def ids_hechos():
    return set(_leer()["hechos"])


def _hora_local(texto):
    """'2026-11-15T09:30' (hora de Bogotá, como la manda el llavero) -> datetime."""
    return datetime.fromisoformat(texto[:16]).replace(tzinfo=calendario.TIMEZONE)


def marcar(evento_id, cuando_texto=None):
    ahora = datetime.now(calendario.TIMEZONE)
    cuando = ahora
    if cuando_texto:
        try:
            cuando = _hora_local(cuando_texto)
        except ValueError:
            raise Rechazado("Hora invalida")
    if cuando > ahora + TOLERANCIA_RELOJ:
        raise Rechazado("Hora del futuro")

    with _candado:
        datos = _leer()
        if evento_id in datos["hechos"]:
            raise Rechazado("Ya estaba hecho")

        ev = calendario.evento(evento_id)                       # se pregunta a Google
        if not ev or ev.get("status") == "cancelled":
            raise Rechazado("No existe")
        inicio, todo_el_dia = calendario._fecha(ev.get("start", {}))
        fin, _ = calendario._fecha(ev.get("end", {}))
        fin = fin or inicio
        creado = datetime.fromisoformat(ev["created"].replace("Z", "+00:00")) if ev.get("created") else None

        if cuando < inicio:
            raise Rechazado("Aun no empieza")
        if cuando > fin + PLAZO_DESPUES:
            raise Rechazado("Ya paso el plazo")
        if creado and creado > inicio + TOLERANCIA_RELOJ:
            raise Rechazado("Creado muy tarde")
        dia = cuando.date().isoformat()
        hoy = sum(1 for h in datos["hechos"].values() if h["marcado"][:10] == dia)
        if hoy >= MAX_POR_DIA:
            raise Rechazado("Limite del dia")

        datos["hechos"][evento_id] = {
            "titulo": (ev.get("summary") or "Sin titulo").strip(),
            "inicio": inicio.isoformat(),
            "marcado": cuando.isoformat(),
        }
        _escribir(datos)
    return resumen()


def resumen():
    hechos = list(_leer()["hechos"].values())
    hoy = datetime.now(calendario.TIMEZONE).date()
    dias = {h["marcado"][:10] for h in hechos}
    racha = 0
    d = hoy if hoy.isoformat() in dias else hoy - timedelta(days=1)
    while d.isoformat() in dias:
        racha += 1
        d -= timedelta(days=1)
    ultimos = sorted(hechos, key=lambda h: h["marcado"], reverse=True)[:5]
    return {
        "total": len(hechos),
        "hoy": sum(1 for h in hechos if h["marcado"][:10] == hoy.isoformat()),
        "racha": racha,
        "max_por_dia": MAX_POR_DIA,
        "ultimos": [{"titulo": h["titulo"], "marcado": h["marcado"]} for h in ultimos],
    }
