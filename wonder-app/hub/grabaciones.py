"""
Wonder Hub - Grabaciones: audio -> transcribe (Whisper) -> resume (Gemini) -> Word / Google Docs

Basado en "GCLASES FINAL FINAL FINAL.py" (parte del computador). Lo que cambia:
  - En vez de dejar una ventana "vigilar" abierta, el hub vigila la carpeta en
    segundo plano y la app muestra el estado de cada grabacion.
  - Los audios llegan a la carpeta de clases por cualquiera de estas vias:
        a) Syncthing (como antes)      b) "Subir audio" en la app
        c) el llavero, por POST /pico/audio (cuando el Pico grabe)
  - El Google Doc usa el mismo login de Google de la app (ya no hay token_docs.json).
  - El modelo de Whisper se carga una sola vez.

Clave de Gemini (NO la escribas en el codigo):
      export GEMINI_API_KEY='tu_clave'      (Linux / Mac)
      setx GEMINI_API_KEY "tu_clave"        (Windows, permanente; abre otra terminal)
"""

import importlib.util
import json
import os
import queue
import re
import threading
import time
import wave
from datetime import datetime

import calendario

# ---------------------------------------------------------------
# Configuracion general
# ---------------------------------------------------------------
CARPETA_SCRIPT = os.path.dirname(os.path.abspath(__file__))
CARPETA_DATOS = os.path.join(CARPETA_SCRIPT, "datos")
CARPETA_ESTADO = os.path.join(CARPETA_DATOS, "grabaciones")     # un .json por grabacion
CARPETA_RESULTADOS = os.path.join(CARPETA_DATOS, "resultados")  # los Word

# Carpeta donde caen los audios (la misma que sincroniza Syncthing).
CARPETA_CLASES = os.path.expanduser(os.environ.get("WONDER_CLASES", "~/clases"))

MODELO_WHISPER = os.environ.get("WONDER_WHISPER", "small")
# Quien transcribe: "auto" = Whisper si esta instalado, si no Gemini.
#                   "gemini" = siempre Gemini (no hay que instalar nada pesado).
#                   "whisper" = siempre Whisper (todo queda en el computador).
TRANSCRIPCION = os.environ.get("WONDER_TRANSCRIPCION", "auto").lower()
MODELO_GEMINI = os.environ.get("WONDER_GEMINI_MODELO", "gemini-flash-latest")
# Si ese falla, el hub le pregunta a Google que modelos hay y usa el "Flash" mas nuevo.
# (Google retira modelos cada pocos meses; asi no hay que cambiar el codigo.)
_modelos = None


def modelos_gemini(cliente):
    """Lista de modelos a probar, en orden: el configurado y los Flash mas nuevos disponibles."""
    global _modelos
    if _modelos is not None:
        return _modelos
    lista = [MODELO_GEMINI]
    try:
        estables, previas = [], []
        for m in cliente.models.list():
            nombre = (getattr(m, "name", "") or "").split("/")[-1]
            acciones = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None) or []
            if "generateContent" not in acciones or "flash" not in nombre:
                continue
            if any(x in nombre for x in ("lite", "image", "tts", "live", "audio", "embedding", "omni", "transcribe", "robotics")):
                continue
            (previas if ("preview" in nombre or "exp" in nombre) else estables).append(nombre)

        def version(n):
            numeros = re.findall(r"\d+(?:\.\d+)?", n)
            return float(numeros[0]) if numeros else 0.0

        estables.sort(key=version, reverse=True)
        previas.sort(key=version, reverse=True)
        lista += estables[:3] + previas[:1]
        print("Modelos de Gemini disponibles:", ", ".join(estables[:3] + previas[:1]) or "ninguno")
    except Exception as e:
        print(f"No pude listar los modelos de Gemini: {e}")
    _modelos = [m for i, m in enumerate(lista) if m and m not in lista[:i]]
    return _modelos

