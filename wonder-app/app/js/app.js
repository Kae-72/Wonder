// Wonder App — logins, personalización y puente entre la web y el llavero.
// Sin frameworks ni compilación: edita, guarda y recarga el navegador.

import * as api from "./api.js";

const $ = (sel, raiz = document) => raiz.querySelector(sel);
const vista = $("#vista");
const dialogo = $("#dialogo");

const EMOCIONES = [["base", "Normal"], ["feliz", "Feliz"], ["enojado", "Enojado"], ["preocupado", "Preocupado"]];
const ACCESORIOS = [["gafas", "Gafas"], ["bufanda", "Bufanda"]];        // se dibujan bufanda -> gafas
const ORDEN_CAPAS = ["bufanda", "gafas"];
const BLOQUEADOS = [["nuevo1", 10], ["nuevo2", 25], ["nuevo3", 50]];   // accesorios que aún no existen
// Comida que gana el llavero con la racha (igual que en llavero/main.py)
const COMIDAS = [
  ["mailo", "Mailo", "Básica", 20, 60],
  ["arepa", "Arepa de maduro con boloñesa", "Rara", 27, 30],
  ["changua", "Changua", "Nicho", 35, 10],
];
const JUEGOS = { br8kout: "Br8kout", flightrunner: "Flight Runner", piper: "Piper", sweetcopter: "Sw8 Copter" };
const AP_NOMBRE = "Wonder-Setup", AP_CLAVE = "wonder1234";             // igual que en pico/main.py

const S = {
  vista: "inicio",
  estado: null,
  eventos: null, errorEventos: null, hora: "", pagina: 0,
  grabs: null, detalle: {}, abiertas: new Set(),
  wonder: null,              // lo que se está editando: { emocion, accesorios }
};

// ---------- utilidades ----------
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fFecha = new Intl.DateTimeFormat("es-CO", { weekday: "long", day: "numeric", month: "long" });
const fHora = new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false });
const fCorta = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false });

