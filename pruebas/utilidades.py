"""Utilidades de las pruebas: enumeracion del espacio de estados y h* por Dijkstra."""
import heapq
from collections import deque
from itertools import count

from modelo import Escenario, Estado, es_meta, sucesores


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
