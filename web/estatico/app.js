"use strict";

// Pantalla de MigraVM: consume la API de web/app.py (ARQUITECTURA.md, modulo 6).

const EJEMPLO = {
  nombre: "ejemplo",
  servidores: 4,
  vms: 6,
  en_vivo: true,
  escenario: {
    capacidades: [6, 6, 6, 6],
    tamanos: [2, 1, 3, 1, 4, 4],
    inicial: [3, 3, 0, 3, 2, 1],
    servidor_a_vaciar: 0,
  },
};

const NOMBRES_ALGORITMO = {
  ucs: "Costo uniforme",
  voraz: "Voraz",
  astar: "A*",
  ida: "IDA*",
  ida_sin_tabla: "IDA* sin tabla",
};
const OPTIMOS = ["ucs", "astar", "ida", "ida_sin_tabla"];
const ESTADOS = { resuelto: "resuelto", sin_solucion: "sin solución", tope: "llegó al tope" };

const estado = {
  escenarios: [],
  actual: null,      // entrada de /api/escenarios
  solucion: null,    // respuesta de /api/buscar
  paso: 0,
  comparacion: null, // respuesta de /api/comparar
  precalculado: null,
  ocupado: false,
};

const $ = (id) => document.getElementById(id);

function crear(etiqueta, opciones = {}, hijos = []) {
  const nodo = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(opciones)) {
    if (clave === "texto") nodo.textContent = valor;
    else if (clave === "clase") nodo.className = valor;
    else if (clave === "estilo") Object.assign(nodo.style, valor);
    else nodo.setAttribute(clave, valor);
  }
  for (const hijo of hijos) nodo.append(hijo);
  return nodo;
}

function vaciar(nodo) {
  while (nodo.firstChild) nodo.removeChild(nodo.firstChild);
}

function fila(celdas, clase) {
  const tr = crear("tr", clase ? { clase } : {});
  for (const celda of celdas) tr.append(crear("td", { texto: celda === null || celda === undefined ? "–" : String(celda) }));
  return tr;
}

function formatoNumero(valor, decimales = 4) {
  if (valor === null || valor === undefined) return "–";
  if (Number.isInteger(valor)) return valor.toLocaleString("es-MX");
  return Number(valor.toPrecision(decimales)).toLocaleString("es-MX");
}

function nombreConfiguracion(algoritmo, heuristica) {
  const base = NOMBRES_ALGORITMO[algoritmo] || algoritmo;
  return algoritmo === "ucs" ? base : `${base} con ${heuristica}`;
}

// --- Red ---

async function pedir(ruta, cuerpo) {
  const opciones = cuerpo === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  };
  const respuesta = await fetch(ruta, opciones);
  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    let detalle = datos && datos.detail;
    if (Array.isArray(detalle)) detalle = detalle.map((d) => `${(d.loc || []).join(".")}: ${d.msg}`).join("; ");
    throw new Error(detalle || `error ${respuesta.status}`);
  }
  return datos;
}

function ponerOcupado(ocupado, texto) {
  estado.ocupado = ocupado;
  const mensaje = $("mensaje-busqueda");
  mensaje.className = ocupado ? "mensaje calculando" : "mensaje";
  mensaje.textContent = ocupado ? texto : "";
  actualizarBotones();
}

function mostrarError(error) {
  const mensaje = $("mensaje-busqueda");
  mensaje.className = "mensaje error";
  mensaje.textContent = `Error: ${error.message}`;
}

// --- Escenario actual ---

function escenarioActual() {
  const base = estado.actual.escenario;
  return { ...base, servidor_a_vaciar: Number($("servidor-a-vaciar").value) };
}

function asignacionEnPaso(k) {
  const esc = escenarioActual();
  const asignacion = esc.inicial.slice();
  const plan = (estado.solucion && estado.solucion.plan) || [];
  for (let i = 0; i < Math.min(k, plan.length); i += 1) asignacion[plan[i].vm] = plan[i].destino;
  return asignacion;
}

function cargasDe(esc, asignacion) {
  const cargas = esc.capacidades.map(() => 0);
  asignacion.forEach((servidor, vm) => { cargas[servidor] += esc.tamanos[vm]; });
  return cargas;
}

// --- Dibujo ---

function dibujarEscenario() {
  const esc = escenarioActual();
  const tbody = $("tabla-vms").querySelector("tbody");
  vaciar(tbody);
  esc.tamanos.forEach((tam, vm) => tbody.append(fila([`VM ${vm}`, `${tam} GB`, `Servidor ${esc.inicial[vm]}`])));
  const total = esc.tamanos.reduce((a, b) => a + b, 0);
  $("detalle-escenario").textContent =
    `${esc.capacidades.length} servidores de ${esc.capacidades[0]} GB, ${esc.tamanos.length} VM (${total} GB en total).` +
    (estado.actual.en_vivo ? "" : " No se calcula en vivo.");
}