function hace(seg) {
  if (seg == null) return "nunca";
  if (seg < 60) return "hace unos segundos";
  if (seg < 3600) return `hace ${Math.round(seg / 60)} min`;
  if (seg < 86400) return `hace ${Math.round(seg / 3600)} h`;
  return `hace ${Math.round(seg / 86400)} días`;
}
function duracion(seg) {
  if (!seg) return "";
  const m = Math.round(seg / 60);
  return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`;
}
function nombreBonito(g) {
  const m = /^clase_(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})/.exec(g.nombre || "");
  return m ? "Clase del " + fCorta.format(new Date(+m[1], m[2] - 1, +m[3], +m[4], +m[5])) : (g.nombre || "").replace(/_/g, " ");
}
let relojTostada;
function avisar(texto) {
  const t = $("#tostada");
  t.textContent = texto; t.hidden = false;
  clearTimeout(relojTostada);
  relojTostada = setTimeout(() => { t.hidden = true; }, 4200);
}
const pastilla = (clase, texto) => `<span class="pastilla ${clase}">${esc(texto)}</span>`;

function capasWonder(w) {
  const capas = [w.emocion, ...ORDEN_CAPAS.filter((a) => w.accesorios.includes(a))];
  return `<div class="wonder-capas" role="img" aria-label="Wonder ${esc(w.emocion)}">${capas
    .map((c) => `<img src="img/wonder_${c}.png" alt="">`).join("")}</div>`;
}

const cacheImg = {};
function imagen(src) {
  cacheImg[src] ??= new Promise((ok, mal) => { const i = new Image(); i.onload = () => ok(i); i.onerror = mal; i.src = src; });
  return cacheImg[src];
}

// ---------- pantalla del llavero (160x128) ----------
const PICO = { navy: "rgb(28,51,80)", azul: "rgb(104,178,255)", claro: "rgb(221,238,255)", gris: "rgb(110,140,170)", blanco: "#fff" };
const POR_PAGINA = 5;

/** Dibuja el calendario igual que dibujar_calendario() de main.py (lienzo al doble). */
function dibujarCalendarioPico(canvas, eventos, hora, pagina) {
  const c = canvas.getContext("2d"), W = 160, H = 128;
  c.setTransform(2, 0, 0, 2, 0, 0);
  c.textBaseline = "top";
  c.font = "bold 8.5px 'Courier New', ui-monospace, monospace";
  const texto = (t, x, y, color) => { c.fillStyle = color; [...t].forEach((ch, i) => c.fillText(ch, x + i * 8 + 1, y)); };
  const rect = (x, y, w, h, color) => { c.fillStyle = color; c.fillRect(x, y, w, h); };
  const recortar = (t, n) => (t.length <= n ? t : t.slice(0, n - 1) + "~");
  const paginas = Math.max(1, Math.ceil(eventos.length / POR_PAGINA));
  pagina = Math.max(0, Math.min(pagina, paginas - 1));

  rect(0, 0, W, H, PICO.azul);
  rect(4, 16, W - 8, H - 29, PICO.claro);
  rect(0, 0, W, 14, PICO.navy);
  texto("CALENDARIO", 3, 3, PICO.blanco);
  texto(hora, W - 42, 3, PICO.claro);
  if (!eventos.length) {
    texto("Sin eventos esta", 16, 56, PICO.navy);
    texto("semana :)", 44, 68, PICO.navy);
  } else {
    let y = 18;
    for (const ev of eventos.slice(pagina * POR_PAGINA, (pagina + 1) * POR_PAGINA)) {
      texto(`${ev.dia} ${ev.fecha} ${ev.hora}`, 6, y, PICO.gris);
      texto(recortar(ev.titulo, 18), 6, y + 9, PICO.navy);
      y += 20;
    }
  }
  texto(`${pagina + 1}/${paginas}`, W - 26, H - 10, PICO.blanco);
  texto("<O mantener", 2, H - 10, PICO.claro);
  return pagina;
}

/** "Mi Wonder" como lo arma hub/pantallas.py: fondo oficial + personaje de 124 px. */
async function dibujarWonderPico(canvas, w) {
  const c = canvas.getContext("2d");
  const capas = [w.emocion, ...ORDEN_CAPAS.filter((a) => w.accesorios.includes(a))];
  const [fondo, ...imgs] = await Promise.all([imagen("img/fondo_wonder.jpg"), ...capas.map((n) => imagen(`img/wonder_${n}.png`))]);
  c.imageSmoothingQuality = "high";
  c.drawImage(fondo, 0, 0, 160, 128);
  imgs.forEach((i) => c.drawImage(i, 80 - 62, 3, 124, 124));
}

// ---------- INICIO ----------
function vistaInicio() {
  const e = S.estado, g = e.google, p = e.pico, h = e.hub;
  let google;
  if (g.conectado) {
    google = `
      <div class="fila">${pastilla("pastilla--bien", "Conectado")}${g.cuenta ? `<span class="dato">${esc(g.cuenta)}</span>` : ""}</div>
      <div class="fila">
        ${pastilla(g.calendario ? "pastilla--bien" : "pastilla--mal", g.calendario ? "Calendar: lectura" : "Calendar sin permiso")}
        ${pastilla(g.docs ? "pastilla--bien" : "pastilla--aviso", g.docs ? "Google Docs" : "Docs sin permiso")}
      </div>
      ${!g.calendario ? `<p class="nota nota--mal">No marcaste el permiso de Calendar. Cierra sesión y vuelve a entrar aceptando todos los permisos.</p>` : ""}
      <div class="fila"><a class="boton boton--chico" href="#calendario">Ver calendario</a>
      <button class="boton boton--claro boton--chico" data-accion="google-salir">Cerrar sesión</button></div>`;
  } else if (!g.librerias) {
    google = `<p class="nota nota--ojo">Faltan las librerías de Google en el hub. En la carpeta <code>hub</code> ejecuta <code>pip install -r requirements.txt</code> y vuelve a iniciarlo.</p>`;
  } else if (!g.credenciales) {
    google = `<p class="nota nota--ojo">Falta el archivo <code>credentials.json</code> en la carpeta <code>hub</code>. Es el mismo que ya usan (OAuth “App de escritorio” de Google Cloud). Cópialo ahí y recarga.</p>`;
  } else if (!h.local) {
    google = `<p>Tu cuenta aún no está conectada.</p>
      <p class="nota">El inicio de sesión se hace una sola vez en el computador donde corre Wonder Hub: abre <code>http://localhost:${esc(h.puerto)}</code> allí.</p>`;
  } else {
    google = `<p>Conecta tu cuenta para que el llavero muestre tu calendario y para guardar los resúmenes en Google Docs.</p>
      <div><button class="boton boton--azul" data-accion="google-entrar"><span class="g-logo">G</span>Entrar con Google</button></div>
      <p class="chico suave">Wonder solo lee tus eventos; no los cambia ni los borra.</p>`;
  }

  const estadoPico = p.visto_hace_seg == null
    ? pastilla("", "Aún no se ha conectado")
    : p.en_linea ? pastilla("pastilla--bien", "En línea") : pastilla("pastilla--aviso", "Sin señal");
  const llavero = `
    <div class="pila">
      ${p.visto_hace_seg == null
        ? `<p>Para que el llavero se conecte necesita el nombre y la clave de tu WiFi. La app se los envía.</p>`
        : `<p>Última conexión ${esc(hace(p.visto_hace_seg))}${p.ip ? ` · <span class="dato">${esc(p.ip)}</span>` : ""}</p>
           <div class="fila">
             ${p.usb ? pastilla("pastilla--azul", "Cargando (USB)") : p.bateria != null ? pastilla(p.bateria > 20 ? "pastilla--bien" : "pastilla--mal", `Batería ${p.bateria}%`) : ""}
             ${p.red ? pastilla("", `WiFi: ${p.red}`) : ""}
             ${p.eventos != null ? pastilla("pastilla--azul", `${p.eventos} eventos enviados`) : ""}
             ${pastilla(p.wonder_al_dia ? "pastilla--bien" : "pastilla--aviso", p.wonder_al_dia ? "Mi Wonder al día" : "Mi Wonder pendiente")}
           </div>
           ${p.redes && p.redes.length ? `<p class="chico suave">Redes guardadas en el llavero: ${p.redes.map(esc).join(" · ")}</p>` : ""}`}
      <div><button class="boton ${p.visto_hace_seg == null ? "" : "boton--claro"}" data-accion="configurar">${p.visto_hace_seg == null ? "Configurar llavero" : "Agregar red WiFi"}</button></div>
    </div>`;

  return `
    <section class="saludo">
      <div class="pila">
        <h1>¡Hola! ¿Qué se dice?</h1>
        <p class="lema">“Wisdom begins in wonder.” — Sócrates</p>
      </div>
      <a href="#wonder" aria-label="Personalizar a Wonder">${capasWonder(e.wonder)}</a>
    </section>
    <section class="panel"><div class="panel__cabeza"><h2>Cuenta de Google</h2></div>${google}</section>
    <section class="panel"><div class="panel__cabeza"><h2>Llavero</h2>${estadoPico}</div>${llavero}</section>
    ${vistaRacha(p)}
    ${vistaPomodoro(e.pomodoro)}
    ${vistaLogros(e.logros)}
    ${h.local && h.pin ? `<section class="panel">
      <div class="panel__cabeza"><h2>Abrir en el celular</h2></div>
      <p>Con el celular en el mismo WiFi, entra a <span class="dato">${esc(h.url)}</span> y escribe el PIN <span class="dato">${esc(h.pin)}</span>.</p>
    </section>` : ""}`;
}