EXTENSIONES = (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac")
REVISAR_CADA_SEG = 15
ESPERA_ESTABLE_SEG = 5

_cola = queue.Queue()
_en_cola = set()
_candado = threading.Lock()
_modelo_whisper = None
_iniciado = False


def nombre_base_nuevo():
    """Nombre con fecha/hora/segundos, p.ej. clase_2026-11-10_10-00-05."""
    return datetime.now().strftime("clase_%Y-%m-%d_%H-%M-%S")


def nombre_seguro(nombre):
    """Deja solo letras, numeros, guiones y punto (evita rutas raras)."""
    nombre = os.path.basename(nombre.replace("\\", "/"))
    base, ext = os.path.splitext(nombre)
    base = re.sub(r"[^A-Za-z0-9_\-]+", "_", calendario.solo_ascii(base)).strip("_")[:80]
    ext = ext.lower()
    if ext not in EXTENSIONES:
        raise ValueError("Formato no admitido. Usa: " + ", ".join(EXTENSIONES))
    return (base or nombre_base_nuevo()) + ext


def _instalado(modulo):
    try:
        return importlib.util.find_spec(modulo) is not None
    except (ImportError, ValueError):
        return False


def herramientas():
    """Que hay instalado/configurado (la app lo muestra para saber que falta)."""
    return {
        "whisper": _instalado("whisper"),
        "transcribe_con": quien_transcribe(),
        "gemini": _instalado("google.genai"),
        "gemini_clave": bool(os.environ.get("GEMINI_API_KEY")),
        "word": _instalado("docx"),
        "carpeta": CARPETA_CLASES,
    }


# ---------------------------------------------------------------
# Estado de cada grabacion (un .json por audio)
# ---------------------------------------------------------------
def _ruta_estado(ident):
    return os.path.join(CARPETA_ESTADO, ident + ".json")


def _id_valido(ident):
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]{1,90}", ident or ""))


def leer(ident):
    if not _id_valido(ident):
        return None
    try:
        with open(_ruta_estado(ident), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _guardar(reg):
    os.makedirs(CARPETA_ESTADO, exist_ok=True)
    temporal = _ruta_estado(reg["id"]) + ".tmp"
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
    os.replace(temporal, _ruta_estado(reg["id"]))


def _actualizar(reg, **cambios):
    reg.update(cambios)
    _guardar(reg)


def listar():
    """Todas las grabaciones, la mas nueva primero (sin la transcripcion completa)."""
    lista = []
    if os.path.isdir(CARPETA_ESTADO):
        for f in os.listdir(CARPETA_ESTADO):
            if f.endswith(".json"):
                reg = leer(f[:-5])
                if reg:
                    corto = dict(reg)
                    corto.pop("transcripcion", None)
                    corto["vista"] = (reg.get("resumen") or "")[:160]
                    corto.pop("resumen", None)
                    lista.append(corto)
    lista.sort(key=lambda r: r.get("creado", ""), reverse=True)
    return lista


def ruta_audio(reg):
    return os.path.join(CARPETA_CLASES, reg["archivo"])


def _duracion(ruta):
    """Segundos de audio (solo se puede saber facil en .wav)."""
    if not ruta.lower().endswith(".wav"):
        return None
    try:
        with wave.open(ruta, "rb") as w:
            return round(w.getnframes() / float(w.getframerate()))
    except Exception:
        return None


# ===============================================================
# PARTE 2: transcribir (Whisper en el computador, o Gemini en la nube)
# ===============================================================
def quien_transcribe():
    if TRANSCRIPCION == "gemini":
        return "gemini"
    if TRANSCRIPCION == "whisper" or _instalado("whisper"):
        return "whisper"
    return "gemini" if _instalado("google.genai") else None


def transcribir(ruta_audio_):
    """Transcribe y guarda un .txt al lado del audio."""
    if quien_transcribe() == "gemini":
        texto = transcribir_con_gemini(ruta_audio_)
    else:
        texto = transcribir_con_whisper(ruta_audio_)
    ruta_txt = os.path.splitext(ruta_audio_)[0] + ".txt"
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"Transcripcion guardada en {ruta_txt}")
    return texto


