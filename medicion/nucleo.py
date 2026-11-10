import csv
import statistics
import time
import tracemalloc
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from buscadores import EstadoBusqueda, Resultado, buscar, ida_estrella
from heuristicas import HEURISTICAS
from modelo import Escenario

COLUMNAS_MEDICION = (
    "escenario", "servidores", "vms", "servidor_a_vaciar", "algoritmo", "heuristica",
    "estado", "costo", "costo_optimo", "migraciones", "nodos_expandidos",
    "estados_guardados", "iteraciones", "tiempo_cpu_s", "memoria_pico_kb", "tope_nodos",
)

_ALGORITMOS = ("ucs", "voraz", "astar", "ida", "ida_sin_tabla")
_OPTIMOS = ("ucs", "astar", "ida", "ida_sin_tabla")
_COLUMNAS_TEXTO = ("escenario", "algoritmo", "heuristica", "estado")
_COLUMNAS_FLOAT = ("tiempo_cpu_s", "memoria_pico_kb")


@dataclass(frozen=True)
class Medicion:
    escenario: str
    servidores: int
    vms: int
    servidor_a_vaciar: int
    algoritmo: str
    heuristica: str
    estado: EstadoBusqueda
    costo: Optional[int]
    costo_optimo: Optional[int]
    migraciones: Optional[int]
    nodos_expandidos: int
    estados_guardados: int
    iteraciones: Optional[int]
    tiempo_cpu_s: float
    memoria_pico_kb: Optional[float]
    tope_nodos: Optional[int]


def _buscador(esc: Escenario, algoritmo: str, heuristica: str,
              tope_nodos: Optional[int]) -> Callable[[], Resultado]:
    """Valida la configuracion y devuelve una funcion que corre la busqueda."""
    if algoritmo not in _ALGORITMOS:
        raise ValueError(f"algoritmo desconocido: {algoritmo!r}")
    if algoritmo != "ucs" and heuristica not in HEURISTICAS:
        raise ValueError(f"heuristica desconocida: {heuristica!r}")
    if algoritmo == "ida_sin_tabla":
        if tope_nodos is None:
            raise ValueError("ida_sin_tabla exige tope_nodos: puede ser exponencial")
        h = HEURISTICAS[heuristica]
        return lambda: ida_estrella(esc, h, tope_nodos, transposicion=False)
    return lambda: buscar(esc, algoritmo, heuristica, tope_nodos)


def medir(esc: Escenario, algoritmo: str, heuristica: str = "h2",
          tope_nodos: Optional[int] = None, con_memoria: bool = False,
          tiempo_minimo_s: float = 0.2) -> Medicion:
    """Corre una busqueda y mide tiempo de CPU y, en una pasada aparte, memoria pico.

    La busqueda se repite hasta acumular tiempo_minimo_s y se reporta el promedio por
    busqueda; los demas datos salen de la primera repeticion.
    """
    correr = _buscador(esc, algoritmo, heuristica, tope_nodos)

    inicio = time.process_time()
    r = correr()
    repeticiones = 1
    while time.process_time() - inicio < tiempo_minimo_s:
        correr()
        repeticiones += 1
    tiempo = (time.process_time() - inicio) / repeticiones

    memoria: Optional[float] = None
    if con_memoria:
        tracemalloc.start()
        try:
            correr()
            memoria = tracemalloc.get_traced_memory()[1] / 1024
        finally:
            tracemalloc.stop()

    return Medicion(
        escenario=esc.nombre,
        servidores=len(esc.capacidades),
        vms=len(esc.tamanos),
        servidor_a_vaciar=esc.servidor_a_vaciar,
        algoritmo=algoritmo,
        heuristica=r.heuristica,
        estado=r.estado,
        costo=r.costo,
        costo_optimo=None,
        migraciones=None if r.plan is None else len(r.plan),
        nodos_expandidos=r.nodos_expandidos,
        estados_guardados=r.estados_guardados,
        iteraciones=r.iteraciones,
        tiempo_cpu_s=tiempo,
        memoria_pico_kb=memoria,
        tope_nodos=tope_nodos,
    )