// ---------- racha, energía y comida (lo cuenta el llavero) ----------
function barraEnergia(e) {
  const v = Math.max(0, Math.min(100, e ?? 0));
  return `<div class="energia" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${v}" aria-label="Energía de Wonder">
      <div class="energia__lleno ${v >= 25 ? "" : "energia__lleno--poca"}" style="width:${v}%"></div>
      <div class="energia__marca" title="Para jugar hace falta 25 %"></div></div>`;
}

function tarjetasComida(c) {
  return `<div class="comidas">${COMIDAS.map(([id, nombre, rareza, sube, prob]) => `
      <div class="comida comida--${id}">
        <img src="img/comida_${id}.png" alt="">
        <span class="comida__rareza">${rareza}</span>
        <b>${esc(nombre)}</b>
        <span class="chico">+${sube}% energía · sale ${prob} de 100</span>
        <span class="comida__n">× ${c ? (c[id] ?? 0) : "–"}</span>
      </div>`).join("")}</div>`;
}

function vistaRacha(p) {
  if (!p || p.visto_hace_seg == null) return "";
  const r = p.racha ?? 0;
  const juego = p.juego ? JUEGOS[p.juego] || p.juego : null;
  return `<section class="panel">
      <div class="panel__cabeza"><h2>Racha de estudio</h2>${pastilla(r >= 2 ? "pastilla--bien" : "", `🔥 ${r} ${r === 1 ? "día" : "días"}`)}</div>
      <p>Cada día de semana con al menos un pomodoro terminado suma a la racha. Desde <b>2 días seguidos</b>, cada pomodoro le da a Wonder una comida al azar; tú decides cuándo dársela en el llavero (menú Wonder).</p>
      <p class="nota nota--ojo"><b>Sábado y domingo no cuentan</b>: no suman a la racha y tampoco la rompen. Si un día de semana no estudias, la racha vuelve a cero y te toca otro juego.</p>
      <div class="pila"><span class="chico">Energía de Wonder: <b>${esc(p.energia ?? 0)}%</b> (para jugar hace falta 25%; nunca baja sola)</span>${barraEnergia(p.energia)}</div>
      ${tarjetasComida(p.comida)}
      ${juego ? `<div class="fila"><img class="juego-mini" src="img/juego_${esc(p.juego)}.png" alt=""><span>Juego de ahora: <b>${esc(juego)}</b></span></div>` : ""}
    </section>`;
}

function vistaLogros(l) {
  if (!l) return "";
  const lista = (l.ultimos || []).map((u) =>
    `<li class="fila fila--entre"><span>${esc(u.titulo)}</span><span class="chico suave">${esc(fCorta.format(new Date(u.marcado)))}</span></li>`).join("");
  return `<section class="panel">
      <div class="panel__cabeza"><h2>¡Hecho!</h2>${pastilla(l.hoy ? "pastilla--bien" : "", `${l.hoy} hoy`)}</div>
      <p>En el llavero, entra a Calendario, elige una tarea o clase y pulsa <b>O</b> cuando la cumplas. Solo cuenta desde que empieza hasta 12 horas después de que termina, si estaba en el calendario desde antes, y máximo ${esc(l.max_por_dia)} al día.</p>
      <div class="fila">${pastilla("pastilla--azul", `${l.total} en total`)}${pastilla("", `Días seguidos con ¡Hecho!: ${l.racha}`)}</div>
      ${lista ? `<ul class="pila chico">${lista}</ul>` : `<p class="chico suave">Aún no hay nada marcado.</p>`}
    </section>`;
}

function vistaPomodoro(po) {
  if (!po) return "";
  const campo = (id, texto, v, min, max) =>
    `<label class="pila chico">${texto}<input id="${id}" type="number" inputmode="numeric" min="${min}" max="${max}" value="${esc(v)}" style="width:90px"></label>`;
  return `<section class="panel">
      <div class="panel__cabeza"><h2>Pomodoro</h2>${pastilla("", `${po.sesiones} × ${po.estudio}/${po.descanso} min`)}</div>
      <p>El llavero usa estos tiempos. En el llavero también puedes cambiar los minutos con IZQ / DER antes de empezar.</p>
      <div class="fila">${campo("po-estudio", "Estudio (min)", po.estudio, 5, 120)}${campo("po-descanso", "Descanso (min)", po.descanso, 1, 60)}${campo("po-sesiones", "Sesiones", po.sesiones, 1, 12)}</div>
      <div id="po-error" aria-live="polite"></div>
      <div><button class="boton boton--claro boton--chico" data-accion="pomodoro-guardar">Guardar en el llavero</button></div>
    </section>`;
}

// ---------- CALENDARIO ----------
async function cargarEventos(forzar = false) {
  try {
    const r = await api.eventos(forzar);
    S.eventos = r.eventos; S.hora = r.hora; S.errorEventos = null;
  } catch (err) {
    S.eventos = null; S.errorEventos = err.clave === "login" ? "login" : err.message;
  }
}