def transcribir_con_gemini(ruta_audio_):
    """Sube el audio a Gemini y pide la transcripcion literal. No necesita Whisper ni ffmpeg."""
    try:
        from google import genai
    except ImportError:
        raise RuntimeError("Falta instalar Gemini:  pip install google-genai")
    cliente = genai.Client(api_key=_leer_api_key())
    print("Subiendo el audio a Gemini para transcribir...")
    archivo = cliente.files.upload(file=ruta_audio_, config={"mime_type": "audio/wav"})
    try:
        for _ in range(90):                                   # espera a que Google lo procese
            estado = getattr(getattr(archivo, "state", None), "name", "ACTIVE")
            if estado != "PROCESSING":
                break
            time.sleep(2)
            archivo = cliente.files.get(name=archivo.name)
        if getattr(getattr(archivo, "state", None), "name", "ACTIVE") == "FAILED":
            raise RuntimeError("Gemini no pudo leer el audio.")
        prompt = ("Transcribe este audio de una clase universitaria en espanol, palabra por palabra. "
                  "Devuelve SOLO el texto hablado, en parrafos, sin titulos, sin Markdown y sin comentarios. "
                  "Si no hay voz, responde exactamente: (sin voz)")
        ultimo = None
        for modelo in modelos_gemini(cliente):
            try:
                print(f"Transcribiendo con Gemini ({modelo})...")
                r = cliente.models.generate_content(model=modelo, contents=[archivo, prompt])
                texto = (r.text or "").strip()
                if texto == "(sin voz)":
                    texto = ""
                return limpiar_markdown(texto) if texto else ""
            except Exception as e:
                ultimo = e
                print(f"  Fallo el modelo {modelo}: {e}")
        raise RuntimeError(f"Gemini no pudo transcribir ({ultimo}).")
    finally:
        try:
            cliente.files.delete(name=archivo.name)               # no dejar el audio guardado en Google
        except Exception:
            pass


def transcribir_con_whisper(ruta_audio_, modelo_nombre=MODELO_WHISPER):
    """Transcribe en el computador con Whisper (el audio no sale del computador)."""
    global _modelo_whisper
    try:
        import whisper
    except ImportError:
        raise RuntimeError("Falta instalar Whisper:  pip install openai-whisper  (y ffmpeg en el sistema)")

    if not os.path.exists(ruta_audio_):
        raise FileNotFoundError(f"No encuentro el archivo de audio: {ruta_audio_}")

    if _modelo_whisper is None:
        print(f"Cargando modelo Whisper '{modelo_nombre}' (puede tardar la primera vez)...")
        _modelo_whisper = whisper.load_model(modelo_nombre)

    print("Transcribiendo... (esto tarda segun la duracion del audio)")
    resultado = _modelo_whisper.transcribe(ruta_audio_, language="es", fp16=False)
    return resultado["text"].strip()


# ===============================================================
# PARTE 3: resumir con Gemini
# ===============================================================
def _leer_api_key():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta la variable de entorno GEMINI_API_KEY. "
            "Consiguela en https://aistudio.google.com/api-keys"
        )
    return api_key


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
    try:
        from google import genai
    except ImportError:
        raise RuntimeError("Falta instalar Gemini:  pip install google-genai")

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

    ultimo_error = None
    for modelo in modelos_gemini(cliente):
        try:
            print(f"Resumiendo con Gemini ({modelo})...")
            respuesta = cliente.models.generate_content(model=modelo, contents=prompt)
            texto_resumen = (respuesta.text or "").strip()
            if texto_resumen:
                return limpiar_markdown(texto_resumen)
            print(f"  El modelo {modelo} no devolvio texto, probando otro...")
        except Exception as e:
            ultimo_error = e
            print(f"  Fallo el modelo {modelo}: {e}")

    raise RuntimeError(f"Gemini no pudo generar el resumen ({ultimo_error or 'respuesta vacia'}).")