function dibujarCluster() {
  const esc = escenarioActual();
  const asignacion = asignacionEnPaso(estado.paso);
  const cargas = cargasDe(esc, asignacion);
  const plan = (estado.solucion && estado.solucion.plan) || [];
  const movida = estado.paso > 0 && plan.length ? plan[estado.paso - 1].vm : null;
  const contenedor = $("servidores");
  vaciar(contenedor);
  const angosto = esc.capacidades.length > 6;
  contenedor.style.gridTemplateColumns = `repeat(${esc.capacidades.length}, minmax(0, 1fr))`;
  esc.capacidades.forEach((capacidad, j) => {
    const esMeta = j === esc.servidor_a_vaciar;
    const torre = crear("div", { clase: "torre" });
    asignacion.forEach((servidor, vm) => {
      if (servidor !== j) return;
      const tam = esc.tamanos[vm];
      const cabe = tam / capacidad >= 0.12;
      const etiqueta = !cabe ? String(vm) : (angosto ? `${vm} · ${tam}` : `VM ${vm} · ${tam} GB`);
      torre.append(crear("div", {
        clase: vm === movida ? "bloque-vm movida" : "bloque-vm",
        title: `VM ${vm}, ${tam} GB`,
        texto: etiqueta,
        estilo: { height: `calc(${(100 * tam) / capacidad}% - 2px)` },
      }));
    });
    const libre = capacidad - cargas[j];
    const pie = crear("div", { clase: "pie-servidor" }, [
      crear("strong", { texto: `Servidor ${j}` }),
      crear("span", { texto: esMeta ? `A vaciar, ${cargas[j]} de ${capacidad} GB` : `${cargas[j]} de ${capacidad} GB, libres ${libre}` }),
    ]);
    const barra = crear("div", {
      clase: "barra", role: "img", "aria-label": `Servidor ${j}: ${cargas[j]} de ${capacidad} GB`,
    }, [crear("div", { estilo: { width: `${Math.min(100, (100 * cargas[j]) / capacidad)}%` } })]);
    contenedor.append(crear("div", { clase: esMeta ? "servidor meta" : "servidor" }, [torre, barra, pie]));
  });
  const total = plan.length;
  $("titulo-cluster").textContent = total ? `Clúster, paso ${estado.paso} de ${total}` : "Clúster";
}

function dibujarPlan() {
  const lista = $("plan");
  vaciar(lista);
  const s = estado.solucion;
  if (!s) {
    $("titulo-plan").textContent = "Plan";
    lista.append(crear("li", { clase: "nota", texto: estado.actual.en_vivo ? "Elija algoritmo y pulse \"Buscar plan\"." : "Vea los resultados precalculados." }));
    return;
  }
  if (!s.plan) {
    $("titulo-plan").textContent = "Plan";
    const razon = s.estado === "tope"
      ? `La búsqueda llegó al tope de ${formatoNumero(s.tope_nodos)} nodos sin encontrar la meta (puede haber solución).`
      : "No hay solución: alguna VM no cabe en ningún servidor.";
    lista.append(crear("li", { clase: "nota", texto: razon }));
    return;
  }
  $("titulo-plan").textContent = `Plan encontrado, costo total ${s.costo} GB`;
  const pasos = [{ etiqueta: "Inicio", texto: "Estado inicial", costo: "g = 0" }].concat(
    s.plan.map((p) => ({
      etiqueta: `Paso ${p.paso}`,
      texto: `Migrar VM ${p.vm} (${p.costo} GB) del servidor ${p.origen} al servidor ${p.destino}`,
      costo: `costo ${p.costo}`,
    })));
  pasos.forEach((p, i) => {
    const boton = crear("button", { type: "button", clase: i === estado.paso ? "paso actual" : "paso" }, [
      crear("span", { clase: "etiqueta", texto: p.etiqueta }),
      crear("span", { texto: p.texto }),
      crear("span", { clase: "costo", texto: p.costo }),
    ]);
    if (i === estado.paso) boton.setAttribute("aria-current", "step");
    boton.addEventListener("click", () => irAPaso(i));
    lista.append(crear("li", {}, [boton]));
  });
}