function vistaCalendario() {
  if (S.errorEventos === "login" || (!S.eventos && !S.estado.google.conectado)) {
    return `<h1>CALENDARIO</h1><section class="panel"><p>Entra con tu cuenta de Google para ver aquí los eventos que recibe el llavero.</p>
      <div><a class="boton" href="#inicio">Ir a conectar Google</a></div></section>`;
  }
  if (S.errorEventos) {
    return `<h1>CALENDARIO</h1><section class="panel"><p class="nota nota--mal">${esc(S.errorEventos)}</p>
      <div><button class="boton" data-accion="cal-actualizar">Reintentar</button></div></section>`;
  }
  if (!S.eventos) return `<h1>CALENDARIO</h1><p class="vacio">Leyendo Google Calendar…</p>`;

  const porDia = new Map();
  for (const ev of S.eventos) {
    const clave = fFecha.format(new Date(ev.inicio));
    if (!porDia.has(clave)) porDia.set(clave, []);
    porDia.get(clave).push(ev);
  }
  const lista = [...porDia].map(([dia, evs]) => `
    <div class="dia"><div class="dia__nombre">${esc(dia)}</div>
      ${evs.map((ev) => `<div class="evento">
        <div class="evento__hora">${ev.todo_el_dia ? "todo el día" : esc(fHora.format(new Date(ev.inicio)))}</div>
        <div><div class="evento__titulo">${esc(ev.titulo)}</div>${ev.lugar ? `<div class="chico suave">${esc(ev.lugar)}</div>` : ""}</div>
      </div>`).join("")}
    </div>`).join("");
  const p = S.estado.pico;

  return `
    <div class="fila fila--entre"><h1>CALENDARIO</h1>
      <button class="boton boton--claro boton--chico" data-accion="cal-actualizar">Actualizar</button></div>
    <section class="panel">
      <div class="panel__cabeza"><h2>Así lo muestra el llavero</h2>
        ${p.eventos != null ? pastilla("pastilla--bien", `Leído ${hace(p.visto_hace_seg)}`) : pastilla("", "El llavero aún no lo ha pedido")}</div>
      <div class="llavero">
        <div class="llavero__pantalla"><canvas id="pico-cal" width="320" height="256" aria-label="Vista previa de la pantalla del llavero"></canvas></div>
        <div class="llavero__botones">
          <button data-accion="cal-pagina" data-paso="-1" aria-label="Página anterior">◀</button>
          <button data-accion="cal-actualizar" aria-label="Actualizar">O</button>
          <button data-accion="cal-pagina" data-paso="1" aria-label="Página siguiente">▶</button>
        </div>
      </div>
      <p class="chico suave">El llavero recibe solo día, fecha, hora y título (sin tildes, máximo 18 letras). Se actualiza al abrir Calendario o al pulsar O.</p>
    </section>
    <section class="panel">
      <div class="panel__cabeza"><h2>Próximos 7 días</h2>${pastilla("pastilla--azul", `${S.eventos.length} eventos`)}</div>
      ${lista || `<p class="vacio">No hay eventos esta semana.</p>`}
    </section>`;
}

// ---------- GRABACIONES ----------
const ESTADOS = {
  pendiente: ["pastilla--latido", "En cola"],
  transcribiendo: ["pastilla--azul pastilla--latido", "Transcribiendo"],
  resumiendo: ["pastilla--azul pastilla--latido", "Resumiendo"],
  listo: ["pastilla--bien", "Listo"],
  error: ["pastilla--mal", "Error"],
};

async function cargarGrabaciones() {
  try { S.grabs = (await api.grabaciones()).grabaciones; } catch (err) { S.grabs = []; avisar(err.message); }
}

function cuerpoGrabacion(g) {
  const d = S.detalle[g.id];
  if (!d) return `<p class="suave">Cargando…</p>`;
  const audio = api.urlAudio(g.id), word = api.urlWord(g.id);
  return `
    ${d.error ? `<p class="nota nota--mal">${esc(d.error)}</p>` : ""}
    ${d.aviso ? `<p class="nota nota--ojo">${esc(d.aviso)}</p>` : ""}
    ${d.resumen ? `<div class="texto-largo">${esc(d.resumen)}</div>` : ""}
    <div class="fila">
      ${d.google_doc ? `<a class="boton boton--chico" href="${esc(d.google_doc)}" target="_blank" rel="noopener">Abrir Google Doc</a>`
        : d.resumen ? `<button class="boton boton--chico" data-accion="grab-doc" data-id="${esc(g.id)}">Crear Google Doc</button>` : ""}
      ${d.word && word ? `<a class="boton boton--claro boton--chico" href="${esc(word)}">Descargar Word</a>` : ""}
      ${d.estado === "error" ? `<button class="boton boton--claro boton--chico" data-accion="grab-reintentar" data-id="${esc(g.id)}">Reintentar</button>` : ""}
    </div>
    ${audio ? `<audio controls preload="none" src="${esc(audio)}"></audio>` : ""}
    ${d.transcripcion ? `<details><summary>Ver transcripción</summary><div class="texto-largo">${esc(d.transcripcion)}</div></details>` : ""}`;
}

