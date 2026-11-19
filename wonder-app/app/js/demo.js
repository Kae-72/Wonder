// Datos de ejemplo para ver la app sin Wonder Hub. Nada de esto es real.

const DIAS = ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"];
const dos = (n) => String(n).padStart(2, "0");

const mem = {
  google: false,
  wonder: { emocion: "feliz", accesorios: ["gafas"], version: 3 },
  picoVersion: 3,
  redes: ["Casa", "iPhone de Paula"],
  pomodoro: { estudio: 25, descanso: 5, sesiones: 4 },
};

function evento(enDias, hora, minutos, duracion, titulo, lugar) {
  const inicio = new Date();
  inicio.setDate(inicio.getDate() + enDias);
  inicio.setHours(hora ?? 0, minutos ?? 0, 0, 0);
  const todoElDia = hora === null;
  const plano = titulo.normalize("NFD").replace(/[̀-ͯ]/g, "");
  return {
    titulo, lugar: lugar || "", todo_el_dia: todoElDia,
    inicio: inicio.toISOString(),
    fin: new Date(inicio.getTime() + duracion * 60000).toISOString(),
    pico: {
      dia: DIAS[inicio.getDay()],
      fecha: `${dos(inicio.getDate())}/${dos(inicio.getMonth() + 1)}`,
      hora: todoElDia ? "todo dia" : `${dos(inicio.getHours())}:${dos(inicio.getMinutes())}`,
      titulo: plano,
    },
  };
}

const eventos = () => [
  evento(1, 7, 0, 110, "Cálculo diferencial", "Bloque C, salón 304"),
  evento(1, 14, 0, 110, "Laboratorio de física", "Lab E2"),
  evento(2, 9, 0, 110, "Programación de computadores", "Sala 512"),
  evento(2, null, 0, 1440, "Entrega taller de álgebra lineal"),
  evento(3, 11, 0, 80, "Música del siglo XIX", "Aula 12"),
  evento(4, 16, 30, 60, "Reunión equipo Wonder"),
  evento(5, 8, 0, 120, "Parcial de cálculo", "Auditorio 2"),
];

const hace = (dias, h, m) => {
  const d = new Date(); d.setDate(d.getDate() - dias); d.setHours(h, m, 5, 0);
  return d.toISOString().slice(0, 19);
};

const grabaciones = [
  {
    id: "clase_algebra", nombre: "Clase de álgebra lineal", archivo: "clase_algebra.wav",
    creado: hace(0, 10, 0), duracion_seg: 4310, estado: "resumiendo", error: null,
  },
  {
    id: "clase_musica", nombre: "Clase música siglo XIX", archivo: "clase_musica.wav",
    creado: hace(1, 11, 2), duracion_seg: 4685, estado: "listo", error: null, word: "x.docx",
    google_doc: "https://docs.google.com/document/",
    resumen:
      "1) Resumen corto\nLa clase recorrió el paso del clasicismo al romanticismo y cómo cambió el papel del compositor.\n\n" +
      "2) Puntos clave\n- El piano se vuelve el instrumento central del salón.\n- Aparece el poema sinfónico como forma libre.\n- El nacionalismo musical toma melodías populares.\n\n" +
      "3) Conceptos importantes\n- Lied: canción para voz y piano sobre un poema.\n- Leitmotiv: tema que identifica a un personaje o idea.\n\n" +
      "4) Tareas o fechas\n- Escuchar dos lieder y traer un párrafo de comparación el jueves.",
    transcripcion: "Buenos días. Hoy vamos a hablar de cómo cambia la música entre el final del siglo dieciocho y el diecinueve… (ejemplo)",
  },
  {
    id: "seminario", nombre: "Seminario pastelería rusa", archivo: "seminario.wav",
    creado: hace(3, 15, 30), duracion_seg: 2950, estado: "error",
    error: "Falta la variable de entorno GEMINI_API_KEY.",
    transcripcion: "Bienvenidos al seminario… (ejemplo)",
  },
];

const corta = (g) => {
  const { transcripcion, resumen, ...resto } = g;
  return { ...resto, vista: (resumen || "").slice(0, 160) };
};

function estado() {
  return {
    hub: { ip: "192.168.1.20", puerto: 8000, url: "http://192.168.1.20:8000", local: true, pin: "123456", clave_pico: "demo0000demo0000" },
    google: { librerias: true, credenciales: true, conectado: mem.google, cuenta: mem.google ? "estudiante@ejemplo.com" : null, calendario: mem.google, docs: mem.google },
    pico: { visto_hace_seg: 42, en_linea: true, ip: "192.168.1.37", wonder_al_dia: mem.picoVersion === mem.wonder.version, eventos: mem.google ? 7 : null,
      bateria: 78, usb: false, red: "iPhone de Paula", redes: [...mem.redes],
      version: "8.0", racha: 3, energia: 62, comida: { mailo: 2, arepa: 1, changua: 1 }, juego: "piper" },
    pomodoro: { ...mem.pomodoro },
    logros: { total: 5, hoy: 1, racha: 3, max_por_dia: 8,
      ultimos: [{ titulo: "Cálculo diferencial", marcado: new Date().toISOString() }] },
    wonder: { ...mem.wonder },
    ia: { whisper: true, gemini: true, gemini_clave: true, word: true, carpeta: "~/clases" },
  };
}

export async function responder(ruta, opciones = {}) {
  const metodo = opciones.method || "GET";
  const r = ruta.split("?")[0];
  if (r === "api/estado") return estado();
  if (r === "api/google/login") { mem.google = true; return { demo: true }; }
  if (r === "api/google/logout") { mem.google = false; return { ok: true }; }
  if (r === "api/eventos") {
    if (!mem.google) { const e = new Error("Inicia sesión con Google."); e.clave = "login"; e.codigo = 401; throw e; }
    const d = new Date();
    return { eventos: eventos(), hora: `${dos(d.getHours())}:${dos(d.getMinutes())}`, cuenta: "estudiante@ejemplo.com" };
  }
  if (r === "api/wonder" && metodo === "POST") {
    mem.wonder = { ...opciones.json, version: mem.wonder.version + 1 };
    return { ...mem.wonder };
  }
  if (r === "api/pomodoro") { mem.pomodoro = { ...opciones.json }; return { ...mem.pomodoro }; }
  if (r === "llavero/info") return { wonder: 2, redes: [...mem.redes] };
  if (r === "llavero/config") {
    mem.redes = [opciones.json.wifi_nombre, ...mem.redes.filter((x) => x !== opciones.json.wifi_nombre)];
    return { ok: true, redes: [...mem.redes] };
  }
  if (r === "llavero/olvidar") { mem.redes = mem.redes.filter((x) => x !== opciones.json.nombre); return { ok: true, redes: [...mem.redes] }; }
  if (r === "api/grabaciones" && metodo === "GET") return { grabaciones: grabaciones.map(corta) };
  if (r === "api/grabaciones" && metodo === "POST") throw new Error("En la demostración no se suben audios.");
  const m = r.match(/^api\/grabaciones\/([^/]+)(?:\/(.+))?$/);
  if (m) {
    const g = grabaciones.find((x) => x.id === decodeURIComponent(m[1]));
    if (!m[2]) return g;
    if (m[2] === "reprocesar") { g.estado = "resumiendo"; g.error = null; return { ok: true }; }
    if (m[2] === "google-doc") { g.google_doc = "https://docs.google.com/document/"; return { url: g.google_doc }; }
  }
  throw new Error("No disponible en la demostración.");
}