function dibujarNodo() {
  const asignacion = asignacionEnPaso(estado.paso);
  $("estado-s").textContent = `s = (${asignacion.join(", ")})`;
  const s = estado.solucion;
  const heuristica = s ? s.heuristica : $("heuristica").value;
  $("etiqueta-f").textContent = heuristica === "h0" ? "f = g (h0 = 0)" : `f = g + ${heuristica}`;
  let g = null, h1 = null, h2 = null;
  if (s) {
    if (estado.paso === 0 || !s.plan) {
      g = 0; h1 = s.inicial.h1; h2 = s.inicial.h2;
    } else {
      const p = s.plan[estado.paso - 1];
      g = p.g; h1 = p.h1; h2 = p.h2;
    }
  }
  const h = { h0: 0, h1, h2 }[heuristica];
  const conUnidad = (v) => (v === null || v === undefined ? "–" : `${v} GB`);
  $("valor-g").textContent = conUnidad(g);
  $("valor-h1").textContent = conUnidad(h1);
  $("valor-h2").textContent = conUnidad(h2);
  $("valor-f").textContent = g === null ? "–" : conUnidad(g + h);
  $("resumen-busqueda").textContent = s
    ? `${nombreConfiguracion(s.algoritmo, s.heuristica)}: ${ESTADOS[s.estado]}, ` +
      `${formatoNumero(s.nodos_expandidos)} nodos expandidos, ${formatoNumero(s.estados_guardados)} estados guardados` +
      (s.iteraciones ? `, ${s.iteraciones} iteraciones` : "") +
      (s.tiempo_cpu_s > 0 ? `, ${formatoNumero(s.tiempo_cpu_s * 1000, 3)} ms de CPU.` : ", menos de 16 ms de CPU (resolución del reloj).") +
      (s.algoritmo === "voraz" ? " La voraz ordena solo por h." : "")
    : "";
}

function dibujarComparacion() {
  const tbody = $("tabla-comparacion").querySelector("tbody");
  vaciar(tbody);
  const lista = estado.comparacion;
  if (!lista) {
    const texto = estado.actual && !estado.actual.en_vivo ? "No se compara en vivo: vea los resultados precalculados." : "Pulse \"Comparar todos\".";
    tbody.append(crear("tr", {}, [crear("td", { colspan: "4", clase: "vacio", texto })]));
    return;
  }
  const optimos = lista.filter((s) => OPTIMOS.includes(s.algoritmo) && s.estado === "resuelto").map((s) => s.costo);
  const mejor = optimos.length ? Math.min(...optimos) : null;
  const elegido = estado.solucion;
  for (const s of lista) {
    const costo = s.estado === "resuelto" ? `${s.costo} GB` : ESTADOS[s.estado];
    const optimo = s.estado !== "resuelto" || mejor === null ? "–" : (s.costo === mejor ? "Sí" : "No");
    const destacada = elegido && elegido.algoritmo === s.algoritmo && elegido.heuristica === s.heuristica;
    tbody.append(fila([nombreConfiguracion(s.algoritmo, s.heuristica), costo, formatoNumero(s.nodos_expandidos), optimo],
      destacada ? "destacada" : ""));
  }
}

async function dibujarPrecalculado() {
  const tarjeta = $("tarjeta-precalculado");
  tarjeta.hidden = estado.actual.en_vivo;
  if (estado.actual.en_vivo) return;
  try {
    if (!estado.precalculado) {
      ponerOcupado(true, "Cargando resultados precalculados…");
      estado.precalculado = await pedir("/api/precalculado");
      ponerOcupado(false);
    }
  } catch (error) {
    ponerOcupado(false);
    mostrarError(error);
    return;
  }
  const { resumen, mediciones } = estado.precalculado;
  const nombre = estado.actual.nombre;
  const cuerpoEscenario = $("tabla-precalculado-escenario").querySelector("tbody");
  vaciar(cuerpoEscenario);
  const propias = mediciones.filter((m) => m.escenario === nombre);
  if (!propias.length) {
    cuerpoEscenario.append(crear("tr", {}, [crear("td", { colspan: "6", clase: "vacio", texto: "Sin mediciones para este escenario." })]));
  }
  for (const m of propias) {
    cuerpoEscenario.append(fila([nombreConfiguracion(m.algoritmo, m.heuristica), ESTADOS[m.estado] || m.estado,
      m.costo === null ? "–" : `${m.costo} GB`, formatoNumero(m.nodos_expandidos),
      formatoNumero(m.estados_guardados), formatoNumero(m.tiempo_cpu_s, 3)]));
  }
  const cuerpoResumen = $("tabla-precalculado-resumen").querySelector("tbody");
  vaciar(cuerpoResumen);
  const filas = resumen.filter((r) => r.servidores === estado.actual.servidores && r.vms === estado.actual.vms);
  for (const r of filas) {
    cuerpoResumen.append(fila([nombreConfiguracion(r.algoritmo, r.heuristica), `${r.resueltos} de ${r.casos}`,
      `${formatoNumero(r.nodos_mediana)} / ${formatoNumero(r.nodos_max)}`, formatoNumero(r.tiempo_mediana_s, 3),
      formatoNumero(r.estados_guardados_max), r.memoria_pico_max_kb === null ? "no medida" : formatoNumero(r.memoria_pico_max_kb, 4)]));
  }
  $("estado-general").textContent = `Tope de nodos de la corrida: ${formatoNumero(filas.length ? filas[0].tope_nodos : null)}.`;
}