function vistaGrabaciones() {
  const ia = S.estado.ia;
  const faltas = [];
  if (!ia.gemini) faltas.push("Falta la librería de Gemini (<code>pip install google-genai</code>): no se puede transcribir ni resumir.");
  else if (!ia.gemini_clave) faltas.push("Falta la variable <code>GEMINI_API_KEY</code> en el computador del hub: no se puede transcribir ni resumir.");
  else if (ia.transcribe_con === "gemini") faltas.push("Se transcribe con Gemini (el audio se sube a Google y se borra al terminar). Para transcribir sin sacar el audio del computador, instala Whisper.");
  const lista = S.grabs == null ? `<p class="vacio">Cargando…</p>`
    : !S.grabs.length ? `<p class="vacio">Todavía no hay grabaciones. Sube un audio o deja uno en la carpeta de clases.</p>`
    : S.grabs.map((g) => {
        const [clase, texto] = ESTADOS[g.estado] || ["", g.estado];
        return `<details class="grabacion" data-id="${esc(g.id)}" ${S.abiertas.has(g.id) ? "open" : ""}>
          <summary>
            <div class="fila fila--entre"><span class="grabacion__titulo">${esc(nombreBonito(g))}</span>${pastilla(clase, texto)}</div>
            <div class="chico">${esc(fCorta.format(new Date(g.creado)))}${g.duracion_seg ? " · " + esc(duracion(g.duracion_seg)) : ""}</div>
            ${g.vista ? `<div class="grabacion__vista">${esc(g.vista)}</div>` : ""}
          </summary>
          <div class="grabacion__cuerpo">${cuerpoGrabacion(g)}</div>
        </details>`;
      }).join("");
  return `
    <div class="fila fila--entre"><h1>GRABACIONES</h1>
      <label class="boton boton--chico" for="subir-audio">Subir audio</label>
      <input id="subir-audio" type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg,.webm,.flac" hidden></div>
    <p class="suave">Cada audio se transcribe con Whisper y se resume con Gemini en el computador. Carpeta de clases: <span class="dato">${esc(ia.carpeta)}</span></p>
    ${faltas.map((f) => `<p class="nota nota--ojo">${f}</p>`).join("")}
    ${lista}`;
}

// ---------- WONDER ----------
const RECORTE = {           // qué parte del PNG (lienzo 800) se ve en cada miniatura de 64 px
  cara: "width:109px;left:-26px;top:0",
  gafas: "width:151px;left:-44px;top:-57px",
  bufanda: "width:341px;left:-146px;top:-220px",
};
function vistaWonder() {
  const w = S.wonder, guardado = S.estado.wonder;
  const igual = w.emocion === guardado.emocion && w.accesorios.slice().sort().join() === guardado.accesorios.slice().sort().join();
  const p = S.estado.pico, total = S.estado.logros?.total ?? 0;
  const emocion = (EMOCIONES.find(([id]) => id === w.emocion) || [, ""])[1];
  return `
    <h1>WONDER</h1>
    <section class="wonder-hero">
      <div class="escenario">${capasWonder(w)}<span class="escenario__etiqueta">${esc(emocion)}${w.accesorios.length ? " · " + w.accesorios.map((a) => esc((ACCESORIOS.find(([id]) => id === a) || [, a])[1])).join(" + ") : ""}</span></div>
      <div class="wonder-hero__datos">
        <div class="dato-grande"><span>🔥</span><b>${esc(p.racha ?? 0)}</b><small>días de racha</small></div>
        <div class="pila"><small>Energía ${esc(p.energia ?? 0)}%</small>${barraEnergia(p.energia)}</div>
        <div class="dato-grande"><span>✔</span><b>${esc(total)}</b><small>¡Hecho! en total</small></div>
      </div>
    </section>
    <section class="panel">
      <h2>¿Cómo se siente?</h2>
      <div class="opciones">${EMOCIONES.map(([id, nombre]) => `
        <button class="opcion" data-accion="emocion" data-id="${id}" aria-pressed="${w.emocion === id}">
          <span class="recorte"><img src="img/wonder_${id}.png" alt="" style="${RECORTE.cara}"></span>${nombre}</button>`).join("")}</div>
      <h2>Accesorios</h2>
      <div class="opciones">${ACCESORIOS.map(([id, nombre]) => `
        <button class="opcion" data-accion="accesorio" data-id="${id}" aria-pressed="${w.accesorios.includes(id)}">
          <span class="recorte"><img src="img/wonder_${id}.png" alt="" style="${RECORTE[id]}"></span>${nombre}</button>`).join("")}
        ${BLOQUEADOS.map(([id, n]) => `
        <div class="opcion opcion--bloqueada" aria-disabled="true">
          <span class="recorte recorte--candado" aria-hidden="true">${total >= n ? "?" : "🔒"}</span>???<small>${total >= n ? "¡Pronto!" : `${n} ¡Hecho!`}</small></div>`).join("")}</div>
    </section>
    <section class="panel">
      <div class="panel__cabeza"><h2>Comida guardada</h2></div>
      ${tarjetasComida(p.comida)}
      <p class="chico suave">En el llavero: menú Wonder → elige la comida → <b>O</b> para dársela.</p>
    </section>
    <section class="panel">
      <div class="panel__cabeza"><h2>En el llavero</h2>
        ${!igual ? pastilla("pastilla--aviso", "Cambios sin guardar")
          : p.wonder_al_dia ? pastilla("pastilla--bien", "El llavero ya lo tiene") : pastilla("pastilla--azul", "Guardado, falta que el llavero lo baje")}</div>
      <div class="llavero"><div class="llavero__pantalla"><canvas id="pico-wonder" width="160" height="128" aria-label="Vista previa de Mi Wonder en el llavero"></canvas></div></div>
      <div><button class="boton" data-accion="wonder-guardar" ${igual ? "disabled" : ""}>Guardar en el llavero</button></div>
      <p class="chico suave">El llavero baja la pantalla nueva la próxima vez que actualice el calendario. Se ve en el inicio pulsando ◀ o ▶.</p>
    </section>`;
}

// ---------- pintar ----------
const VISTAS = { inicio: vistaInicio, calendario: vistaCalendario, grabaciones: vistaGrabaciones, wonder: vistaWonder };

