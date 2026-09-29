"use strict";
/* =====================================================================
   Profesora de inglés - lógica de la página
   - Habla: pide la voz al servidor (voces naturales) o usa la del navegador.
   - Escucha: reconocimiento de voz del navegador (Chrome / Edge).
   - Pronunciación: compara lo que se escuchó con la frase a repetir.
   ===================================================================== */

const $ = (sel) => document.querySelector(sel);
const CLAVE_GUARDADO = "clase-en-curso";

const estado = {
  info: null,
  historial: [],          // [{role: "assistant"|"user", content}]
  practica: null,         // frase en inglés que debe repetir, o null
  ultimaRespuesta: "",
  audio: null,            // <audio> que está sonando
  reconocedor: null,
  escuchando: false,
  ocupado: false,
  conversacionAuto: true, // tras hablar la profe, el micrófono se abre solo
};

const Reconocimiento = window.SpeechRecognition || window.webkitSpeechRecognition;

/* ------------------------------------------------------------ utilidades */

function mostrarError(msg) {
  const caja = $("#error");
  caja.textContent = msg;
  caja.hidden = false;
  clearTimeout(mostrarError.t);
  mostrarError.t = setTimeout(() => (caja.hidden = true), 7000);
}

function cargando(si, texto = "Un momento…") {
  $("#cargando").hidden = !si;
  $("#cargando-texto").textContent = texto;
}

async function api(ruta, datos) {
  const opciones = datos === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos),
  };
  const r = await fetch(ruta, opciones);
  if (!r.ok) {
    let detalle = "Algo salió mal. Intenta otra vez.";
    try { detalle = (await r.json()).detail || detalle; } catch (_) { /* sin cuerpo */ }
    throw new Error(detalle);
  }
  return r.json();
}