# ===============================================================
# PARTE 4a: exportar a Word
# ===============================================================
def guardar_word(resumen, nombre):
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError("Falta instalar python-docx:  pip install python-docx")

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
# PARTE 4b: exportar a Google Docs (con el login de la app)
# ===============================================================
def guardar_google_docs(resumen, titulo):
    from googleapiclient.discovery import build

    creds = calendario.credenciales()
    if calendario.SCOPE_DOCS not in (creds.scopes or []):
        raise RuntimeError("El login de Google no incluyo el permiso de Google Docs. Cierra sesion y vuelve a entrar marcando todos los permisos.")
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    doc = docs.documents().create(body={"title": f"Resumen {titulo}"}).execute()
    doc_id = doc["documentId"]

    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": resumen}}]},
    ).execute()

    url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(f"Google Doc creado: {url}")
    return url


def crear_google_doc(ident):
    """Boton 'Crear Google Doc' de la app."""
    reg = leer(ident)
    if not reg or not reg.get("resumen"):
        raise ValueError("Esa grabacion aun no tiene resumen.")
    url = guardar_google_docs(reg["resumen"], reg["nombre"])
    _actualizar(reg, google_doc=url)
    return url


# ===============================================================
# Orquestacion: transcribir -> resumir -> Word (-> Google Docs)
# ===============================================================
def procesar(ident):
    reg = leer(ident)
    if not reg:
        return
    ruta = ruta_audio(reg)
    try:
        ruta_txt = os.path.splitext(ruta)[0] + ".txt"
        if reg.get("transcripcion"):
            texto = reg["transcripcion"]
        elif os.path.exists(ruta_txt):                # ya estaba transcrito (p.ej. por el script anterior)
            with open(ruta_txt, encoding="utf-8") as f:
                texto = f.read().strip()
        else:
            _actualizar(reg, estado="transcribiendo", error=None)
            texto = transcribir(ruta)
        if not texto:
            raise RuntimeError("La transcripcion salio vacia (audio sin voz?).")
        _actualizar(reg, transcripcion=texto, estado="resumiendo", error=None)

        resumen = resumir(texto)
        _actualizar(reg, resumen=resumen)

        avisos = []
        try:
            _actualizar(reg, word=os.path.basename(guardar_word(resumen, reg["nombre"])))
        except Exception as e:
            avisos.append(str(e))
        if calendario.estado().get("docs"):
            try:
                _actualizar(reg, google_doc=guardar_google_docs(resumen, reg["nombre"]))
            except Exception as e:
                avisos.append(f"No se pudo crear el Google Doc: {e}")
        _actualizar(reg, estado="listo", error=None, aviso=" · ".join(avisos) or None,
                    terminado=datetime.now().isoformat(timespec="seconds"))
        print(f"Proceso completo: {reg['nombre']}")
    except Exception as e:
        print(f"Error procesando {reg['nombre']}: {e}")
        _actualizar(reg, estado="error", error=str(e))


def _encolar(ident):
    with _candado:
        if ident in _en_cola:
            return
        _en_cola.add(ident)
    _cola.put(ident)


def reprocesar(ident):
    reg = leer(ident)
    if not reg:
        raise ValueError("No existe esa grabacion.")
    if not os.path.exists(ruta_audio(reg)) and not reg.get("transcripcion"):
        raise ValueError("Ya no esta el archivo de audio en la carpeta de clases.")
    _actualizar(reg, estado="pendiente", error=None)
    _encolar(ident)


def registrar(archivo):
    """Crea el registro de un audio que ya esta completo en la carpeta y lo encola."""
    ident = os.path.splitext(archivo)[0]
    if not _id_valido(ident):
        return None
    reg = leer(ident)
    if reg is None:
        ruta = os.path.join(CARPETA_CLASES, archivo)
        reg = {
            "id": ident,
            "nombre": ident,
            "archivo": archivo,
            "creado": datetime.fromtimestamp(os.path.getmtime(ruta)).isoformat(timespec="seconds"),
            "duracion_seg": _duracion(ruta),
            "tamano": os.path.getsize(ruta),
            "estado": "pendiente",
            "error": None,
        }
        _guardar(reg)
        _encolar(ident)
    return reg


