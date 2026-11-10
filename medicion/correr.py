"""Linea de comandos de la medicion por lotes de los cinco tamanos.

Ejemplo:
    python -m medicion.correr --tamanos 4x7 5x10 --tope 150000

Escribe medicion/resultados/mediciones_{H}x{V}.csv al terminar cada tamano y rehace
medicion/resultados/resumen.csv con todos los tamanos que haya en la carpeta.
"""
import argparse
import csv
import time
from pathlib import Path
from typing import Optional, Sequence

from escenarios import cargar_escenario, leer_metas
from medicion.nucleo import Medicion, _leer_csv, correr_lote, escribir_csv, resumen_por_algoritmo
from modelo import Escenario

# (algoritmo, heuristica, con pasada de memoria) por tamano. UCS no corre en 8x24 ni en
# 10x32 (no resuelve dentro del tope); la pasada de memoria de A* en 10x32 no se mide.
_TODAS = [("ucs", "h0"), ("voraz", "h2"), ("astar", "h1"), ("astar", "h2"), ("ida", "h2"),
          ("ida_sin_tabla", "h2")]
CONFIGURACIONES: dict[str, list[tuple[str, str, bool]]] = {
    "4x7": [(a, h, True) for a, h in _TODAS],
    "5x10": [(a, h, True) for a, h in _TODAS],
    "6x16": [(a, h, a != "ucs") for a, h in _TODAS],
    "8x24": [("voraz", "h2", True), ("astar", "h1", False), ("astar", "h2", True),
             ("ida", "h2", True), ("ida_sin_tabla", "h2", False)],
    "10x32": [("voraz", "h2", True), ("astar", "h1", False), ("astar", "h2", False),
              ("ida", "h2", True), ("ida_sin_tabla", "h2", False)],
}
COLUMNAS_RESUMEN = (
    "servidores", "vms", "tope_nodos", "algoritmo", "heuristica", "casos", "resueltos",
    "nodos_mediana", "nodos_max", "tiempo_mediana_s", "estados_guardados_max",
    "memoria_pico_max_kb", "casos_con_memoria",
)


def cargar_tamano(datos: Path, tamano: str) -> tuple[list[Escenario], dict[str, int]]:
    """Escenarios de un tamano (una fila de metas.csv por escenario) y su costo optimo."""
    escenarios, optimos = [], {}
    carpetas = sorted(datos.glob(f"{tamano}_s*"), key=lambda c: int(c.name.split("_s")[1]))
    for carpeta in carpetas:
        for x, _, costo in leer_metas(carpeta):
            esc = cargar_escenario(carpeta, x)
            escenarios.append(esc)
            optimos[esc.nombre] = costo
    return escenarios, optimos


def medir_tamano(tamano: str, escenarios: Sequence[Escenario], optimos: dict[str, int],
                 tope_nodos: int, tiempo_minimo_s: float) -> list[Medicion]:
    """Corre las configuraciones del tamano; las filas quedan por escenario y configuracion."""
    configs = CONFIGURACIONES[tamano]
    filas: dict[tuple[str, str, str], Medicion] = {}
    for con_memoria in (True, False):
        elegidas = [(a, h) for a, h, m in configs if m == con_memoria]
        if elegidas:
            for m in correr_lote(escenarios, elegidas, tope_nodos, con_memoria, optimos,
                                 tiempo_minimo_s):
                filas[(m.escenario, m.algoritmo, m.heuristica)] = m
    return [filas[(esc.nombre, a, h)] for esc in escenarios for a, h, _ in configs]


def escribir_resumen(salida: Path) -> list[dict]:
    """Rehace resumen.csv con los mediciones_*.csv de la carpeta, por tamano."""
    filas = []
    for tamano in CONFIGURACIONES:
        ruta = salida / f"mediciones_{tamano}.csv"
        if not ruta.exists():
            continue
        mediciones = _leer_csv(ruta)
        if not mediciones:
            continue
        for fila in resumen_por_algoritmo(mediciones):
            filas.append({"servidores": mediciones[0].servidores, "vms": mediciones[0].vms,
                          "tope_nodos": mediciones[0].tope_nodos, **fila})
    with open(salida / "resumen.csv", "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, COLUMNAS_RESUMEN, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows({k: ("" if v is None else v) for k, v in f.items()} for f in filas)
    return filas


def _celda(valor) -> str:
    if valor is None:
        return "-"
    if isinstance(valor, float):
        return f"{valor:.4g}"
    return str(valor)


def main(argumentos: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m medicion.correr",
                                     description="Mide los algoritmos sobre escenarios/datos.")
    parser.add_argument("--tamanos", nargs="+", default=list(CONFIGURACIONES),
                        choices=list(CONFIGURACIONES))
    parser.add_argument("--tope", type=int, default=150_000, help="tope de nodos por busqueda")
    parser.add_argument("--tiempo-minimo", type=float, default=0.2,
                        help="segundos de CPU a acumular por medicion de tiempo")
    parser.add_argument("--datos", type=Path, default=Path("escenarios") / "datos")
    parser.add_argument("--salida", type=Path, default=Path("medicion") / "resultados")
    args = parser.parse_args(argumentos)

    args.salida.mkdir(parents=True, exist_ok=True)
    for tamano in args.tamanos:
        inicio = time.perf_counter()
        escenarios, optimos = cargar_tamano(args.datos, tamano)
        mediciones = medir_tamano(tamano, escenarios, optimos, args.tope, args.tiempo_minimo)
        escribir_csv(mediciones, args.salida / f"mediciones_{tamano}.csv")
        print(f"{tamano}: {len(mediciones)} filas ({len(escenarios)} escenarios) en "
              f"{time.perf_counter() - inicio:.1f} s", flush=True)

    filas = escribir_resumen(args.salida)
    print()
    print(" | ".join(COLUMNAS_RESUMEN))
    for fila in filas:
        print(" | ".join(_celda(fila[c]) for c in COLUMNAS_RESUMEN))


if __name__ == "__main__":
    main()
