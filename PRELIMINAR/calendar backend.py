"""
Wonder - Backend de Google Calendar (solo lectura)

Muestra en pantalla los proximos eventos de tu Google Calendar, en forma
de tabla:  dd/mm/aaaa | hh:mm | titulo

Instalar:
    pip install google-api-python-client google-auth-oauthlib
    (en Windows ademas:  pip install tzdata  -> trae las zonas horarias)

Necesitas 'credentials.json' (OAuth "App de escritorio" de Google Cloud)
junto a este archivo. La primera vez se abre el navegador para autorizar
y se crea 'token.json' (no lo subas a Git: agregalo a .gitignore).

Uso:
    python calendar_backend.py              -> muestra los eventos de los proximos 7 dias
    python calendar_backend.py 14           -> muestra los eventos de los proximos 14 dias
    python calendar_backend.py --servir     -> ademas se los entrega al Pico por WiFi
    python calendar_backend.py 14 --servir  -> lo mismo, con 14 dias

Para el Pico: cambia CLAVE (abajo) o define la variable de entorno WONDER_CLAVE,
y pon la misma clave en calendario_pico.py.
"""

import json
import os
import socket
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ---------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------
# Solo lectura de eventos (el permiso mas restringido que sirve aqui).
SCOPES_CALENDAR = [
    "https://www.googleapis.com/auth/calendar.events.readonly"
]

TIMEZONE = ZoneInfo("America/Bogota")
CALENDAR_ID = "primary"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

# Servidor para el Pico (modo --servir)
PUERTO = 8000
REFRESCO_SEG = 300      # vuelve a consultar Google cada 5 minutos
# Clave compartida con el Pico: sin ella el servidor no entrega nada.
CLAVE = os.environ.get("WONDER_CLAVE", "cambia-esta-clave")
DIAS_SEMANA = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]

# ---------------------------------------------------------------
# 1. Autenticacion
# ---------------------------------------------------------------
def _login_nuevo():
    """Abre el navegador para que el usuario autorice y guarda el token."""
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"Falta {CREDENTIALS_FILE}. Descargalo de Google Cloud Console "
            "(OAuth 'App de escritorio') y ponlo junto a este script."
        )
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES_CALENDAR)
    return flow.run_local_server(port=0)

def _guardar_token(credentials):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(credentials.to_json())
    try:
        os.chmod(TOKEN_FILE, 0o600)  # solo el dueno puede leerlo (Linux/Mac)
    except OSError:
        pass

def connect_calendar():
    credentials = None

    if os.path.exists(TOKEN_FILE):
        credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES_CALENDAR)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                # El usuario revoco el acceso o el token vencio: pedir login de nuevo
                print("El acceso guardado ya no es valido. Inicia sesion otra vez.")
                try:
                    os.remove(TOKEN_FILE)
                except OSError:
                    pass
                credentials = _login_nuevo()
        else:
            credentials = _login_nuevo()

        _guardar_token(credentials)

    return build("calendar", "v3", credentials=credentials)

# ---------------------------------------------------------------
# 2. Leer eventos (con reintentos y paginacion)
#    Calcula el rango (desde ahora hasta N dias despues) y pide
#    los eventos a Google ordenados por hora de inicio.
# ---------------------------------------------------------------
def _ejecutar_con_reintentos(peticion, intentos=4):
    """Ejecuta una peticion a Google; reintenta si es un fallo temporal."""
    for intento in range(intentos):
        try:
            return peticion.execute()
        except HttpError as e:
            codigo = e.resp.status if e.resp is not None else 0
            temporal = codigo in (403, 429, 500, 502, 503, 504)
            if not temporal or intento == intentos - 1:
                raise
            espera = 2 ** intento
            print(f"Google respondio {codigo}; reintentando en {espera}s...")
            time.sleep(espera)

def get_events(service, days=7):
    now = datetime.now(TIMEZONE)
    end = now + timedelta(days=days)

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

        page_token = respuesta.get("nextPageToken")
        if not page_token:
            break

    return eventos

# ---------------------------------------------------------------
# 3. Interpretar fechas
# ---------------------------------------------------------------
def _inicio_evento(event):
    """Devuelve (datetime, es_todo_el_dia). El datetime esta en hora de Bogota."""
    start = event.get("start", {})

    if "dateTime" in start:
        dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
        return dt.astimezone(TIMEZONE), False

    if "date" in start:
        # Evento de dia completo: Google envia "date" (YYYY-MM-DD), no "dateTime"
        d = datetime.fromisoformat(start["date"])
        return d.replace(tzinfo=TIMEZONE), True

    return None, False