function actualizarBotones() {
  const vivo = estado.actual ? estado.actual.en_vivo : false;
  $("boton-buscar").disabled = estado.ocupado || !vivo;
  $("boton-comparar").disabled = estado.ocupado || !vivo;
  const total = estado.solucion && estado.solucion.plan ? estado.solucion.plan.length : 0;
  $("boton-anterior").disabled = estado.ocupado || estado.paso <= 0;
  $("boton-siguiente").disabled = estado.ocupado || estado.paso >= total;
  $("heuristica").disabled = $("algoritmo").value === "ucs";
}

function dibujarTodo() {
  dibujarEscenario();
  dibujarCluster();
  dibujarPlan();
  dibujarNodo();
  dibujarComparacion();
  actualizarBotones();
}

// --- Acciones ---

function irAPaso(i) {
  estado.paso = i;
  dibujarCluster();
  dibujarPlan();
  dibujarNodo();
  actualizarBotones();
}

function reiniciarResultados() {
  estado.solucion = null;
  estado.comparacion = null;
  estado.paso = 0;
  $("mensaje-busqueda").textContent = "";
}

function topeElegido() {
  const tope = Number($("tope").value);
  if (!Number.isInteger(tope) || tope < 1 || tope > 150000) throw new Error("el tope debe ser un entero entre 1 y 150 000");
  return tope;
}

async function buscarPlan(evento) {
  evento.preventDefault();
  if (estado.ocupado || !estado.actual.en_vivo) return;
  try {
    const pedido = {
      escenario: escenarioActual(),
      algoritmo: $("algoritmo").value,
      heuristica: $("heuristica").value,
      tope_nodos: topeElegido(),
    };
    ponerOcupado(true, "Calculando…");
    estado.solucion = await pedir("/api/buscar", pedido);
    estado.paso = 0;
    ponerOcupado(false);
  } catch (error) {
    ponerOcupado(false);
    mostrarError(error);
  }
  dibujarTodo();
}

async function compararTodos() {
  if (estado.ocupado || !estado.actual.en_vivo) return;
  try {
    const pedido = { escenario: escenarioActual(), tope_nodos: topeElegido() };
    ponerOcupado(true, "Calculando los cinco algoritmos…");
    estado.comparacion = await pedir("/api/comparar", pedido);
    ponerOcupado(false);
  } catch (error) {
    ponerOcupado(false);
    mostrarError(error);
  }
  dibujarComparacion();
}

function elegirEscenario() {
  estado.actual = estado.escenarios[Number($("escenario").value)];
  const selector = $("servidor-a-vaciar");
  vaciar(selector);
  estado.actual.escenario.capacidades.forEach((_, j) => selector.append(crear("option", { value: String(j), texto: `Servidor ${j}` })));
  selector.value = String(estado.actual.escenario.servidor_a_vaciar);
  reiniciarResultados();
  $("estado-general").textContent = estado.actual.en_vivo ? "" : "Escenario grande: se muestran resultados precalculados.";
  dibujarTodo();
  dibujarPrecalculado();
}

function elegirServidor() {
  reiniciarResultados();
  dibujarTodo();
}

async function iniciar() {
  $("formulario").addEventListener("submit", buscarPlan);
  $("boton-comparar").addEventListener("click", compararTodos);
  $("boton-anterior").addEventListener("click", () => irAPaso(Math.max(0, estado.paso - 1)));
  $("boton-siguiente").addEventListener("click", () => irAPaso(estado.paso + 1));
  $("escenario").addEventListener("change", elegirEscenario);
  $("servidor-a-vaciar").addEventListener("change", elegirServidor);
  $("algoritmo").addEventListener("change", actualizarBotones);

  let lista = [];
  try {
    lista = await pedir("/api/escenarios");
  } catch (error) {
    const aviso = $("estado-general");
    aviso.className = "estado-general error";
    aviso.textContent = `No se pudo cargar la lista de escenarios: ${error.message}`;
  }
  estado.escenarios = [EJEMPLO].concat(lista);

  const selector = $("escenario");
  const grupos = new Map();
  estado.escenarios.forEach((e, i) => {
    const clave = e === EJEMPLO ? "Ejemplo de la sección 6" : `${e.servidores}×${e.vms}${e.en_vivo ? "" : " (precalculado)"}`;
    if (!grupos.has(clave)) grupos.set(clave, crear("optgroup", { label: clave }));
    grupos.get(clave).append(crear("option", { value: String(i), texto: e.nombre }));
  });
  for (const grupo of grupos.values()) selector.append(grupo);
  selector.value = "0";
  elegirEscenario();
}

document.addEventListener("DOMContentLoaded", iniciar);
