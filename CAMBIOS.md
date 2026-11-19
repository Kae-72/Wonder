# Cambios de Wonder

## Cómo aplicar una versión nueva

1. **GitHub:** descomprime el zip y copia su contenido **encima** de la carpeta del repositorio
   (la de GitHub Desktop). Acepta **reemplazar** los archivos. Si cambió algo de `llavero/`,
   corre `herramientas/hacer_manifiesto.py` (F5 en Spyder). Después, en GitHub Desktop:
   escribe un resumen (p. ej. "v8") → **Commit to main** → **Push origin**.
   Desde la v8, los llaveros se pueden actualizar solos: Configuración → Actualizar.
2. **Llavero:** en Thonny, pulsa ■ Stop y sube los archivos de `llavero/` que diga la lista
   de la versión (o todos los `.py` si no estás seguro). La carpeta `pruebas/` no se sube:
   esos archivos se abren desde el computador y se corren con ▶.
3. **Hub:** si el hub corre desde otra carpeta, copia ahí también `wonder-app/` encima
   (reemplazando). Nunca borres `wonder-app/hub/datos/` ni `credentials.json`.

**Lo que nunca sube a GitHub** (lo bloquea `.gitignore`): `credentials.json`, `hub/datos/`
(sesión de Google, clave del llavero, logros), los archivos que crea el llavero (`config.json`
con las claves del WiFi, `pines.json`, etc.) y las grabaciones `.wav`.

---

## v8 — 18 de noviembre de 2026

> **Ojo:** la v7.3 y la v7.4 nunca se subieron a GitHub. Esta versión las incluye (están más
> abajo), así que con este commit el repo queda al día.

**Subir al Pico (la primera vez, a mano con Thonny): TODO lo que está en `llavero/`**
(menos la carpeta `pruebas/`). Hay unos 30 archivos nuevos: `juegos.py`, `chip8.py`, `ajustes.py`,
`ota.py`, `version.txt`, los 4 juegos `juego_*.ch8` y los `.spr` de comidas, juegos y
Configuración. De aquí en adelante se puede actualizar por internet.

**Los botones NO cambian** (izq GP15, O GP14, der GP16). `pines.json` sigue mandando.

### Llavero
- **Menú Configuración** (ícono del engranaje de Paula): volumen de notificaciones, de efectos
  y de música por separado (cada uno con su prueba de sonido), silenciar todo, redes WiFi,
  **Actualizar** y **Borrar todo**.
- **Actualizar por internet**: el llavero revisa `llavero/manifiesto.json` en GitHub y baja
  solo lo que cambió. Primero lo baja todo y lo revisa; si algo falla, queda como estaba.
  Pide el cargador conectado. Nunca toca botones, redes, Wonder, ¡Hecho! ni ajustes.
- **Borrar todo** (de fábrica): mantener O 3 s. Borra redes, logros, comida, energía, racha,
  juego, Mi Wonder y ajustes, y vuelve a configurar desde cero. **Nunca borra `pines.json`.**
  Si hay hub, el hub guarda una copia de los logros en `hub/datos/copias/`.
- **Protección del parlante**: el amplificador solo se prende mientras suena algo. Un vigilante
  (interrupción de reloj, funciona aunque el programa se trabe) lo apaga si un sonido dura
  demasiado o el audio se atasca, y muestra "Parlante silenciado". Se reactiva al reiniciar
  o en Configuración → Reactivar parlante.
- **Reloj**: se pone solo con el hub o con internet (y se corrige cada pocas horas), se guarda
  en `hora.json` cada 30 min. Si el Pico se reinicia sin internet, **ya no supone que es de día**:
  usa el último momento que conoció. Prueba nueva: `pruebas/prueba_reloj.py`.
- **Racha de estudio** con fueguito en la barra y en el Pomodoro. Cuenta cualquier pomodoro
  terminado (hasta el más corto), solo de lunes a viernes. **Sábado y domingo no cuentan ni la
  rompen** (lo explica la pantalla "La racha", que sale la primera vez que entras a Wonder).
- **Comida con rarezas**: desde 2 días de racha, cada pomodoro da una comida al azar que se
  guarda: Básica **Mailo** +20 % (60 de cada 100), Rara **Arepa** +27 % (30), Nicho
  **Changua** +35 % (10). Se la das a Wonder en su menú (elige la comida → O).
- **Energía**: solo sube comiendo y nunca baja sola. Se quitó la barra de estudio.
- **Juegos** (menú nuevo, su ícono y nombre son los del juego que te tocó): Br8kout,
  Flight Runner, Piper y Sw8 Copter (CHIP-8, dominio público, con crédito a sus autores).
  Hace falta 25 % de energía y jugar no gasta nada. Si pierdes la racha (de 2+ días), el juego
  cambia al azar. Con 100 % puedes pagar 50 % para elegir otro. Salir: mantener IZQ + DER 1 s.
- **Barra de arriba**: racha 🔥 y parlante (con X roja si está silenciado).
- **Después de apagar con IZQ + DER**, al prender vuelve a "Pulsa O". Si se durmió solo,
  vuelve a donde estabas.
- **Encontrar el hub**: si no llega el aviso de la red, al actualizar el calendario el llavero
  prueba solo las direcciones más comunes de la red ("Buscando el hub...").

### Wonder Hub y app
- El hub avisa dónde está en **cada** red del computador (WiFi, cable, hotspot del PC).
- La app saluda "¡Hola! ¿Qué se dice?", muestra la racha, la energía, la comida guardada
  (con su rareza) y el juego actual, con el aviso de que el fin de semana no cuenta.
- La página de Wonder es más bonita: escena grande, racha / energía / ¡Hecho!, accesorios
  bloqueados a la vista y la comida guardada.

### Herramientas
- `herramientas/preparar_v8.py`: hace los sprites de comidas y Configuración (de
  `herramientas/sprites_v8/`) y los logos de los juegos, sacados de la pantalla de cada juego.
  También rehízo `nombre_wonder.spr` con la misma letra de los otros nombres del menú.
- `herramientas/hacer_manifiesto.py`: correrlo antes de cada commit que cambie `llavero/`.
- `.gitattributes`: los archivos de `llavero/` se guardan tal cual (necesario para que las
  huellas del manifiesto coincidan).
- README: corregidos los pines de los botones en el texto (el código ya estaba bien).

---

## v7.4 — 17 de noviembre de 2026 (no se había anotado)

Subir al Pico: `main.py`, `grabadora.py`.

- **microSD "error 5"**: la tarjeta va más despacio (1 MHz), se reinicia sola y se reintenta;
  si falla grabando, se guarda la parte que alcanzó a grabar.
- Si la microSD falla solo en batería: le falta voltaje (necesita ~5 V; un elevador lo arregla).

---

## v7.3 — 17 de noviembre de 2026

Subir al Pico: `main.py`.

- **Apagar con los botones:** mantener IZQ + DER 2,5 s apaga pantalla, WiFi y parlante (el Pico
  queda casi sin consumir). Para prender: mantener O 2 s. No es un apagado total: no hay
  interruptor, así que la batería se sigue gastando muy despacio.
- `VOLUMEN = 80` por defecto en `sonidos.py`.
- Prueba nueva `llavero/pruebas/prueba_red.py`: dice por qué el llavero no llega al hub.

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
