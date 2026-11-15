# Wonder · app web + hub + llavero

Tres carpetas, tres piezas:

| Carpeta | Qué es | Dónde corre |
|---|---|---|
| `app/` | La app web (HTML + CSS + JS, sin compilar) | En el navegador |
| `hub/` | **Wonder Hub**: servidor local en Python | En el computador |
| `pico/` | `main.py` + sprites del llavero | En el Pico 2 W |

La app solo hace tres cosas: los inicios de sesión, la personalización de Wonder y
pasar información al llavero. Todo lo pesado (Google, Whisper, Gemini) lo hace el hub.

```
 Navegador (app) ──► Wonder Hub (computador) ──► Google Calendar / Docs / Gemini
                          ▲
 Llavero (Pico) ──────────┘   pide /eventos y /pico/* con su clave, por WiFi
```

## 1. Arrancar

```bash
cd hub
pip install -r requirements-minimo.txt     # app + Google Calendar
pip install -r requirements.txt            # además grabaciones (Whisper, Gemini, Word)
python hub.py                              # o doble clic en iniciar.bat
```

Abre **http://localhost:8000** en ese computador. Desde el celular (mismo WiFi) se entra
con la dirección y el PIN que muestra la terminal.

Para editar la app: cambia un archivo de `app/`, guarda y recarga el navegador.

## 2. Login de Google

1. Copia su `credentials.json` (OAuth "App de escritorio") dentro de `hub/`.
2. En Google Cloud, el proyecto debe tener activas **Google Calendar API** y **Google Docs API**,
   y la cuenta con la que van a entrar debe estar en "Usuarios de prueba".
3. En la app: Inicio → **Entrar con Google** → aceptar los dos permisos.

El login se hace una sola vez y solo desde el computador del hub (Google exige `localhost`).
El token queda en `hub/datos/token.json`. Los `token.json` / `token_docs.json` anteriores ya no se usan.

Permisos pedidos: `calendar.events.readonly` (solo leer eventos) y `documents` (crear el resumen).

## 3. Llavero: cómo le llega el WiFi (v0.4)

1. Copia al Pico todo lo de `llavero/` (con Thonny), menos la carpeta `pruebas/`.
2. Un llavero sin configurar arranca en **CONFIGURAR** y crea la red `Wonder-Setup`
   (clave `wonder1234`). Uno ya configurado entra manteniendo **O** en la pantalla de inicio.
3. En la app: Inicio → **Agregar red WiFi**. Escribe el nombre y la clave del WiFi.
4. Conecta el computador o el celular a `Wonder-Setup` y pulsa **Enviar al llavero**.
   Puedes mandar varias redes seguidas. Al terminar, pulsa **O** en el llavero.

- El llavero **recuerda varias redes** (máx. 8) y se conecta solo a la que tenga cerca,
  sin detener la pantalla. Agregar una red no borra las otras. "Ver redes guardadas" y
  "Olvidar" funcionan con el llavero en CONFIGURAR.
- Cada red guarda su propia dirección del hub. Si el computador cambia de IP, el hub
  avisa por la red local (UDP 37020) y el llavero lo encuentra solo.
- WiFi del celular: solo 2,4 GHz. En iPhone, "Maximizar compatibilidad".
- Plan B por cable: el diálogo descarga `config.json` (ojo: reemplaza la lista de redes).

### Qué hace el llavero ahora

- Barra arriba a la derecha (menos en el inicio): hora, WiFi, batería y el pomodoro si corre.
- La hora viene del hub (o de internet si no hay hub). La batería se lee de VSYS (`bateria.py`).
- Cada 5 min, si hay WiFi: hora, calendario, Mi Wonder y ajustes del pomodoro.
  Le cuenta al hub su batería y sus redes (se ven en Inicio de la app).
- Aviso con sonido 10 min antes de cada evento del día.
- Pomodoro (`main.py`): tiempos desde la app; sigue corriendo si sales al menú.
- **¡Hecho!**: en Calendario, IZQ/DER eligen un evento y O lo marca como cumplido (tarea o clase).
  El hub lo valida contra Google (`hub/logros.py`): evento real, creado antes de empezar, desde
  que empieza hasta 12 h después de terminar, una vez, máximo 8 por día. Sin WiFi queda pendiente.
- **Dormir**: en batería, 3 min sin tocar nada y sin pomodoro ni grabación, apaga pantalla, WiFi y
  parlante. Despierta con cualquier botón o 10 min antes de un evento (`APAGAR_MIN` en `main.py`).
- **Permiso**: antes de abrir la grabadora pregunta si se pidió permiso a las personas grabadas.
- Grabadora (`grabadora.py`): micrófono INMP441 → WAV 16 kHz en la microSD → sube al hub
  por partes con `POST /pico/audio` (se puede pausar y retomar).

## 4. Grabaciones

**Transcripción:** si Whisper no está instalado, el hub transcribe con **Gemini** (sube el audio,
lo transcribe y lo borra de Google). Solo hace falta `pip install google-genai` y la variable
`GEMINI_API_KEY`. Para forzar uno: variable `WONDER_TRANSCRIPCION` = `gemini` o `whisper`.


El hub vigila la carpeta de clases (`~/clases`, o la variable `WONDER_CLASES`). Cada audio nuevo pasa por
Whisper → Gemini → Word → Google Doc, igual que en `GCLASES FINAL`. Un audio llega por:

- **Subir audio** en la app,
- Syncthing (como antes),
- el llavero: `POST /pico/audio?nombre=clase_x.wav&pos=0` … `&fin=1` (por partes, con reanudación).

Requisitos: `ffmpeg` instalado y la variable `GEMINI_API_KEY`. La app avisa qué falta.

## 5. Wonder (emociones y accesorios)

Sección Wonder: 4 emociones y 2 accesorios con los PNG originales. **Guardar en el llavero**
hace que el hub arme la pantalla de 160×128 (`hub/pantallas.py`) y el llavero la descargue.

Para agregar un accesorio: PNG en el mismo lienzo que los demás → `app/img/wonder_<nombre>.png`
y `hub/recursos/wonder_<nombre>.png`, y añadirlo a `ACCESORIOS` en `app/js/app.js` y `hub/pantallas.py`.

## 6. Lo que habla el llavero con el hub

Todas con la cabecera `X-Wonder-Key: <clave del llavero>`.

| Ruta | Devuelve |
|---|---|
| `GET /eventos` | `{"eventos":[{"dia","fecha","hora","titulo"}],"hora":"HH:MM"}` |
| `GET /pico/estado?v=N` | versión de Mi Wonder y hora |
| `GET /pico/wonder.raw` | 40 960 bytes RGB565 (160×128) |
| `POST /pico/audio` | subida de grabaciones por partes |

## 7. Seguridad (corto)

- No subir a GitHub: `hub/credentials.json` ni `hub/datos/` (ya están en `.gitignore`).
- La clave del WiFi va directo del navegador al llavero; el hub no la ve. En el Pico queda en `config.json` sin cifrar.
- La app desde otro dispositivo pide PIN; el llavero usa su propia clave.
- Todo viaja por HTTP dentro del WiFi: úsenlo en redes de confianza (casa o el hotspot del celular).
