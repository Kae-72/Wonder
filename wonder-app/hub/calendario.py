"""
Wonder Hub - Google (login web) + Calendar

Basado en "CALENDARIO FINAL FINAL FINAL.py". Cambios para la app web:
  - El login ya no abre una ventana desde la consola: la app pide una URL de
    Google, el usuario autoriza y Google lo devuelve a http://localhost:PUERTO/
  - Un solo login sirve para Calendar (solo lectura) y para crear Google Docs.
  - Ademas de la tabla, entrega los eventos en el formato que lee el Pico:
        {"dia": "Lun", "fecha": "16/11", "hora": "08:00", "titulo": "Calculo"}

Necesita 'credentials.json' (OAuth "App de escritorio" de Google Cloud) en la
carpeta hub/. El token se guarda en hub/datos/token.json (no lo subas a Git).
"""

import os
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    TIMEZONE = ZoneInfo("America/Bogota")
except Exception:                       # Windows sin 'tzdata': Bogota es UTC-5 todo el ano
    TIMEZONE = timezone(timedelta(hours=-5))

# Google devuelve a http://localhost (sin https) y a veces reordena los permisos
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

SCOPE_CALENDAR = "https://www.googleapis.com/auth/calendar.events.readonly"
SCOPE_DOCS = "https://www.googleapis.com/auth/documents"
SCOPES = [SCOPE_CALENDAR, SCOPE_DOCS]

CALENDAR_ID = "primary"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATOS_DIR = os.path.join(BASE_DIR, "datos")
TOKEN_FILE = os.path.join(DATOS_DIR, "token.json")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]

_candado = threading.Lock()
_flujos = {}            # state -> (flow, hora) mientras el usuario autoriza en Google
_cache = {}             # dias -> (hora, eventos)
_cuenta = None          # correo del calendario principal (lo dice Google al listar)
CACHE_SEG = 60


class SinLogin(Exception):
    """Todavia no se ha iniciado sesion con Google (o el acceso fue revocado)."""


class FaltanLibrerias(Exception):
    """No estan instaladas las librerias de Google."""


def librerias_ok():
    try:
        import google_auth_oauthlib  # noqa: F401
        import googleapiclient       # noqa: F401
        return True
    except ImportError:
        return False


def hay_credenciales():
    return os.path.exists(CREDENTIALS_FILE)


# ---------------------------------------------------------------
# 1. Login (flujo web con regreso a localhost)
# ---------------------------------------------------------------
def url_de_login(redirect_uri):
    """Devuelve la URL de Google a la que hay que mandar al usuario."""
    if not librerias_ok():
        raise FaltanLibrerias("Faltan librerias: pip install -r requirements.txt")
    if not hay_credenciales():
        raise FileNotFoundError(
            "Falta credentials.json en la carpeta hub/. Descargalo de Google Cloud "
            "Console (OAuth 'App de escritorio')."
        )
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=redirect_uri)
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    with _candado:
        ahora = time.time()
        for viejo in [s for s, (_, t) in _flujos.items() if ahora - t > 900]:
            _flujos.pop(viejo, None)
        _flujos[state] = (flow, ahora)
    return url


def terminar_login(state, url_completa):
    """Google volvio con ?code=...: cambia el codigo por el token y lo guarda."""
    with _candado:
        entrada = _flujos.pop(state, None)
    if entrada is None:
        raise ValueError("El inicio de sesion expiro. Vuelve a pulsar el boton de Google.")
    flow = entrada[0]
    flow.fetch_token(authorization_response=url_completa)
    _guardar_token(flow.credentials)
    _olvidar_cache()