function escaparHtml(t) {
  return String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function guardarLocal() {
  try { localStorage.setItem(CLAVE_GUARDADO, JSON.stringify(estado.historial)); } catch (_) { /* sin almacenamiento */ }
}
function leerLocal() {
  try { return JSON.parse(localStorage.getItem(CLAVE_GUARDADO) || "null"); } catch (_) { return null; }
}
function borrarLocal() {
  try { localStorage.removeItem(CLAVE_GUARDADO); } catch (_) { /* nada */ }
}

/* ------------------------------------------------------------ vistas */

function irA(vista) {
  document.querySelectorAll(".vista").forEach((v) => (v.hidden = v.id !== `vista-${vista}`));
  if (vista !== "clase") { detenerAudio(); detenerEscucha(); }
  if (vista === "inicio") cargarInicio();
  if (vista === "historial") cargarHistorial();
  window.scrollTo(0, 0);
}

document.querySelectorAll("[data-ir]").forEach((b) => b.addEventListener("click", () => irA(b.dataset.ir)));

async function cargarInicio() {
  try {
    estado.info = await api("/api/estado");
  } catch (e) { mostrarError(e.message); return; }
  const i = estado.info;
  $("#titulo-app").textContent = `Clase de Inglés de ${i.alumna}`;
  $("#saludo").textContent = `¡Hola, ${i.alumna}!`;
  $("#subtitulo").textContent = i.clase_numero === 1
    ? `Soy ${i.profesora}, tu profesora. Vamos a empezar desde cero, paso a paso y sin afanes.`
    : `Hoy es tu clase número ${i.clase_numero}. ¡Qué bueno verte otra vez!`;
  $("#dato-clase").textContent = i.clase_numero;
  $("#dato-unidad").textContent = `${i.unidad_numero}/${i.total_unidades}`;
  $("#dato-unidad-titulo").textContent = i.unidad_titulo;
  $("#dato-palabras").textContent = i.palabras_aprendidas;
  $("#nombre-profe").textContent = `Profe ${i.profesora}`;
  const guardada = leerLocal();
  $("#btn-continuar").hidden = !(guardada && guardada.length);
  $("#aviso-navegador").hidden = !!Reconocimiento;
}

/* ------------------------------------------------------------ texto con marcas [en] / [repite] */

const MARCAS = /\[(en|repite)\]([\s\S]*?)\[\/\1\]/gi;

function textoAHtml(texto) {
  let html = "", pos = 0;
  for (const m of texto.matchAll(MARCAS)) {
    html += escaparHtml(texto.slice(pos, m.index));
    const frase = m[2].trim();
    html += `<span class="en" data-frase="${escaparHtml(frase)}" title="Toca para escuchar">${escaparHtml(frase)}</span>`;
    pos = m.index + m[0].length;
  }
  html += escaparHtml(texto.slice(pos));
  return html.replace(/\[\/?(en|repite)\]/gi, "");
}

function segmentos(texto) {
  const out = [];
  let pos = 0;
  for (const m of texto.matchAll(MARCAS)) {
    if (m.index > pos) out.push({ idioma: "es", texto: texto.slice(pos, m.index) });
    out.push({ idioma: "en", texto: m[2] });
    pos = m.index + m[0].length;
  }
  out.push({ idioma: "es", texto: texto.slice(pos) });
  return out
    .map((s) => ({ ...s, texto: s.texto.replace(/\[\/?(en|repite)\]/gi, "").trim() }))
    .filter((s) => /[\p{L}\p{N}]/u.test(s.texto));
}

function fraseParaRepetir(texto) {
  const m = [...texto.matchAll(/\[repite\]([\s\S]*?)\[\/repite\]/gi)];
  return m.length ? m[m.length - 1][1].trim() : null;
}

/* ------------------------------------------------------------ chat */

function agregarBurbuja(rol, texto) {
  const div = document.createElement("div");
  if (rol === "assistant") {
    div.className = "burbuja profe";
    div.innerHTML = textoAHtml(texto);
  } else if (texto.startsWith("[Resultado de práctica")) {
    div.className = "burbuja nota";
    div.textContent = "🎯 Práctica de pronunciación enviada a la profe";
  } else {
    div.className = "burbuja alumna";
    div.textContent = texto;
  }
  $("#chat").appendChild(div);
  div.scrollIntoView({ behavior: "smooth", block: "end" });
  return div;
}

$("#chat").addEventListener("click", (e) => {
  const en = e.target.closest(".en");
  if (en) hablar(`[en]${en.dataset.frase}[/en]`, true);
});

function ponerEstado(texto) { $("#estado-profe").textContent = texto; }

function actualizarMic() {
  const mic = $("#btn-mic");
  mic.classList.toggle("escuchando", estado.escuchando);
  mic.classList.toggle("ocupado", estado.ocupado && !estado.escuchando);
  $("#mic-texto").textContent = estado.escuchando ? "Te escucho… (toca para terminar)"
    : estado.ocupado ? "Espera…" : estado.practica ? "Toca y repite" : "Toca para hablar";
}

function mostrarPractica(frase) {
  estado.practica = frase;
  $("#practica").hidden = !frase;
  if (frase) $("#practica-frase").textContent = frase;
  actualizarMic();
}

/* ------------------------------------------------------------ conversación */

async function empezarClase(continuar) {
  irA("clase");
  $("#chat").innerHTML = "";
  estado.historial = continuar ? (leerLocal() || []) : [];
  if (!continuar) borrarLocal();
  estado.historial.forEach((m) => agregarBurbuja(m.role, m.content));
  const ultimo = estado.historial[estado.historial.length - 1];
  if (ultimo && ultimo.role === "assistant") {
    estado.ultimaRespuesta = ultimo.content;
    mostrarPractica(fraseParaRepetir(ultimo.content));
    ponerEstado("Tu turno: toca el micrófono");
    actualizarMic();
    return;
  }
  await turnoProfe();
}

async function turnoProfe() {
  estado.ocupado = true;
  actualizarMic();
  ponerEstado("Pensando…");
  let respuesta;
  try {
    respuesta = (await api("/api/hablar", { historial: estado.historial })).respuesta;
  } catch (e) {
    estado.ocupado = false;
    actualizarMic();
    ponerEstado("Hubo un problema. Toca el micrófono para intentarlo otra vez.");
    mostrarError(e.message);
    return;
  }
  estado.historial.push({ role: "assistant", content: respuesta });
  guardarLocal();
  estado.ultimaRespuesta = respuesta;
  agregarBurbuja("assistant", respuesta);
  mostrarPractica(fraseParaRepetir(respuesta));
  const id = await hablar(respuesta);
  estado.ocupado = false;
  ponerEstado("Tu turno");
  actualizarMic();
  // Abre el micrófono solo si nadie pidió otro audio mientras tanto (p. ej. "Repetir").
  if (estado.conversacionAuto && Reconocimiento && id === hablar.id && !$("#vista-clase").hidden) escuchar();
}

async function enviarAlumna(texto) {
  texto = texto.trim();
  if (!texto) return;
  estado.historial.push({ role: "user", content: texto });
  guardarLocal();
  agregarBurbuja("user", texto);
  mostrarPractica(null);
  await turnoProfe();
}

/* ------------------------------------------------------------ voz de la profesora */

function detenerAudio() {
  if (estado.audio) { estado.audio.pause(); estado.audio.onended = null; estado.audio = null; }
  if (window.speechSynthesis) speechSynthesis.cancel();
  $("#avatar").classList.remove("hablando");
  if (hablar.fin) { hablar.fin(); hablar.fin = null; }
}

async function hablar(texto, despacio = false) {
  detenerAudio();
  const id = (hablar.id = (hablar.id || 0) + 1);
  $("#avatar").classList.add("hablando");
  ponerEstado("Hablando…");
  try {
    const r = await fetch("/api/voz", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto, despacio }),
    });
    if (r.status === 200) {
      const url = URL.createObjectURL(await r.blob());
      await new Promise((resolver) => {
        const audio = new Audio(url);
        estado.audio = audio;
        hablar.fin = resolver;
        audio.onended = audio.onerror = () => { hablar.fin = null; resolver(); };
        audio.play().catch(() => { hablar.fin = null; resolver(); });
      });
      URL.revokeObjectURL(url);
    } else {
      await hablarNavegador(texto, despacio);
    }
  } catch (_) {
    await hablarNavegador(texto, despacio);
  }
  if (id === hablar.id) {
    $("#avatar").classList.remove("hablando");
    if (!estado.ocupado && !estado.escuchando) ponerEstado("Tu turno");
  }
  return id;
}

