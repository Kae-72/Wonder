# Cambios de Wonder

## Cómo aplicar una versión nueva

1. **GitHub:** descomprime el zip y copia su contenido **encima** de la carpeta del repositorio
   (la de GitHub Desktop). Acepta **reemplazar** los archivos. Después, en GitHub Desktop:
   escribe un resumen (p. ej. "v6") → **Commit to main** → **Push origin**.
2. **Llavero:** en Thonny, pulsa ■ Stop y sube los archivos de `llavero/` que diga la lista
   de la versión (o todos los `.py` si no estás seguro). La carpeta `pruebas/` no se sube:
   esos archivos se abren desde el computador y se corren con ▶.
3. **Hub:** si el hub corre desde otra carpeta, copia ahí también `wonder-app/` encima
   (reemplazando). Nunca borres `wonder-app/hub/datos/` ni `credentials.json`.

**Lo que nunca sube a GitHub** (lo bloquea `.gitignore`): `credentials.json`, `hub/datos/`
(sesión de Google, clave del llavero, logros), los archivos que crea el llavero (`config.json`
con las claves del WiFi, `pines.json`, etc.) y las grabaciones `.wav`.

---

## v7.2 — 16 de noviembre de 2026 (noche)

Subir al Pico: `sonidos.py` y `main.py`.

- **El sonido ya no se queda mudo:** si la cadena de audio se corta (el Pico estaba ocupado con
  el WiFi o la memoria), se vuelve a enganchar sola.
- `VOLUMEN = 35` por defecto para cuidar el parlante de 8 Ω 0,5 W (no pasar de ~45).

## v7.1 — 16 de noviembre de 2026 (noche)

Subir al Pico: `main.py`, `bateria.py`, `sonidos.py`, `grabadora.py`. **Borrar `pines.json` del Pico.**

- **Arregla los timeouts del WiFi:** desde la v6.1 el llavero tocaba el pin GP29 para medir la
  batería, pero ese pin lo usa el chip WiFi y lo dejaba colgado. Ya no se toca nunca.
- **Batería:** la barra muestra el rayo con USB y "?" sin USB. Para ver el porcentaje hay que
  poner un divisor de 2 resistencias de 100k hacia GP27 (instrucciones en `bateria.py`).
- **Menos memoria:** los fondos se leen directo de la memoria del Pico (sin copia en RAM),
  los sonidos usan 11 kHz y el micrófono un búfer menor.
- **Botones por defecto corregidos:** izquierdo GP15, centro GP14, derecho GP16.

## v7 — 16 de noviembre de 2026

Subir al Pico: **`main.py`** y los archivos nuevos: `icono_wonder.spr`, `icono_wonder_mini.spr`,
`nombre_wonder.spr`, `fondo_inventario.raw`, `wonder_base.spr`, `wonder_feliz.spr`,
`wonder_triste.spr`, `wonder_enojado.spr`, `acc_gafas.spr`, `acc_bufanda.spr`,
`fondo_grabadora_dia.raw`, `fondo_grabadora_tarde.raw`, `fondo_grabadora_noche.raw`
(y todo lo de v6.1 si aún no se subió). Hub: `wonder-app/hub/hub.py`.

- **Nueva opción del menú: Wonder.** Inventario con Wonder según su ánimo (feliz, normal,
  triste, enojado), tres barras (ánimo, energía, estudio) y una frase.
  - Ánimo: ¡Hecho! de hoy confirmados por el hub, racha de días, minutos de pomodoro
    terminados, visitar a Wonder una vez al día; baja con tareas o clases de las últimas 24 h
    que terminaron sin marcar (2 o más = enojado).
  - Energía: según la hora (de noche tiene sueño) y la batería.
  - Estudio: minutos de pomodoro terminados hoy (meta: 100).
  - Accesorios: gafas y bufanda desde el inicio; 3 espacios "???" que se desbloquean con
    10, 25 y 50 ¡Hecho! (cuando lleguen sus sprites). Solo cuentan los ¡Hecho! confirmados
    por el hub, así no se puede hacer trampa desde el llavero.
