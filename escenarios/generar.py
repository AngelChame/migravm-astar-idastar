"""Linea de comandos del generador de escenarios no triviales.

Ejemplo:
    python -m escenarios.generar --servidores 8 --vms 24 --cantidad 30 --tope 150000 \
        --algoritmo ida --salida escenarios/datos
"""
import argparse
import time
from pathlib import Path
from typing import Optional, Sequence

from escenarios.nucleo import _generar_con_metas, _guardar_metas, guardar_escenario
from modelo import Escenario


def main(argumentos: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m escenarios.generar",
        description="Genera escenarios no triviales y los guarda como CSV, una carpeta "
                    "{H}x{V}_s{semilla} por cluster.")
    parser.add_argument("--servidores", type=int, required=True)
    parser.add_argument("--vms", type=int, required=True)
    parser.add_argument("--cantidad", type=int, required=True)
    parser.add_argument("--tope", type=int, required=True, help="tope de nodos por busqueda")
    parser.add_argument("--algoritmo", default="ida", choices=("ida", "astar", "ucs"))
    parser.add_argument("--semilla-inicial", type=int, default=0)
    parser.add_argument("--factor", type=float, default=1.03)
    parser.add_argument("--servidores-a-vaciar", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--salida", type=Path, default=Path("escenarios") / "datos")
    args = parser.parse_args(argumentos)

    inicio = time.perf_counter()
    por_semilla: dict[int, list[tuple[int, int, int]]] = {}
    clusteres: dict[int, Escenario] = {}
    for meta in _generar_con_metas(args.servidores, args.vms, args.cantidad, args.tope,
                                   args.semilla_inicial, args.factor,
                                   tuple(args.servidores_a_vaciar), args.algoritmo):
        clusteres.setdefault(meta.semilla, meta.escenario)
        por_semilla.setdefault(meta.semilla, []).append(
            (meta.escenario.servidor_a_vaciar, meta.h1_inicial, meta.costo_optimo))

    for semilla, filas in por_semilla.items():
        carpeta = args.salida / f"{args.servidores}x{args.vms}_s{semilla}"
        guardar_escenario(clusteres[semilla], carpeta)
        _guardar_metas(carpeta, filas)

    total = sum(len(filas) for filas in por_semilla.values())
    print(f"{args.servidores}x{args.vms}: {total} escenarios no triviales en "
          f"{len(por_semilla)} clusteres, guardados en {args.salida} "
          f"({args.algoritmo}, tope {args.tope}, {time.perf_counter() - inicio:.1f} s)")


if __name__ == "__main__":
    main()