function vozNavegador(prefijo) {
  const voces = speechSynthesis.getVoices();
  const del = voces.filter((v) => v.lang.toLowerCase().startsWith(prefijo));
  return del.find((v) => /natural|neural|online/i.test(v.name)) || del.find((v) => /es-co|en-us/i.test(v.lang)) || del[0];
}

function hablarNavegador(texto, despacio) {
  if (!window.speechSynthesis) return Promise.resolve();
  return new Promise((resolver) => {
    hablar.fin = resolver;
    const partes = segmentos(texto);
    if (!partes.length) { resolver(); return; }
    partes.forEach((p, i) => {
      const u = new SpeechSynthesisUtterance(p.texto);
      u.lang = p.idioma === "en" ? "en-US" : "es-CO";
      u.voice = vozNavegador(p.idioma === "en" ? "en" : "es") || null;
      u.rate = p.idioma === "en" ? (despacio ? 0.6 : 0.8) : (despacio ? 0.9 : 1);
      if (i === partes.length - 1) u.onend = u.onerror = () => { hablar.fin = null; resolver(); };
      speechSynthesis.speak(u);
    });
  });
}
if (window.speechSynthesis) speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();

/* ------------------------------------------------------------ escuchar a la alumna */

function detenerEscucha() {
  if (estado.reconocedor) { try { estado.reconocedor.stop(); } catch (_) { /* ya detenido */ } }
}

