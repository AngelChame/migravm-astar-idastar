"""Utilidades de las pruebas: copia provisional del generador y enumeracion del espacio."""
import heapq
import random
from collections import deque
from itertools import count
from typing import Optional

from modelo import Escenario, Estado, cargas, es_meta, sucesores


def _generar_cluster_provisional(semilla: int, n_servidores: int, n_vms: int,
                                 factor: float = 1.03, servidor_a_vaciar: int = 0,
                                 ocupados: tuple[int, ...] = (0,),
                                 max_intentos: int = 4000) -> Optional[Escenario]:
    """Copia provisional del generador de ARQUITECTURA.md seccion 4 (modulo 4).

    Se reemplaza por escenarios.generar_cluster cuando exista el modulo 4.
    """
    rnd = random.Random(semilla)
    tamanos = tuple(rnd.randint(1, 4) for _ in range(n_vms))
    capacidad = int(sum(tamanos) / (n_servidores - 1) * factor) + 1
    capacidades = (capacidad,) * n_servidores
    for _ in range(max_intentos):
        inicial = tuple(rnd.randrange(n_servidores) for _ in range(n_vms))
        esc = Escenario(capacidades, tamanos, inicial, servidor_a_vaciar)
        carga = cargas(esc, inicial)
        if max(carga) <= capacidad and all(carga[j] > 0 for j in ocupados):
            return esc
    return None


def espacio_completo(esc: Escenario) -> tuple[set[Estado], list[tuple[Estado, Estado, int]]]:
    """Busqueda en anchura desde el estado inicial sin expandir estados meta."""
    vistos = {esc.inicial}
    cola = deque([esc.inicial])
    aristas = []
    while cola:
        estado = cola.popleft()
        if es_meta(esc, estado):
            continue
        for suc in sucesores(esc, estado):
            aristas.append((estado, suc.estado, suc.costo))
            if suc.estado not in vistos:
                vistos.add(suc.estado)
                cola.append(suc.estado)
    return vistos, aristas


def costos_optimos(esc: Escenario, vistos: set[Estado],
                   aristas: list[tuple[Estado, Estado, int]]) -> dict[Estado, int]:
    """h* por Dijkstra sobre el grafo invertido desde los estados meta."""
    invertido: dict[Estado, list[tuple[Estado, int]]] = {}
    for a, b, c in aristas:
        invertido.setdefault(b, []).append((a, c))
    contador = count()
    hs = {s: 0 for s in vistos if es_meta(esc, s)}
    frontera = [(0, next(contador), s) for s in hs]
    heapq.heapify(frontera)
    while frontera:
        g, _, estado = heapq.heappop(frontera)
        if g > hs[estado]:
            continue
        for previo, c in invertido.get(estado, []):
            if previo not in hs or g + c < hs[previo]:
                hs[previo] = g + c
                heapq.heappush(frontera, (g + c, next(contador), previo))
    return hs