def guardar_subida(nombre, flujo, limite=600 * 1024 * 1024):
    """Guarda un audio subido desde la app. Escribe en .part y renombra al final
    (igual que la Pi), para que nadie procese un archivo a medias."""
    archivo = nombre_seguro(nombre)
    os.makedirs(CARPETA_CLASES, exist_ok=True)
    base, ext = os.path.splitext(archivo)
    if os.path.exists(os.path.join(CARPETA_CLASES, archivo)) or leer(base):
        archivo = f"{base}_{datetime.now().strftime('%H%M%S')}{ext}"
    destino = os.path.join(CARPETA_CLASES, archivo)
    total = 0
    with open(destino + ".part", "wb") as f:
        while True:
            trozo = flujo.read(256 * 1024)
            if not trozo:
                break
            total += len(trozo)
            if total > limite:
                f.close()
                os.remove(destino + ".part")
                raise ValueError("El audio es demasiado grande (maximo 600 MB).")
            f.write(trozo)
    if total == 0:
        os.remove(destino + ".part")
        raise ValueError("El archivo llego vacio.")
    os.replace(destino + ".part", destino)
    return registrar(archivo)


def recibir_trozo_pico(nombre, desplazamiento, datos, fin):
    """El llavero sube el .wav por partes: POST /pico/audio?nombre=..&pos=..[&fin=1]."""
    archivo = nombre_seguro(nombre)
    os.makedirs(CARPETA_CLASES, exist_ok=True)
    parcial = os.path.join(CARPETA_CLASES, archivo + ".part")
    actual = os.path.getsize(parcial) if os.path.exists(parcial) else 0
    if desplazamiento == 0 and actual:
        os.remove(parcial)
        actual = 0
    if desplazamiento != actual:
        return {"ok": False, "pos": actual}          # el Pico retoma desde 'pos'
    with open(parcial, "ab") as f:
        f.write(datos)
    actual += len(datos)
    if fin:
        os.replace(parcial, os.path.join(CARPETA_CLASES, archivo))
        registrar(archivo)
    return {"ok": True, "pos": actual}


# ===============================================================
# Automatizacion: vigilar la carpeta y procesar en segundo plano
# ===============================================================
def _archivo_estable(ruta, espera=ESPERA_ESTABLE_SEG):
    """True si el archivo ya no esta creciendo."""
    try:
        tam1 = os.path.getsize(ruta)
    except OSError:
        return False
    time.sleep(espera)
    try:
        return tam1 == os.path.getsize(ruta) and tam1 > 0
    except OSError:
        return False


def _vigilar():
    while True:
        try:
            if os.path.isdir(CARPETA_CLASES):
                for f in sorted(os.listdir(CARPETA_CLASES)):
                    if f.lower().endswith(EXTENSIONES):
                        ident = os.path.splitext(f)[0]
                        if _id_valido(ident) and leer(ident) is None:
                            if _archivo_estable(os.path.join(CARPETA_CLASES, f)):
                                print(f"Audio nuevo detectado: {f}")
                                registrar(f)
        except Exception as e:
            print(f"Vigilancia: {e}")
        time.sleep(REVISAR_CADA_SEG)


def _trabajar():
    while True:
        ident = _cola.get()
        try:
            procesar(ident)
        finally:
            with _candado:
                _en_cola.discard(ident)


def iniciar():
    """Arranca los hilos (una sola vez) y retoma lo que quedo a medias."""
    global _iniciado
    if _iniciado:
        return
    _iniciado = True
    os.makedirs(CARPETA_CLASES, exist_ok=True)
    os.makedirs(CARPETA_ESTADO, exist_ok=True)
    for reg in listar():
        if reg.get("estado") in ("pendiente", "transcribiendo", "resumiendo"):
            _encolar(reg["id"])
    threading.Thread(target=_trabajar, daemon=True, name="wonder-procesar").start()
    threading.Thread(target=_vigilar, daemon=True, name="wonder-vigilar").start()
    print(f"Grabaciones: vigilando {CARPETA_CLASES}")