def _guardar_token(credentials):
    os.makedirs(DATOS_DIR, exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(credentials.to_json())
    try:
        os.chmod(TOKEN_FILE, 0o600)     # solo el dueno puede leerlo (Linux/Mac)
    except OSError:
        pass


def _olvidar_cache():
    global _cuenta
    with _candado:
        _cache.clear()
        _cuenta = None


def cerrar_sesion():
    """Revoca el acceso en Google (si se puede) y borra el token local."""
    try:
        creds = credenciales()
        import urllib.parse
        import urllib.request
        datos = urllib.parse.urlencode({"token": creds.refresh_token or creds.token}).encode()
        urllib.request.urlopen("https://oauth2.googleapis.com/revoke", data=datos, timeout=8).close()
    except Exception:
        pass
    try:
        os.remove(TOKEN_FILE)
    except OSError:
        pass
    _olvidar_cache()


def credenciales():
    """Credenciales validas (renueva el token si vencio) o lanza SinLogin."""
    if not librerias_ok():
        raise FaltanLibrerias("Faltan librerias: pip install -r requirements.txt")
    if not os.path.exists(TOKEN_FILE):
        raise SinLogin("Inicia sesion con Google en la app.")
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(TOKEN_FILE)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # El usuario revoco el acceso o el token vencio: pedir login de nuevo
                try:
                    os.remove(TOKEN_FILE)
                except OSError:
                    pass
                raise SinLogin("El acceso guardado ya no es valido. Inicia sesion otra vez.")
            _guardar_token(creds)
        else:
            raise SinLogin("Inicia sesion con Google en la app.")
    return creds


def estado():
    """Resumen para la app: hay credentials.json, hay sesion, que permisos dio."""
    info = {
        "librerias": librerias_ok(),
        "credenciales": hay_credenciales(),
        "conectado": False,
        "cuenta": _cuenta,
        "calendario": False,
        "docs": False,
    }
    if not info["librerias"] or not os.path.exists(TOKEN_FILE):
        return info
    try:
        permisos = set(credenciales().scopes or [])
    except (SinLogin, FaltanLibrerias):
        return info
    except Exception:                    # sin internet para renovar: hay sesion, no sabemos mas
        info["conectado"] = True
        return info
    info["conectado"] = True
    info["calendario"] = SCOPE_CALENDAR in permisos
    info["docs"] = SCOPE_DOCS in permisos
    return info


# ---------------------------------------------------------------
# 2. Leer eventos (con reintentos y paginacion)
# ---------------------------------------------------------------
def _ejecutar_con_reintentos(peticion, intentos=4):
    """Ejecuta una peticion a Google; reintenta si es un fallo temporal."""
    from googleapiclient.errors import HttpError

    for intento in range(intentos):
        try:
            return peticion.execute()
        except HttpError as e:
            codigo = e.resp.status if e.resp is not None else 0
            temporal = codigo in (429, 500, 502, 503, 504)
            if not temporal or intento == intentos - 1:
                raise
            espera = 2 ** intento
            print(f"Google respondio {codigo}; reintentando en {espera}s...")
            time.sleep(espera)


def evento(evento_id):
    """Un evento crudo de Google (para revisar un "¡Hecho!")."""
    creds = credenciales()
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    try:
        return _ejecutar_con_reintentos(service.events().get(calendarId=CALENDAR_ID, eventId=evento_id))
    except HttpError as e:
        if getattr(e, "resp", None) is not None and e.resp.status in (404, 410):
            return None
        raise


def get_events(days=7, horas_atras=0):
    """Eventos crudos de Google desde ahora (menos 'horas_atras') hasta 'days' dias despues."""
    global _cuenta
    creds = credenciales()                  # lanza SinLogin / FaltanLibrerias antes de importar nada
    from googleapiclient.discovery import build

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    now = datetime.now(TIMEZONE)
    end = now + timedelta(days=days)
    now = now - timedelta(hours=horas_atras)

    eventos = []
    page_token = None
    while True:
        peticion = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
            pageToken=page_token,
        )
        respuesta = _ejecutar_con_reintentos(peticion)
        eventos.extend(respuesta.get("items", []))
        if respuesta.get("summary"):
            _cuenta = respuesta["summary"]      # en el calendario principal es el correo
        page_token = respuesta.get("nextPageToken")
        if not page_token:
            break
    return eventos


# ---------------------------------------------------------------
# 3. Interpretar fechas
# ---------------------------------------------------------------
def _fecha(parte):
    """Devuelve (datetime en hora de Bogota, es_todo_el_dia)."""
    if "dateTime" in parte:
        dt = datetime.fromisoformat(parte["dateTime"].replace("Z", "+00:00"))
        return dt.astimezone(TIMEZONE), False
    if "date" in parte:
        # Evento de dia completo: Google envia "date" (YYYY-MM-DD), no "dateTime"
        d = datetime.fromisoformat(parte["date"])
        return d.replace(tzinfo=TIMEZONE), True
    return None, False


def solo_ascii(texto):
    """La letra del Pico no tiene tildes ni enie: 'Cálculo' -> 'Calculo'."""
    for raro, simple in (("\u2013", "-"), ("\u2014", "-"), ("\u201c", '"'), ("\u201d", '"'),
                         ("\u2018", "'"), ("\u2019", "'"), ("\u2026", "..."), ("\u00bf", ""), ("\u00a1", "")):
        texto = texto.replace(raro, simple)
    plano = unicodedata.normalize("NFKD", texto)
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in plano).strip()


# ---------------------------------------------------------------
# 4. Formatos de salida: uno para la app y uno (minimo) para el Pico
# ---------------------------------------------------------------
def simplificar(event):
    """Evento de Google -> lo unico que usa Wonder."""
    inicio, todo_el_dia = _fecha(event.get("start", {}))
    fin, _ = _fecha(event.get("end", {}))
    titulo = (event.get("summary") or "Sin titulo").strip()
    if inicio is None:
        return None
    return {
        "titulo": titulo,
        "inicio": inicio.isoformat(),
        "fin": fin.isoformat() if fin else None,
        "todo_el_dia": todo_el_dia,
        "lugar": (event.get("location") or "").strip(),
        # exactamente lo que recibe el llavero:
        "pico": {
            "id": event.get("id", ""),
            "ini": inicio.strftime("%Y-%m-%dT%H:%M"),
            "fin": (fin or inicio).strftime("%Y-%m-%dT%H:%M"),
            "dia": DIAS[inicio.weekday()],
            "fecha": inicio.strftime("%d/%m"),
            "hora": "todo dia" if todo_el_dia else inicio.strftime("%H:%M"),
            "titulo": solo_ascii(titulo) or "Sin titulo",
        },
    }


def eventos(dias=7, forzar=False, horas_atras=0):
    """Lista simplificada (con cache de 1 minuto para no saturar a Google)."""
    ahora = time.time()
    clave = (dias, horas_atras)
    with _candado:
        guardado = _cache.get(clave)
    if guardado and not forzar and ahora - guardado[0] < CACHE_SEG:
        return guardado[1]
    lista = [e for e in (simplificar(ev) for ev in get_events(dias, horas_atras)) if e]
    with _candado:
        _cache[clave] = (ahora, lista)
    return lista


def para_pico(dias=7, forzar=False, hechos=()):
    """El JSON que pide main.py del Pico en /eventos.
    Incluye las últimas 24 h, para poder marcar como hecha una clase que ya pasó."""
    lista = []
    for e in eventos(dias, forzar, horas_atras=24):
        p = dict(e["pico"])
        p["hecho"] = p["id"] in hechos
        lista.append(p)
    return {"eventos": lista, "hora": datetime.now(TIMEZONE).strftime("%H:%M")}
