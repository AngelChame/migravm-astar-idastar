"""API web de MigraVM (FastAPI) y archivos de la pantalla.

Arranque, desde la raiz del repositorio:

    uvicorn web.app:app --reload

y abrir http://127.0.0.1:8000/ en el navegador. Las rutas de la API estan bajo /api/
(ver ARQUITECTURA.md, seccion 4, modulo 6). La pantalla se sirve desde web/estatico/.
"""
import csv
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StrictInt, StrictStr

from buscadores import buscar
from escenarios import cargar_escenario, leer_metas
from heuristicas import HEURISTICAS, h1, h2
from modelo import Escenario, EscenarioInvalido, aplicar, cargas, validar_escenario

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "escenarios" / "datos"
RESULTADOS = RAIZ / "medicion" / "resultados"
ESTATICO = Path(__file__).resolve().parent / "estatico"

ALGORITMOS = ("ucs", "voraz", "astar", "ida")
TOPE_POR_OMISION = 150_000
TOPE_MAXIMO = 150_000
MAX_SERVIDORES = 8
MAX_VMS = 24
COMPARACION_POR_OMISION = (("ucs", "h0"), ("voraz", "h2"), ("astar", "h1"), ("astar", "h2"),
                           ("ida", "h2"))

app = FastAPI(title="MigraVM", description="Planificador de migraciones de VM con A* e IDA*")


# --- Entrada ---

class EscenarioEntrada(BaseModel):
    capacidades: list[StrictInt]
    tamanos: list[StrictInt]
    inicial: list[StrictInt]
    servidor_a_vaciar: StrictInt


class PedidoBuscar(BaseModel):
    escenario: EscenarioEntrada
    algoritmo: StrictStr
    heuristica: StrictStr = "h2"
    tope_nodos: StrictInt = TOPE_POR_OMISION


class PedidoComparar(BaseModel):
    escenario: EscenarioEntrada
    tope_nodos: StrictInt = TOPE_POR_OMISION
    heuristicas: Optional[list[StrictStr]] = None


def _error(mensaje: str) -> HTTPException:
    return HTTPException(status_code=422, detail=mensaje)


def en_vivo(servidores: int, vms: int) -> bool:
    return servidores <= MAX_SERVIDORES and vms <= MAX_VMS


def _a_escenario(entrada: EscenarioEntrada) -> Escenario:
    """Convierte la entrada JSON a Escenario (tuplas), valida y aplica el limite en vivo."""
    esc = Escenario(
        capacidades=tuple(entrada.capacidades),
        tamanos=tuple(entrada.tamanos),
        inicial=tuple(entrada.inicial),
        servidor_a_vaciar=entrada.servidor_a_vaciar,
    )
    try:
        validar_escenario(esc)
    except EscenarioInvalido as error:
        raise _error(f"escenario invalido: {error}") from None
    if not en_vivo(len(esc.capacidades), len(esc.tamanos)):
        raise _error(f"en vivo se aceptan hasta {MAX_SERVIDORES} servidores y {MAX_VMS} VM; "
                     f"este escenario tiene {len(esc.capacidades)} y {len(esc.tamanos)}. "
                     f"Use /api/precalculado")
    return esc


def _validar_tope(tope_nodos: int) -> None:
    if not 1 <= tope_nodos <= TOPE_MAXIMO:
        raise _error(f"tope_nodos debe estar entre 1 y {TOPE_MAXIMO}, se recibio {tope_nodos}")


def _validar_configuracion(algoritmo: str, heuristica: str) -> None:
    if algoritmo not in ALGORITMOS:
        raise _error(f"algoritmo desconocido: {algoritmo!r}; use uno de {list(ALGORITMOS)}")
    if algoritmo != "ucs" and heuristica not in HEURISTICAS:
        raise _error(f"heuristica desconocida: {heuristica!r}; use una de {list(HEURISTICAS)}")


# --- Solucion ---