function escuchar() {
  if (!Reconocimiento) { mostrarError("Este navegador no puede escuchar. Usa Chrome o Edge, o el botón Escribir."); return; }
  if (estado.escuchando) { detenerEscucha(); return; }
  detenerAudio();

  const enIngles = !!estado.practica;
  const rec = new Reconocimiento();
  rec.lang = enIngles ? "en-US" : "es-CO";
  rec.continuous = true;
  rec.interimResults = true;
  rec.maxAlternatives = 5;
  estado.reconocedor = rec;

  let finales = [];          // por cada resultado final, sus alternativas
  let parcial = "";
  let silencio = null;
  const esperar = enIngles ? 2200 : 2800; // ms de silencio para dar por terminado
  const reiniciarSilencio = () => { clearTimeout(silencio); silencio = setTimeout(() => rec.stop(), esperar); };
  const limite = setTimeout(() => rec.stop(), 45000);

  rec.onstart = () => {
    estado.escuchando = true;
    actualizarMic();
    ponerEstado(enIngles ? "Te escucho en inglés…" : "Te escucho…");
    $("#lo-que-digo").hidden = false;
    $("#lo-que-digo").textContent = "…";
    silencio = setTimeout(() => rec.stop(), 9000); // si no dice nada en 9 s
  };
  rec.onresult = (e) => {
    parcial = "";
    finales = [];
    for (let i = 0; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finales.push([...r].map((a) => a.transcript));
      else parcial += r[0].transcript;
    }
    $("#lo-que-digo").textContent = (finales.map((f) => f[0]).join(" ") + " " + parcial).trim() || "…";
    reiniciarSilencio();
  };
  rec.onerror = (e) => {
    if (e.error === "not-allowed" || e.error === "service-not-allowed") {
      mostrarError("Hay que darle permiso al micrófono (el candado junto a la dirección de la página).");
    } else if (e.error === "network") {
      mostrarError("El reconocimiento de voz necesita internet.");
    }
  };
  rec.onend = () => {
    clearTimeout(silencio); clearTimeout(limite);
    estado.escuchando = false;
    estado.reconocedor = null;
    $("#lo-que-digo").hidden = true;
    actualizarMic();
    if (parcial) finales.push([parcial]);
    const texto = finales.map((f) => f[0]).join(" ").trim();
    if (!texto) { ponerEstado("No te escuché. Toca el micrófono cuando quieras."); return; }
    if (enIngles) evaluarPractica(estado.practica, finales);
    else enviarAlumna(texto);
  };
  rec.start();
}

$("#btn-mic").addEventListener("click", () => {
  if (estado.escuchando) { detenerEscucha(); return; }
  if (estado.ocupado && estado.audio) { detenerAudio(); return; }  // interrumpir a la profe
  if (estado.ocupado) return;
  escuchar();
});

/* ------------------------------------------------------------ pronunciación */

const NUMEROS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
  "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"];
const CONTRACCIONES = { "i'm": "i am", "you're": "you are", "he's": "he is", "she's": "she is", "it's": "it is",
  "we're": "we are", "they're": "they are", "what's": "what is", "don't": "do not", "can't": "can not",
  "cannot": "can not", "i'd": "i would", "that's": "that is", "where's": "where is", "let's": "let us" };