function pintar() {
  vista.innerHTML = VISTAS[S.vista]();
  document.querySelectorAll(".pestanas a").forEach((a) =>
    a.dataset.vista === S.vista ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  const cal = $("#pico-cal");
  if (cal && S.eventos) S.pagina = dibujarCalendarioPico(cal, S.eventos.map((e) => e.pico), S.hora, S.pagina);
  const won = $("#pico-wonder");
  if (won) dibujarWonderPico(won, S.wonder).catch(() => {});
}

async function irA(nombre) {
  S.vista = VISTAS[nombre] ? nombre : "inicio";
  if (S.vista === "wonder") S.wonder = { emocion: S.estado.wonder.emocion, accesorios: [...S.estado.wonder.accesorios] };
  pintar();
  window.scrollTo(0, 0);
  if (S.vista === "calendario" && S.estado.google.conectado) { await cargarEventos(); pintar(); }
  if (S.vista === "grabaciones") { await cargarGrabaciones(); pintar(); }
}

// ---------- configurar llavero ----------
function abrirConfigurar() {
  const h = S.estado.hub;
  dialogo.innerHTML = `
    <form class="dialogo__dentro" id="form-config" novalidate>
      <h2 id="dialogo-titulo">Agregar red WiFi al llavero</h2>
      <p class="suave">El llavero recuerda varias redes (casa, universidad, el WiFi compartido del celular) y se conecta solo a la que tenga cerca. Agregar una red no borra las otras.</p>
      <label>Nombre del WiFi<input id="cfg-wifi" type="text" autocomplete="off" autocapitalize="none" spellcheck="false" required></label>
      <label>Clave del WiFi<input id="cfg-clave" type="password" autocomplete="off"></label>
      <label class="fila chico"><input id="cfg-ver" type="checkbox" style="width:auto"> Mostrar la clave</label>
      <details class="chico"><summary>Avanzado</summary>
        <label>Dirección de Wonder Hub en esa red<input id="cfg-servidor" type="text" value="${esc(h.url)}" spellcheck="false"></label>
        <p class="suave">Si el computador cambia de IP, el llavero busca el hub solo.</p>
        <label>Clave del llavero (la crea el hub)<input id="cfg-llave" type="text" value="${esc(h.clave_pico)}" readonly></label>
      </details>
      <p class="nota nota--ojo chico"><b>WiFi del celular:</b> el llavero solo ve redes de 2,4 GHz. En iPhone activa <b>Maximizar compatibilidad</b> en Compartir internet; en Android elige la banda de 2,4 GHz.</p>
      <ol class="pasos">
        <li>En el llavero, mantén pulsado <b>O</b> en la pantalla de inicio hasta ver <b>CONFIGURAR</b>. Un llavero nuevo entra solo.</li>
        <li>Conecta <b>este dispositivo</b> a la red <span class="dato">${AP_NOMBRE}</span>, clave <span class="dato">${AP_CLAVE}</span>.</li>
        <li>Pulsa <b>Enviar al llavero</b>. Puedes agregar varias redes seguidas. Al terminar, pulsa <b>O</b> en el llavero y vuelve a tu WiFi.</li>
      </ol>
      <p class="nota chico">La clave del WiFi viaja directo de este dispositivo al llavero. Wonder Hub no la recibe ni la guarda.</p>
      <div id="cfg-resultado" aria-live="polite"></div>
      <div id="cfg-redes"></div>
      <div class="fila">
        <button class="boton" type="submit">Enviar al llavero</button>
        <button class="boton boton--claro" type="button" data-accion="cfg-ver-redes">Ver redes guardadas</button>
        <button class="boton boton--claro" type="button" data-accion="cfg-cerrar">Cerrar</button>
      </div>
      <p class="chico suave">Plan B por cable: <button class="enlace" type="button" data-accion="cfg-descargar">descarga config.json</button> y cópialo al llavero con Thonny. Ojo: ese archivo reemplaza las redes que ya tenía.</p>
    </form>`;
  dialogo.showModal();
}

function pintarRedes(redes) {
  $("#cfg-redes").innerHTML = redes.length
    ? `<p class="chico">Redes guardadas en el llavero:</p><ul class="pila chico">${redes.map((r) =>
        `<li class="fila fila--entre"><span class="dato">${esc(r)}</span><button class="boton boton--claro boton--chico" type="button" data-accion="cfg-olvidar" data-red="${esc(r)}">Olvidar</button></li>`).join("")}</ul>`
    : `<p class="chico suave">El llavero aún no tiene redes guardadas.</p>`;
}

function datosConfig() {
  return {
    wifi_nombre: $("#cfg-wifi").value.trim(),
    wifi_clave: $("#cfg-clave").value,
    servidor: $("#cfg-servidor").value.trim().replace(/\/+$/, ""),
    clave: $("#cfg-llave").value,
  };
}
function configValida(c) {
  const res = $("#cfg-resultado");
  if (!c.wifi_nombre) { res.innerHTML = `<p class="nota nota--mal">Escribe el nombre del WiFi.</p>`; $("#cfg-wifi").focus(); return false; }
  if (c.servidor && !/^https?:\/\/.+/.test(c.servidor)) { res.innerHTML = `<p class="nota nota--mal">La dirección del hub debe empezar por http://</p>`; return false; }
  if (/localhost|127\.0\.0\.1/.test(c.servidor)) { res.innerHTML = `<p class="nota nota--mal">El llavero no entiende “localhost”. Usa la IP del computador en el WiFi (por ejemplo ${esc(S.estado.hub.url)}).</p>`; return false; }
  return true;
}

dialogo.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const c = datosConfig(), res = $("#cfg-resultado");
  if (!configValida(c)) return;
  res.innerHTML = `<p class="nota">Buscando el llavero en ${AP_NOMBRE}…</p>`;
  try {
    const r = await api.enviarAlLlavero(c);
    res.innerHTML = `<p class="nota"><b>“${esc(c.wifi_nombre)}” guardada.</b> Puedes agregar otra red. Cuando termines, pulsa O en el llavero y vuelve a conectar este dispositivo a tu WiFi: en Inicio aparecerá En línea.</p>`;
    $("#cfg-wifi").value = ""; $("#cfg-clave").value = "";
    if (r.redes) pintarRedes(r.redes);
  } catch {
    res.innerHTML = `<p class="nota nota--mal">No encontré el llavero. Revisa que muestre CONFIGURAR y que este dispositivo esté conectado a la red ${AP_NOMBRE} (no a tu WiFi). Si sigue sin funcionar, usa el plan B por cable.</p>`;
  }
});