- **Grabadora:** el fondo cambia según la hora (cielo + capa blanca + Wonder escuchando).
- Herramienta nueva: `herramientas/preparar_inventario.py` (y `herramientas/accesorios/`).

## v6.1 — 15 de noviembre de 2026 (noche)

Subir al Pico: `main.py`, `sonidos.py`, `bateria.py`, `red.py`, `grabadora.py` y los 6 fondos
nuevos `fondo_pomodoro_dia/tarde/noche.raw` y `fondo_descanso_dia/tarde/noche.raw`.
Hub: `wonder-app/hub/grabaciones.py`.

- **Fondos según la hora** (día 6–17 h, tarde 17–19 h, noche 19–6 h): en el pomodoro el cielo
  se ve por la ventana; en el descanso, Wonder de día, al atardecer o de noche.
- **Al dormir:** muestra a Wonder descansando según la hora y toca una melodía corta
  (3 por cada momento del día, al azar).
- **Batería:** se lee apagando el WiFi un instante (el pin lo comparte el chip WiFi), cada 5 min.
  Antes leía mal con WiFi y mostraba la batería vacía. En el Shell sale `VSYS = x.xx V`.
- **Grabadora:** el micrófono se crea una sola vez (arregla "memory allocation failed" en la
  segunda grabación) y dos grabaciones nunca se pisan.
- **Hub:** elige solo el modelo de Gemini disponible (Google retiró `gemini-2.5-flash`).
- Si los botones salen cruzados: borrar `pines.json` del Pico (usa izq 14, O 15, der 16).

## v6 — 15 de noviembre de 2026

Archivos del llavero que cambiaron: **todos los `.py`** de `llavero/`.

- **Sonidos con variedad:** los sonidos de navegación cambian un poco cada vez (otra
  variante, otro timbre, notas de adorno), siempre en la misma escala. Jingle de encendido
  distinto cada vez y arpegio nuevo al entrar a la sesión (`entrar`). Los avisos y errores
  no cambian, para reconocerlos al instante.
- **Memoria:** pantalla, fondos y sonido reservan su espacio al arrancar (arregla
  "memory allocation failed").
- **¡Hecho!:** en Calendario, IZQ/DER eligen un evento y O lo marca como cumplido (tarea o
  clase). El hub lo valida contra Google Calendar (`hub/logros.py`): evento real, creado antes
  de empezar, desde que empieza hasta 12 h después de terminar, una vez, máximo 8 por día.
  Mantener DER actualiza el calendario.
- **Dormir:** en batería, 3 min sin tocar nada y sin pomodoro ni grabación → apaga pantalla,
  WiFi y parlante. Despierta con un botón o antes de una clase.
- **Permiso para grabar:** pregunta al entrar a la grabadora y antes de cada grabación.
- **Grabadora:** micrófono en estéreo con `MIC_CANAL` (0 = L/R a GND, 1 = L/R a 3.3V);
  texto de la pantalla corregido; muestra el error real de la microSD;
  prueba nueva `llavero/pruebas/prueba_grabar.py`.
- **Hub:** transcribe con Gemini si Whisper no está instalado (`WONDER_TRANSCRIPCION`).
- **App:** paneles ¡Hecho! y Pomodoro; batería, red y redes guardadas del llavero.
- **Botones por defecto:** izquierdo GP14, centro GP15, derecho GP16.
- **Seguridad:** se quitó la clave del WiFi de `PRELIMINAR/calendario pico.py`.

## v4 — 14 de noviembre de 2026

- Varias redes WiFi guardadas y conexión automática; el hub se anuncia por UDP 37020.
- Barra con hora, WiFi y batería; pomodoro en segundo plano; grabadora a microSD.
- Sonidos estilo Game Boy por el amplificador MAX98357A.
