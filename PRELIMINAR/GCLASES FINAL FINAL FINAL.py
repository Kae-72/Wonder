"""
Grabador de clases: graba -> transcribe (Whisper) -> resume (Gemini) -> exporta (Word / Google Docs)

El usuario SOLO pulsa el boton:
  - Raspberry Pi: graba con el boton GPIO 17 y guarda el audio en ~/clases,
    carpeta que Syncthing copia sola al computador.
  - Computador (prendido): vigila ~/clases y, cuando llega un audio nuevo,
    lo transcribe (Whisper), lo resume (Gemini) y crea el Word y el Google Doc.

Instalar:
  En la Raspberry Pi:
      sudo apt install libportaudio2 ffmpeg syncthing
      pip install sounddevice soundfile gpiozero lgpio

  En el computador:
      pip install openai-whisper google-genai python-docx
      pip install google-api-python-client google-auth-oauthlib
      (ffmpeg instalado en el sistema, y Syncthing)

Como usarlo:
  MODO AUTOMATICO:
    - En la Pi:            python3 grabador_clases.py pi
    - En el computador:    python grabador_clases.py vigilar

  MODO MANUAL (pruebas):
    - python grabador_clases.py grabar
    - python grabador_clases.py procesar archivo.wav
    - python grabador_clases.py todo

Clave de Gemini (NO la escribas en el codigo):
      export GEMINI_API_KEY='tu_clave'      (Linux / Mac / Pi)
      setx GEMINI_API_KEY "tu_clave"        (Windows, permanente)
"""

import os
import re
import sys
import queue
import threading
import time
from datetime import datetime

# ---------------------------------------------------------------
# Configuracion general
# ---------------------------------------------------------------
DURATION_MINUTES = 80   # tope de seguridad: para solo a los 80 min
FS = 16000              # 16 kHz: lo que usa Whisper
CHANNELS = 1
BOTON_PIN = 17          # el boton va al GPIO 17 (y a GND)

# Carpeta que Syncthing mantiene igual en la Pi y en el computador.
CARPETA_CLASES = os.path.expanduser("~/clases")

# Rutas fijas, junto al script (no dependen de desde donde se lance)
CARPETA_SCRIPT = os.path.dirname(os.path.abspath(__file__))
CARPETA_RESULTADOS = os.path.join(CARPETA_SCRIPT, "resultados")
TOKEN_DOCS = os.path.join(CARPETA_SCRIPT, "token_docs.json")
CREDENCIALES = os.path.join(CARPETA_SCRIPT, "credentials.json")

MODELO_GEMINI = "gemini-flash-latest"
MODELO_GEMINI_RESPALDO = "gemini-2.5-flash"

SCOPES = ["https://www.googleapis.com/auth/documents"]


def nombre_base_nuevo():
    """Nombre con fecha/hora/segundos, p.ej. clase_2026-11-10_10-00-05."""
    return datetime.now().strftime("clase_%Y-%m-%d_%H-%M-%S")


# ===============================================================
# PARTE 1: grabar con el boton fisico (en la Raspberry Pi)
# ===============================================================
def grabar_con_boton(nombre_archivo=None):
    """1er toque: empieza. 2o toque: para y guarda.
    Graba en un archivo .part y lo renombra a .wav al terminar,
    para que Syncthing nunca copie un audio a medias."""
    import sounddevice as sd
    import soundfile as sf
    from gpiozero import Button

    if nombre_archivo is None:
        nombre_archivo = f"{nombre_base_nuevo()}.wav"

    boton = Button(BOTON_PIN, pull_up=True, bounce_time=0.2)

    cola = queue.Queue()
    grabando = threading.Event()
    detener = threading.Event()

    def callback(indata, frames, time_info, status):
        if status:
            print(status)
        if grabando.is_set():
            cola.put(indata.copy())

    def al_pulsar():
        if not grabando.is_set():
            print("Grabacion INICIADA (pulsa de nuevo para parar)")
            grabando.set()
        else:
            print("Grabacion DETENIDA")
            detener.set()

    boton.when_pressed = al_pulsar

    print("Listo. Pulsa el boton para EMPEZAR a grabar...")

    try:
        try:
            while not grabando.is_set():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nCancelado antes de empezar. No se grabo nada.")
            return None

        fin = time.time() + DURATION_MINUTES * 60
        temporal = nombre_archivo + ".part"

        with sf.SoundFile(temporal, mode="w", samplerate=FS,
                          channels=CHANNELS, format="WAV") as archivo:
            with sd.InputStream(samplerate=FS, channels=CHANNELS, callback=callback):
                try:
                    while not detener.is_set() and time.time() < fin:
                        try:
                            archivo.write(cola.get(timeout=1))
                        except queue.Empty:
                            pass
                except KeyboardInterrupt:
                    print("\nGrabacion detenida manualmente.")

                # vaciar lo que quede en la cola para no perder el final
                while not cola.empty():
                    archivo.write(cola.get())

        # Recien ahora el archivo aparece como .wav (ya esta completo)
        os.replace(temporal, nombre_archivo)

        if not detener.is_set() and time.time() >= fin:
            print(f"Se alcanzo el tope de {DURATION_MINUTES} min, grabacion detenida.")
        print(f"Grabacion terminada. Audio guardado en {nombre_archivo}")
        return nombre_archivo
    finally:
        boton.close()