# ---------------------------------------------------------------
# 4. Mostrar en pantalla (la tabla del tamagotchi)
#    Recorre la lista de eventos uno por uno, convierte cada fecha
#    y hora a la zona de Bogota y la muestra con formato de tabla
#    (dd/mm/aaaa | hh:mm | titulo).
# ---------------------------------------------------------------
def print_events(events):
    print("MY GOOGLE CALENDAR")
    print("=" * 50)

    if not events:
        print("No upcoming events.")
        return

    for event in events:
        title = event.get("summary", "Untitled event")
        dt, todo_el_dia = _inicio_evento(event)

        if dt is None:
            date_text, time_text = "??/??/????", "??:??"
        else:
            date_text = dt.strftime("%d/%m/%Y")
            time_text = "All day" if todo_el_dia else dt.strftime("%H:%M")

        print(f"{date_text} | {time_text} | {title}")

# ---------------------------------------------------------------
# 5. Servidor para el Pico (modo --servir)
#    El Pico pide /eventos por WiFi y recibe la misma tabla en JSON,
#    sin tildes (la pantalla solo tiene letras basicas).
# ---------------------------------------------------------------
def _a_ascii(texto):
    texto = unicodedata.normalize("NFKD", texto)
    return texto.encode("ascii", "ignore").decode("ascii")

def eventos_para_pico(events):
    tabla = []
    for event in events:
        dt, todo_el_dia = _inicio_evento(event)
        if dt is None:
            continue
        tabla.append({
            "dia": DIAS_SEMANA[dt.weekday()],
            "fecha": dt.strftime("%d/%m"),
            "hora": "Todo dia" if todo_el_dia else dt.strftime("%H:%M"),
            "titulo": _a_ascii(event.get("summary", "Sin titulo"))[:60],
        })
    return tabla

class _Cache:
    service = None
    dias = 7
    tabla = []
    momento = 0.0

def _refrescar_si_hace_falta():
    if time.time() - _Cache.momento < REFRESCO_SEG:
        return
    try:
        events = get_events(_Cache.service, days=_Cache.dias)
        _Cache.tabla = eventos_para_pico(events)
        _Cache.momento = time.time()
        print(f"[{datetime.now():%H:%M:%S}] Calendario actualizado: {len(_Cache.tabla)} eventos")
    except Exception as e:
        # Si Google falla, el Pico recibe la ultima tabla buena
        print(f"[{datetime.now():%H:%M:%S}] Error leyendo Google Calendar: {e}")

class _ManejadorPico(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/eventos":
            self.send_error(404)
            return
        if self.headers.get("X-Wonder-Key") != CLAVE:
            self.send_error(403, "Clave incorrecta")
            return
        _refrescar_si_hace_falta()
        cuerpo = json.dumps({
            "hora": datetime.now(TIMEZONE).strftime("%H:%M"),
            "eventos": _Cache.tabla,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, fmt, *args):
        print(f"[{datetime.now():%H:%M:%S}] Pico {self.client_address[0]} -> {fmt % args}")

def _ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no envia nada; solo averigua la IP del PC en la red
        return s.getsockname()[0]
    finally:
        s.close()

def servir_al_pico(service, dias):
    _Cache.service = service
    _Cache.dias = dias
    _refrescar_si_hace_falta()
    if CLAVE == "cambia-esta-clave":
        print("AVISO: estas usando la clave por defecto. Cambiala (y ponla igual en el Pico).")
    print("\nServidor para el Pico listo. En calendario_pico.py pon:")
    print(f'    SERVIDOR = "http://{_ip_local()}:{PUERTO}/eventos"')
    print("Si Windows pregunta por el firewall, permite el acceso en redes PRIVADAS.")
    print("Ctrl+C para detener.\n")
    try:
        ThreadingHTTPServer(("0.0.0.0", PUERTO), _ManejadorPico).serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")

# ---------------------------------------------------------------
# 6. Programa principal
# ---------------------------------------------------------------
def main():
    args = sys.argv[1:]
    numeros = [a for a in args if a.isdigit()]
    dias = int(numeros[0]) if numeros else 7

    try:
        service = connect_calendar()
        events = get_events(service, days=dias)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
    except HttpError as e:
        print(f"Google Calendar devolvio un error: {e}")
        sys.exit(1)

    print_events(events)

    if "--servir" in args:
        servir_al_pico(service, dias)

if __name__ == "__main__":
    main()