def _solucion(esc: Escenario, algoritmo: str, heuristica: str, tope_nodos: int) -> dict:
    inicio = time.process_time()
    r = buscar(esc, algoritmo, heuristica, tope_nodos)
    tiempo = time.process_time() - inicio

    plan = None
    if r.plan is not None:
        plan = []
        estado, g = esc.inicial, 0
        for paso, accion in enumerate(r.plan, start=1):
            estado = aplicar(esc, estado, accion)
            g += esc.tamanos[accion.vm]
            plan.append({
                "paso": paso, "vm": accion.vm, "origen": accion.origen,
                "destino": accion.destino, "costo": esc.tamanos[accion.vm],
                "cargas_despues": list(cargas(esc, estado)),
                "g": g, "h1": h1(esc, estado), "h2": h2(esc, estado),
            })
    return {
        "algoritmo": r.algoritmo, "heuristica": r.heuristica, "estado": r.estado,
        "costo": r.costo, "nodos_expandidos": r.nodos_expandidos,
        "estados_guardados": r.estados_guardados, "iteraciones": r.iteraciones,
        "tiempo_cpu_s": tiempo, "tope_nodos": tope_nodos,
        "inicial": {"cargas": list(cargas(esc, esc.inicial)),
                    "h1": h1(esc, esc.inicial), "h2": h2(esc, esc.inicial)},
        "plan": plan,
    }


# --- Escenarios y resultados precalculados ---

_CARPETA = re.compile(r"^(\d+)x(\d+)_s(\d+)$")


@lru_cache(maxsize=1)
def _escenarios_disponibles() -> tuple[dict, ...]:
    entradas = []
    for carpeta in DATOS.iterdir():
        coincidencia = _CARPETA.match(carpeta.name)
        if not carpeta.is_dir() or coincidencia is None:
            continue
        servidores, vms, semilla = (int(v) for v in coincidencia.groups())
        for x, _, _ in leer_metas(carpeta):
            esc = cargar_escenario(carpeta, x)
            entradas.append(((servidores, vms, semilla, x), {
                "nombre": esc.nombre,
                "servidores": servidores,
                "vms": vms,
                "en_vivo": en_vivo(servidores, vms),
                "escenario": {
                    "capacidades": list(esc.capacidades),
                    "tamanos": list(esc.tamanos),
                    "inicial": list(esc.inicial),
                    "servidor_a_vaciar": esc.servidor_a_vaciar,
                },
            }))
    return tuple(entrada for _, entrada in sorted(entradas, key=lambda e: e[0]))


def _valor(texto: str):
    """Celda de CSV a numero si se puede; vacia a None."""
    if texto == "":
        return None
    for convertir in (int, float):
        try:
            return convertir(texto)
        except ValueError:
            pass
    return texto


def _leer_filas(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return [{k: _valor(v) for k, v in fila.items()} for fila in csv.DictReader(archivo)]


# --- Rutas ---

@app.get("/api/escenarios")
def listar_escenarios() -> list[dict]:
    return list(_escenarios_disponibles())


@app.post("/api/buscar")
def buscar_plan(pedido: PedidoBuscar) -> dict:
    _validar_configuracion(pedido.algoritmo, pedido.heuristica)
    _validar_tope(pedido.tope_nodos)
    esc = _a_escenario(pedido.escenario)
    return _solucion(esc, pedido.algoritmo, pedido.heuristica, pedido.tope_nodos)


@app.post("/api/comparar")
def comparar(pedido: PedidoComparar) -> list[dict]:
    _validar_tope(pedido.tope_nodos)
    if pedido.heuristicas is None:
        configuraciones = list(COMPARACION_POR_OMISION)
    else:
        if not pedido.heuristicas:
            raise _error("heuristicas no puede ser una lista vacia")
        if len(set(pedido.heuristicas)) != len(pedido.heuristicas):
            raise _error(f"heuristicas repetidas: {pedido.heuristicas}")
        for nombre in pedido.heuristicas:
            _validar_configuracion("astar", nombre)
        configuraciones = [("ucs", "h0")] + [(a, h) for a in ("voraz", "astar", "ida")
                                             for h in pedido.heuristicas]
    esc = _a_escenario(pedido.escenario)
    return [_solucion(esc, a, h, pedido.tope_nodos) for a, h in configuraciones]


@app.get("/api/precalculado")
def precalculado() -> dict:
    resumen = _leer_filas(RESULTADOS / "resumen.csv")
    mediciones = []
    for ruta in sorted(RESULTADOS.glob("mediciones_*.csv")):
        mediciones.extend(fila for fila in _leer_filas(ruta)
                          if not en_vivo(fila["servidores"], fila["vms"]))
    return {"resumen": resumen, "mediciones": mediciones}


app.mount("/", StaticFiles(directory=ESTATICO, html=True, check_dir=False), name="estatico")