# ===============================================================
# PARTE 2: transcribir con Whisper (en el computador)
# ===============================================================
def transcribir(ruta_audio, modelo_nombre="small"):
    """Transcribe a texto en espanol y guarda un .txt al lado del audio."""
    import whisper

    if not os.path.exists(ruta_audio):
        raise FileNotFoundError(f"No encuentro el archivo de audio: {ruta_audio}")

    print(f"Cargando modelo Whisper '{modelo_nombre}' (puede tardar la primera vez)...")
    modelo = whisper.load_model(modelo_nombre)

    print("Transcribiendo... (esto tarda segun la duracion del audio)")
    resultado = modelo.transcribe(ruta_audio, language="es", fp16=False)
    texto = resultado["text"].strip()

    ruta_txt = os.path.splitext(ruta_audio)[0] + ".txt"
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"Transcripcion guardada en {ruta_txt}")
    return texto


# ===============================================================
# PARTE 3: resumir con Gemini
# ===============================================================
def _leer_api_key():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta la variable de entorno GEMINI_API_KEY.\n"
            "Consiguela en https://aistudio.google.com/api-keys"
        )
    return api_key


def listar_modelos():
    from google import genai

    cliente = genai.Client(api_key=_leer_api_key())
    print("Modelos disponibles para tu clave:")
    for m in cliente.models.list():
        print(" -", m.name)


