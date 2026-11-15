// Único punto de contacto con Wonder Hub (hub/hub.py).
// Si el hub no responde (p. ej. abriste index.html suelto o una vista previa),
// la app entra en modo demostración con datos de ejemplo.

import * as demo from "./demo.js";

export let esDemo = false;

export class ErrorApi extends Error {
  constructor(mensaje, codigo, clave) {
    super(mensaje);
    this.codigo = codigo;   // estado HTTP
    this.clave = clave;     // "pin", "login", ...
  }
}

async function pedir(ruta, opciones = {}) {
  if (esDemo) return demo.responder(ruta, opciones);
  const cabeceras = { "X-Wonder": "app", ...(opciones.headers || {}) };
  if (opciones.json !== undefined) {
    cabeceras["Content-Type"] = "application/json";
    opciones.body = JSON.stringify(opciones.json);
  }
  const r = await fetch(ruta, { ...opciones, headers: cabeceras, credentials: "same-origin" });
  let datos = null;
  try { datos = await r.json(); } catch { /* respuesta sin JSON */ }
  if (!r.ok) {
    const d = datos || {};
    throw new ErrorApi(d.mensaje || d.error || `El hub respondió ${r.status}`, r.status, d.error);
  }
  return datos;
}

/** Primera llamada: decide si hay hub o si mostramos la demostración. */
export async function conectar() {
  try {
    const r = await fetch("api/estado", { headers: { "X-Wonder": "app" }, credentials: "same-origin" });
    if (r.status === 401) return { pin: true };
    const tipo = r.headers.get("content-type") || "";
    if (!r.ok || !tipo.includes("json")) throw new Error("sin hub");
    return { estado: await r.json() };
  } catch {
    esDemo = true;
    return { estado: await demo.responder("api/estado") };
  }
}

export const estado = () => pedir("api/estado");
export const emparejar = (pin) => pedir("api/emparejar", { method: "POST", json: { pin } });

export const googleLogin = () => pedir("api/google/login", { method: "POST" });
export const googleLogout = () => pedir("api/google/logout", { method: "POST" });

export const eventos = (forzar = false) => pedir("api/eventos" + (forzar ? "?forzar=1" : ""));

export const guardarPomodoro = (datos) => pedir("api/pomodoro", { method: "POST", json: datos });

export const guardarWonder = (emocion, accesorios) =>
  pedir("api/wonder", { method: "POST", json: { emocion, accesorios } });

export const grabaciones = () => pedir("api/grabaciones");
export const grabacion = (id) => pedir("api/grabaciones/" + encodeURIComponent(id));
export const reprocesar = (id) => pedir(`api/grabaciones/${encodeURIComponent(id)}/reprocesar`, { method: "POST" });
export const crearGoogleDoc = (id) => pedir(`api/grabaciones/${encodeURIComponent(id)}/google-doc`, { method: "POST" });
export const subirAudio = (archivo) =>
  pedir("api/grabaciones", { method: "POST", body: archivo, headers: { "X-Nombre": encodeURIComponent(archivo.name) } });
export const urlAudio = (id) => (esDemo ? null : `api/grabaciones/${encodeURIComponent(id)}/audio`);
export const urlWord = (id) => (esDemo ? null : `api/grabaciones/${encodeURIComponent(id)}/word`);

// ---- Hablar directo con el llavero en modo configurar (no pasa por el hub) ----
const LLAVERO = "http://192.168.4.1";

async function alLlavero(ruta, cuerpo) {
  if (esDemo) return demo.responder("llavero" + ruta, { method: cuerpo ? "POST" : "GET", json: cuerpo });
  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), 7000);
  try {
    // text/plain evita la consulta previa (preflight) del navegador
    const r = await fetch(LLAVERO + ruta, cuerpo
      ? { method: "POST", headers: { "Content-Type": "text/plain" }, body: JSON.stringify(cuerpo), signal: control.signal }
      : { signal: control.signal });
    const d = await r.json();
    if (d.ok === false) throw new Error(d.error || "El llavero rechazó los datos");
    return d;
  } finally {
    clearTimeout(reloj);
  }
}

/** Agrega una red WiFi al llavero (las que ya tenía se conservan). */
export const enviarAlLlavero = (config) => alLlavero("/config", config);
export const infoLlavero = () => alLlavero("/info");
export const olvidarRed = (nombre) => alLlavero("/olvidar", { nombre });