function palabras(texto) {
  return texto.toLowerCase().replace(/[’`]/g, "'").replace(/[^a-z0-9' ]+/g, " ").split(/\s+/).filter(Boolean)
    .flatMap((p) => (CONTRACCIONES[p] || (/^\d+$/.test(p) && NUMEROS[+p]) || p.replace(/'/g, "")).split(" "));
}

function parecido(a, b) {
  if (a === b) return 1;
  const m = a.length, n = b.length;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    prev = cur;
  }
  return 1 - prev[n] / Math.max(m, n);
}

/** Compara palabra por palabra (en orden) la frase objetivo con lo que se escuchó. */
function calificar(objetivo, oido) {
  const obj = palabras(objetivo), dicho = palabras(oido);
  let desde = 0;
  const detalle = obj.map((p) => {
    let mejor = 0, idx = -1;
    for (let j = desde; j < Math.min(dicho.length, desde + 4); j++) {
      const s = parecido(p, dicho[j]);
      if (s > mejor) { mejor = s; idx = j; }
    }
    if (mejor >= 0.5) desde = idx + 1;
    return { palabra: p, oido: mejor >= 0.5 ? dicho[idx] : "", nota: mejor };
  });
  const puntaje = detalle.length ? Math.round(100 * detalle.reduce((s, d) => s + d.nota, 0) / detalle.length) : 0;
  return { detalle, puntaje, oido };
}

function evaluarPractica(frase, finales) {
  // Se prueban todas las alternativas del reconocedor y se queda con la más favorable.
  const candidatos = new Set([finales.map((f) => f[0]).join(" ")]);
  if (finales.length === 1) finales[0].forEach((a) => candidatos.add(a));
  let mejor = null;
  for (const c of candidatos) {
    const r = calificar(frase, c);
    if (!mejor || r.puntaje > mejor.puntaje) mejor = r;
  }

  const tarjeta = document.createElement("div");
  tarjeta.className = "resultado";
  const estrellas = mejor.puntaje >= 85 ? "⭐⭐⭐" : mejor.puntaje >= 60 ? "⭐⭐" : "⭐";
  tarjeta.innerHTML = `<div>${estrellas}</div><div class="palabras">${mejor.detalle.map((d) =>
    `<span class="palabra ${d.nota >= 0.99 ? "bien" : d.nota >= 0.5 ? "casi" : "falta"}">${escaparHtml(d.palabra)}</span>`).join(" ")}</div>
    <div class="oido">Se escuchó: “${escaparHtml(mejor.oido)}”</div>`;
  $("#chat").appendChild(tarjeta);
  tarjeta.scrollIntoView({ behavior: "smooth", block: "end" });

  const porPalabra = mejor.detalle.map((d) => d.nota >= 0.99 ? `${d.palabra} (bien)`
    : d.nota >= 0.5 ? `${d.palabra} (casi: se oyó "${d.oido}")` : `${d.palabra} (no se reconoció)`).join(", ");
  const mensaje = `[Resultado de práctica de pronunciación] Frase: "${frase}". El reconocedor de voz en inglés escuchó: "${mejor.oido}". `
    + `Por palabra: ${porPalabra}. Puntaje aproximado: ${mejor.puntaje}/100.`;
  estado.historial.push({ role: "user", content: mensaje });
  guardarLocal();
  mostrarPractica(null);
  turnoProfe();
}

$("#btn-oir-frase").addEventListener("click", () => estado.practica && hablar(`[en]${estado.practica}[/en]`, true));

/* ------------------------------------------------------------ otros botones */

$("#btn-empezar").addEventListener("click", () => empezarClase(false));
$("#btn-continuar").addEventListener("click", () => empezarClase(true));
$("#btn-repetir").addEventListener("click", () => estado.ultimaRespuesta && !estado.escuchando && hablar(estado.ultimaRespuesta));
$("#btn-despacio").addEventListener("click", () => estado.ultimaRespuesta && !estado.escuchando && hablar(estado.ultimaRespuesta, true));
$("#btn-escribir").addEventListener("click", () => {
  $("#form-escribir").hidden = !$("#form-escribir").hidden;
  if (!$("#form-escribir").hidden) $("#entrada-texto").focus();
});
$("#form-escribir").addEventListener("submit", (e) => {
  e.preventDefault();
  if (estado.ocupado) return;
  const t = $("#entrada-texto").value;
  $("#entrada-texto").value = "";
  enviarAlumna(t);
});

$("#btn-terminar").addEventListener("click", async () => {
  detenerAudio(); detenerEscucha();
  if (estado.historial.filter((m) => m.role === "user").length < 2) {
    if (confirm("La clase apenas empezó. ¿Quieres salir sin guardar resumen?")) { borrarLocal(); irA("inicio"); }
    return;
  }
  cargando(true, "Preparando el resumen de tu clase…");
  try {
    const clase = await api("/api/terminar", { historial: estado.historial });
    borrarLocal();
    estado.historial = [];
    mostrarResumen(clase);
  } catch (e) {
    mostrarError(e.message);
  } finally {
    cargando(false);
  }
});

/* ------------------------------------------------------------ resúmenes */

let resumenActual = null;

function mostrarResumen(clase) {
  const r = clase.resumen;
  resumenActual = clase;
  const lista = (items) => `<ul>${items.map((x) => `<li>${escaparHtml(x)}</li>`).join("")}</ul>`;
  let html = `<h1>Clase ${clase.numero}: ${escaparHtml(r.titulo)}</h1><p class="suave">${escaparHtml(clase.fecha)}</p>
    <p>${escaparHtml(r.resumen)}</p>`;
  if (r.palabras_nuevas?.length) {
    html += `<h2>Palabras nuevas</h2><table><tr><th>Inglés</th><th>Español</th><th>Cómo suena</th></tr>${
      r.palabras_nuevas.map((p) => `<tr><td><span class="en" data-frase="${escaparHtml(p.en)}">${escaparHtml(p.en)}</span></td>
        <td>${escaparHtml(p.es)}</td><td>${escaparHtml(p.pronunciacion)}</td></tr>`).join("")}</table>`;
  }
  if (r.frases_nuevas?.length) html += `<h2>Frases para practicar</h2>${lista(r.frases_nuevas)}`;
  if (r.logros?.length) html += `<h2>¡Lo que hiciste muy bien!</h2>${lista(r.logros)}`;
  if (r.dificultades_pronunciacion?.length) html += `<h2>Sonidos para seguir practicando</h2>${lista(r.dificultades_pronunciacion)}`;
  if (r.tarea) html += `<h2>Tarea para la casa</h2><p class="tarea">${escaparHtml(r.tarea)}</p>`;
  $("#resumen").innerHTML = html;
  irA("resumen");
}

$("#resumen").addEventListener("click", (e) => {
  const en = e.target.closest(".en");
  if (en) hablar(`[en]${en.dataset.frase}[/en]`, true);
});

$("#btn-oir-resumen").addEventListener("click", () => {
  if (!resumenActual) return;
  const r = resumenActual.resumen;
  let texto = `${r.titulo}. ${r.resumen} `;
  if (r.palabras_nuevas?.length) texto += "Las palabras nuevas de hoy: " + r.palabras_nuevas.map((p) => `[en]${p.en}[/en], ${p.es}.`).join(" ") + " ";
  if (r.tarea) texto += `Tu tarea: ${r.tarea}`;
  hablar(texto);
});
$("#btn-imprimir").addEventListener("click", () => window.print());

async function cargarHistorial() {
  const cont = $("#lista-clases");
  cont.innerHTML = "";
  let clases;
  try { clases = await api("/api/clases"); } catch (e) { mostrarError(e.message); return; }
  if (!clases.length) { cont.innerHTML = `<p class="suave">Todavía no hay clases terminadas.</p>`; return; }
  clases.forEach((c) => {
    const b = document.createElement("button");
    b.className = "item-clase";
    b.innerHTML = `<b>Clase ${c.numero}: ${escaparHtml(c.titulo)}</b><small>${escaparHtml(c.fecha)}</small>`;
    b.addEventListener("click", async () => {
      try { mostrarResumen(await api(`/api/clases/${encodeURIComponent(c.id)}`)); } catch (e) { mostrarError(e.message); }
    });
    cont.appendChild(b);
  });
}

cargarInicio();