dialogo.addEventListener("change", (ev) => {
  if (ev.target.id === "cfg-ver") $("#cfg-clave").type = ev.target.checked ? "text" : "password";
});

dialogo.addEventListener("click", (ev) => {
  const accion = ev.target.closest("[data-accion]")?.dataset.accion;
  if (accion === "cfg-cerrar") dialogo.close();
  if (accion === "cfg-ver-redes" || accion === "cfg-olvidar") {
    const res = $("#cfg-resultado");
    (accion === "cfg-olvidar" ? api.olvidarRed(ev.target.closest("[data-red]").dataset.red) : api.infoLlavero())
      .then((d) => { res.innerHTML = ""; pintarRedes(d.redes || []); })
      .catch(() => { res.innerHTML = `<p class="nota nota--mal">No encontré el llavero. Revisa que muestre CONFIGURAR y que este dispositivo esté conectado a la red ${AP_NOMBRE}.</p>`; });
  }
  if (accion === "cfg-descargar") {
    const c = datosConfig();
    if (!configValida(c)) return;
    const texto = JSON.stringify({ redes: [{ nombre: c.wifi_nombre, clave: c.wifi_clave, servidor: c.servidor }], servidor: c.servidor, clave: c.clave }, null, 1);
    try {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([texto], { type: "application/json" }));
      a.download = "config.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    } catch { /* sin descargas: queda el texto de abajo */ }
    $("#cfg-resultado").innerHTML = `<p class="nota">Si no se descargó, crea <code>config.json</code> en el llavero con este contenido:</p><pre class="texto-largo" id="cfg-texto"></pre>`;
    $("#cfg-texto").textContent = texto;
  }
});

// ---------- acciones ----------
vista.addEventListener("click", async (ev) => {
  const el = ev.target.closest("[data-accion]");
  if (!el) return;
  const { accion, id } = el.dataset;
  try {
    if (accion === "google-entrar") {
      const r = await api.googleLogin();
      if (r.url) location.href = r.url;
      else { await refrescarEstado(true); avisar("Demostración: cuenta de ejemplo conectada."); }
    } else if (accion === "google-salir") {
      await api.googleLogout(); S.eventos = null; await refrescarEstado(true); avisar("Sesión de Google cerrada.");
    } else if (accion === "configurar") {
      abrirConfigurar();
    } else if (accion === "pomodoro-guardar") {
      const v = (id) => Number($(id).value);
      const datos = { estudio: v("#po-estudio"), descanso: v("#po-descanso"), sesiones: v("#po-sesiones") };
      const err = $("#po-error");
      if (Object.values(datos).some((n) => !Number.isInteger(n) || n < 1)) {
        err.innerHTML = `<p class="nota nota--mal">Escribe números enteros en los tres campos.</p>`; return;
      }
      err.innerHTML = "";
      el.disabled = true;
      await api.guardarPomodoro(datos);
      await refrescarEstado(true); avisar("Guardado. El llavero lo usará en su próxima actualización.");
    } else if (accion === "cal-actualizar") {
      el.disabled = true; await cargarEventos(true); S.pagina = 0; pintar(); if (!S.errorEventos) avisar("Calendario actualizado.");
    } else if (accion === "cal-pagina") {
      S.pagina += Number(el.dataset.paso); pintar();
    } else if (accion === "emocion") {
      S.wonder.emocion = id; pintar();
    } else if (accion === "accesorio") {
      const a = S.wonder.accesorios;
      S.wonder.accesorios = a.includes(id) ? a.filter((x) => x !== id) : [...a, id]; pintar();
    } else if (accion === "wonder-guardar") {
      el.disabled = true;
      await api.guardarWonder(S.wonder.emocion, S.wonder.accesorios);
      await refrescarEstado(true); avisar("Guardado. El llavero lo bajará en su próxima actualización.");
    } else if (accion === "grab-reintentar") {
      await api.reprocesar(id); delete S.detalle[id]; await cargarGrabaciones(); await cargarDetalle(id); pintar();
    } else if (accion === "grab-doc") {
      el.disabled = true; el.textContent = "Creando…";
      await api.crearGoogleDoc(id); await cargarDetalle(id); pintar();
    }
  } catch (err) {
    avisar(err.message || "Algo falló.");
    el.disabled = false;
  }
});

async function cargarDetalle(id) {
  try { S.detalle[id] = await api.grabacion(id); } catch { /* se reintenta al abrir */ }
}

// abrir una grabación carga su resumen y transcripción
vista.addEventListener("toggle", async (ev) => {
  const d = ev.target;
  if (!d.classList?.contains("grabacion")) return;
  const id = d.dataset.id;
  if (!d.open) { S.abiertas.delete(id); return; }
  S.abiertas.add(id);
  if (!S.detalle[id]) {
    await cargarDetalle(id);
    const g = S.grabs?.find((x) => x.id === id);
    const cuerpo = d.querySelector(".grabacion__cuerpo");
    if (g && cuerpo) cuerpo.innerHTML = cuerpoGrabacion(g);
  }
}, true);