def limpiar_markdown(texto):
    """Quita simbolos de Markdown para que Word / Google Docs no muestren ** o #."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"__(.+?)__", r"\1", texto)
    texto = re.sub(r"^\s{0,3}#{1,6}\s*", "", texto, flags=re.M)
    texto = re.sub(r"^\s*[\*\-]\s+", "- ", texto, flags=re.M)
    texto = re.sub(r"(?<!\w)\*(?!\s)(.+?)\*(?!\w)", r"\1", texto)
    texto = texto.replace("`", "")
    return texto.strip()


def resumir(texto):
    from google import genai

    cliente = genai.Client(api_key=_leer_api_key())

    prompt = (
        "Eres un asistente que toma apuntes de clases universitarias. "
        "Responde en espanol, claro y organizado. "
        "Usa SOLO texto plano: nada de Markdown, sin asteriscos, sin #. "
        "Para listas usa guiones simples (-).\n\n"
        "Esta es la transcripcion de una clase. Hazme:\n"
        "1) Un resumen corto\n"
        "2) Los puntos clave\n"
        "3) Conceptos o definiciones importantes\n"
        "4) Tareas o fechas mencionadas (si las hay)\n\n"
        f"Transcripcion:\n{texto}"
    )

    for modelo in (MODELO_GEMINI, MODELO_GEMINI_RESPALDO):
        try:
            print(f"Resumiendo con Gemini ({modelo})...")
            respuesta = cliente.models.generate_content(model=modelo, contents=prompt)
            texto_resumen = (respuesta.text or "").strip()
            if texto_resumen:
                return limpiar_markdown(texto_resumen)
            print(f"  El modelo {modelo} no devolvio texto, probando otro...")
        except Exception as e:
            print(f"  Fallo el modelo {modelo}: {e}")
            print("  Probando con el siguiente modelo...")

    raise RuntimeError(
        "No se pudo generar el resumen con ningun modelo. "
        "Ejecuta 'python grabador_clases.py modelos' y ajusta MODELO_GEMINI."
    )


# ===============================================================
# PARTE 4a: exportar a Word
# ===============================================================
def guardar_word(resumen, nombre):
    from docx import Document

    doc = Document()
    doc.add_heading(f"Resumen de {nombre}", level=1)
    for linea in resumen.split("\n"):
        doc.add_paragraph(linea)

    os.makedirs(CARPETA_RESULTADOS, exist_ok=True)
    ruta = os.path.join(CARPETA_RESULTADOS, f"{nombre}_resumen.docx")
    doc.save(ruta)
    print(f"Word guardado en {ruta}")
    return ruta


# ===============================================================
# PARTE 4b: exportar a Google Docs
# ===============================================================
def servicio_docs():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_DOCS):
        creds = Credentials.from_authorized_user_file(TOKEN_DOCS, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENCIALES):
                raise FileNotFoundError(
                    "Falta credentials.json. Descargalo de Google Cloud Console "
                    "(OAuth 'App de escritorio') y ponlo junto a este script."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENCIALES, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_DOCS, "w") as f:
            f.write(creds.to_json())

    return build("docs", "v1", credentials=creds)


def guardar_google_docs(resumen, titulo):
    docs = servicio_docs()
    doc = docs.documents().create(body={"title": f"Resumen {titulo}"}).execute()
    doc_id = doc["documentId"]

    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": resumen}}]},
    ).execute()

    url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"Google Doc creado: {url}")

    # Guardar el enlace en un archivo, por si nadie mira la pantalla
    os.makedirs(CARPETA_RESULTADOS, exist_ok=True)
    with open(os.path.join(CARPETA_RESULTADOS, "enlaces_google_docs.txt"),
              "a", encoding="utf-8") as f:
        f.write(f"{titulo}: {url}\n")
    return url


# ===============================================================
# Orquestacion
# ===============================================================
def procesar(ruta_audio, exportar_google=True):
    """Toma un .wav y hace: transcribir -> resumir -> Word (-> Google Docs)."""
    nombre = os.path.splitext(os.path.basename(ruta_audio))[0]

    texto = transcribir(ruta_audio)

    try:
        resumen = resumir(texto)
    except Exception as e:
        print(f"No se pudo resumir: {e}")
        print("De todos modos tienes la transcripcion (.txt) guardada.")
        return

    guardar_word(resumen, nombre)

    if exportar_google:
        try:
            guardar_google_docs(resumen, nombre)
        except Exception as e:
            print(f"No se pudo crear el Google Doc: {e}")
            print("El resumen en Word si se guardo.")

    print("Proceso completo.")


# ===============================================================
# Automatizacion: Pi graba sola / Computador procesa solo
# ===============================================================
def modo_pi(carpeta=CARPETA_CLASES):
    """PARA LA PI: graba una clase tras otra en la carpeta sincronizada."""
    os.makedirs(carpeta, exist_ok=True)

    # Le dice a Syncthing que ignore los archivos temporales .part
    ruta_ignore = os.path.join(carpeta, ".stignore")
    if not os.path.exists(ruta_ignore):
        with open(ruta_ignore, "w") as f:
            f.write("*.part\n")

    print(f"Modo Pi activo. Los audios se guardan en {carpeta}")
    while True:
        ruta = os.path.join(carpeta, f"{nombre_base_nuevo()}.wav")
        if grabar_con_boton(ruta) is None:
            break  # Ctrl+C antes de empezar: salir


def _archivo_estable(ruta, espera=20):
    """True si el archivo ya no esta creciendo."""
    try:
        tam1 = os.path.getsize(ruta)
    except OSError:
        return False
    time.sleep(espera)
    try:
        return tam1 == os.path.getsize(ruta)
    except OSError:
        return False


def vigilar(carpeta=CARPETA_CLASES):
    """PARA EL COMPUTADOR: procesa solo cada .wav nuevo que llegue."""
    os.makedirs(carpeta, exist_ok=True)
    print(f"Vigilando {carpeta} ... (deja esta ventana abierta)")
    try:
        while True:
            for f in sorted(os.listdir(carpeta)):
                if f.endswith(".wav"):
                    ruta = os.path.join(carpeta, f)
                    ya_hecho = os.path.splitext(ruta)[0] + ".txt"
                    if not os.path.exists(ya_hecho) and _archivo_estable(ruta):
                        print(f"Audio nuevo detectado: {f}")
                        try:
                            procesar(ruta)
                        except Exception as e:
                            print(f"Error procesando {f}: {e}")
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nVigilancia detenida.")


# ===============================================================
# Programa principal
# ===============================================================
def _ayuda():
    print(__doc__)
    print("Comandos:")
    print("  pi        -> (en la Pi) graba clase tras clase con el boton")
    print("  vigilar   -> (en el computador) procesa solo cada audio nuevo")
    print("  grabar    -> graba una vez con el boton")
    print("  procesar <archivo.wav> -> transcribe, resume y exporta")
    print("  todo      -> graba y luego procesa")
    print("  modelos   -> lista los modelos de Gemini disponibles")


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "grabar"

    if comando in ("-h", "--help", "ayuda"):
        _ayuda()
    elif comando == "pi":
        modo_pi()
    elif comando == "vigilar":
        vigilar()
    elif comando == "grabar":
        grabar_con_boton()
    elif comando == "procesar":
        if len(sys.argv) < 3:
            print("Uso: python grabador_clases.py procesar <archivo.wav>")
            sys.exit(1)
        procesar(sys.argv[2])
    elif comando == "todo":
        audio = grabar_con_boton()
        if audio:
            procesar(audio)
    elif comando == "modelos":
        listar_modelos()
    else:
        print(f"Comando no reconocido: {comando}\n")
        _ayuda()