def _costo_optimo(nombre: str, filas: Sequence[Medicion],
                  costos_optimos: Optional[Mapping[str, int]]) -> Optional[int]:
    """Costo optimo de un escenario; ValueError si dos fuentes no coinciden."""
    fuentes = []
    if costos_optimos is not None and nombre in costos_optimos:
        fuentes.append(("costos_optimos", costos_optimos[nombre]))
    for m in filas:
        if m.algoritmo in _OPTIMOS and m.estado == "resuelto":
            fuentes.append((f"{m.algoritmo}/{m.heuristica}", m.costo))
    if len({costo for _, costo in fuentes}) > 1:
        raise ValueError(f"costos optimos distintos en {nombre!r}: {fuentes}")
    return fuentes[0][1] if fuentes else None


def correr_lote(escenarios: Sequence[Escenario], configuraciones: Sequence[tuple[str, str]],
                tope_nodos: int, con_memoria: bool = False,
                costos_optimos: Optional[Mapping[str, int]] = None,
                tiempo_minimo_s: float = 0.2) -> list[Medicion]:
    mediciones = []
    for esc in escenarios:
        filas = [medir(esc, algoritmo, heuristica, tope_nodos, con_memoria, tiempo_minimo_s)
                 for algoritmo, heuristica in configuraciones]
        optimo = _costo_optimo(esc.nombre, filas, costos_optimos)
        mediciones.extend(replace(m, costo_optimo=optimo) for m in filas)
    return mediciones


def escribir_csv(mediciones: Sequence[Medicion], ruta: "Path | str") -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo, lineterminator="\n")
        escritor.writerow(COLUMNAS_MEDICION)
        for m in mediciones:
            escritor.writerow("" if getattr(m, c) is None else getattr(m, c)
                              for c in COLUMNAS_MEDICION)


def _leer_csv(ruta: "Path | str") -> list[Medicion]:
    """Lee un CSV escrito por escribir_csv; las celdas vacias vuelven a None."""
    def convertir(columna: str, valor: str):
        if valor == "":
            return None
        if columna in _COLUMNAS_FLOAT:
            return float(valor)
        if columna in _COLUMNAS_TEXTO:
            return valor
        return int(valor)

    with open(ruta, encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        if tuple(lector.fieldnames or ()) != COLUMNAS_MEDICION:
            raise ValueError(f"{ruta}: columnas distintas de COLUMNAS_MEDICION")
        return [Medicion(**{c: convertir(c, fila[c]) for c in COLUMNAS_MEDICION})
                for fila in lector]


def resumen_por_algoritmo(mediciones: Sequence[Medicion]) -> list[dict]:
    grupos: dict[tuple[str, str], list[Medicion]] = {}
    for m in mediciones:
        grupos.setdefault((m.algoritmo, m.heuristica), []).append(m)
    filas = []
    for (algoritmo, heuristica), grupo in grupos.items():
        resueltos = [m for m in grupo if m.estado == "resuelto"]
        nodos = [m.nodos_expandidos for m in resueltos]
        memoria = [m.memoria_pico_kb for m in grupo if m.memoria_pico_kb is not None]
        filas.append({
            "algoritmo": algoritmo,
            "heuristica": heuristica,
            "casos": len(grupo),
            "resueltos": len(resueltos),
            "nodos_mediana": statistics.median(nodos) if nodos else None,
            "nodos_max": max(nodos) if nodos else None,
            "tiempo_mediana_s": (statistics.median(m.tiempo_cpu_s for m in resueltos)
                                 if resueltos else None),
            "estados_guardados_max": max(m.estados_guardados for m in grupo),
            "memoria_pico_max_kb": max(memoria) if memoria else None,
            "casos_con_memoria": len(memoria),
        })
    return filas