vista.addEventListener("change", async (ev) => {
  if (ev.target.id !== "subir-audio" || !ev.target.files[0]) return;
  const archivo = ev.target.files[0];
  avisar(`Subiendo ${archivo.name}…`);
  try {
    await api.subirAudio(archivo);
    avisar("Audio recibido. Empieza la transcripción.");
    await cargarGrabaciones(); pintar();
  } catch (err) { avisar(err.message); }
});

// ---------- refresco periódico ----------
const firma = (e) => JSON.stringify([e.google.conectado, e.google.cuenta, e.pico.en_linea, e.pico.wonder_al_dia, e.pico.eventos,
  e.pico.bateria, e.pico.usb, e.pico.red, e.pico.redes, e.pomodoro, e.logros?.total, e.wonder.version, e.ia,
  e.pico.racha, e.pico.energia, e.pico.comida, e.pico.juego]);

async function refrescarEstado(forzarPintado = false) {
  let nuevo;
  try { nuevo = await api.estado(); } catch { return; }
  const cambio = !S.estado || firma(nuevo) !== firma(S.estado);
  S.estado = nuevo;
  if (forzarPintado || cambio || S.vista === "inicio") {
    if (dialogo.open && !forzarPintado) return;
    pintar();
  }
}

async function refrescarGrabaciones() {
  if (S.vista !== "grabaciones" || !S.grabs) return;
  const enCurso = S.grabs.some((g) => ["pendiente", "transcribiendo", "resumiendo"].includes(g.estado));
  const antes = JSON.stringify(S.grabs);
  await cargarGrabaciones();
  if (JSON.stringify(S.grabs) === antes) return;
  for (const id of S.abiertas) await cargarDetalle(id);      // lo abierto se vuelve a leer
  const sonando = [...vista.querySelectorAll("audio")].some((a) => !a.paused);
  if (enCurso || !sonando) pintar();
}

// ---------- PIN (cuando se abre desde otro dispositivo) ----------
function pedirPin() {
  vista.innerHTML = `
    <h1>PIN</h1>
    <form class="panel" id="form-pin">
      <p>Escribe el PIN de 6 dígitos que muestra Wonder Hub en el computador (en la terminal o en la app, sección Inicio).</p>
      <label>PIN<input id="pin" type="text" inputmode="numeric" maxlength="6" autocomplete="one-time-code" required></label>
      <div id="pin-error" aria-live="polite"></div>
      <div><button class="boton" type="submit">Entrar</button></div>
    </form>`;
  $("#form-pin").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try { await api.emparejar($("#pin").value.trim()); location.reload(); }
    catch (err) { $("#pin-error").innerHTML = `<p class="nota nota--mal">${esc(err.message)}</p>`; }
  });
}

// ---------- tema claro / oscuro ----------
// Tres posiciones: Auto (sigue al sistema) -> Claro -> Oscuro. Se recuerda en este navegador.
const TEMAS = [["auto", "◐ Auto"], ["light", "☀ Claro"], ["dark", "☾ Oscuro"]];
const sistemaOscuro = window.matchMedia("(prefers-color-scheme: dark)");

function temaElegido() {
  try { const t = localStorage.getItem("wonder-tema"); return t === "light" || t === "dark" ? t : "auto"; } catch { return "auto"; }
}
function aplicarTema(tema) {
  const raiz = document.documentElement;
  if (tema === "auto") delete raiz.dataset.theme; else raiz.dataset.theme = tema;
  const oscuro = tema === "dark" || (tema === "auto" && sistemaOscuro.matches);
  $('meta[name="theme-color"]').content = oscuro ? "#070b14" : "#dceaff";
  const boton = $("#boton-tema");
  boton.textContent = TEMAS.find(([id]) => id === tema)[1];
  boton.setAttribute("aria-label", `Tema: ${boton.textContent.slice(2)}. Pulsa para cambiar.`);
  boton.dataset.tema = tema;
}
$("#boton-tema").addEventListener("click", (ev) => {
  const i = TEMAS.findIndex(([id]) => id === ev.currentTarget.dataset.tema);
  const tema = TEMAS[(i + 1) % TEMAS.length][0];
  try { tema === "auto" ? localStorage.removeItem("wonder-tema") : localStorage.setItem("wonder-tema", tema); } catch { /* sin almacenamiento: vale solo esta visita */ }
  aplicarTema(tema);
});
sistemaOscuro.addEventListener("change", () => aplicarTema($("#boton-tema").dataset.tema));
aplicarTema(temaElegido());

// ---------- arranque ----------
async function arrancar() {
  const r = await api.conectar();
  if (r.pin) { $(".pestanas").hidden = true; pedirPin(); return; }
  S.estado = r.estado;
  $("#aviso-demo").hidden = !api.esDemo;

  const google = new URLSearchParams(location.search).get("google");
  if (google) {
    history.replaceState(null, "", location.pathname + location.hash);
    avisar({ ok: "Cuenta de Google conectada.", cancelado: "No se completó el inicio de sesión.", error: "Google rechazó el inicio de sesión. Inténtalo de nuevo." }[google] || "");
  }
  window.addEventListener("hashchange", () => irA(location.hash.slice(1)));
  await irA(location.hash.slice(1) || "inicio");
  setInterval(refrescarEstado, 10000);
  setInterval(refrescarGrabaciones, 5000);
}

arrancar();
