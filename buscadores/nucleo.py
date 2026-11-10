import heapq
from dataclasses import dataclass
from itertools import count
from typing import Iterator, Literal, Optional

from heuristicas import HEURISTICAS, Heuristica, h0
from modelo import Accion, Escenario, Estado, Sucesor, es_meta, sucesores

EstadoBusqueda = Literal["resuelto", "sin_solucion", "tope"]


@dataclass(frozen=True)
class Resultado:
    algoritmo: str                      # "ucs", "voraz", "astar" o "ida"
    heuristica: str                     # "h0", "h1" o "h2"
    estado: EstadoBusqueda
    costo: Optional[int]                # None si no hay plan
    plan: Optional[tuple[Accion, ...]]  # None si no hay plan
    nodos_expandidos: int
    estados_guardados: int
    iteraciones: Optional[int] = None   # solo IDA*


Padres = dict[Estado, Optional[tuple[Estado, Accion]]]


def _reconstruir(padres: Padres, estado: Estado) -> tuple[Accion, ...]:
    """Recorre los padres desde un estado hasta el inicial y devuelve el plan en orden."""
    acciones = []
    enlace = padres[estado]
    while enlace is not None:
        previo, accion = enlace
        acciones.append(accion)
        enlace = padres[previo]
    return tuple(reversed(acciones))


def _sin_plan(algoritmo: str, heuristica: str, estado: EstadoBusqueda, expandidos: int,
              guardados: int, iteraciones: Optional[int] = None) -> Resultado:
    return Resultado(algoritmo, heuristica, estado, None, None, expandidos, guardados,
                     iteraciones)


def _mejor_primero_g(esc: Escenario, h: Heuristica, algoritmo: str, heuristica: str,
                     tope_nodos: Optional[int]) -> Resultado:
    """Costo uniforme y A*: clave (f, g, contador), mejor g por estado, sin conjunto cerrado."""
    contador = count()
    s0 = esc.inicial
    frontera = [(h(esc, s0), 0, next(contador), s0)]
    mejor_g = {s0: 0}
    padres: Padres = {s0: None}
    expandidos = 0
    while frontera:
        _, g, _, estado = heapq.heappop(frontera)
        if g > mejor_g[estado]:
            continue
        if es_meta(esc, estado):
            return Resultado(algoritmo, heuristica, "resuelto", g,
                             _reconstruir(padres, estado), expandidos, len(mejor_g))
        if tope_nodos is not None and expandidos == tope_nodos:
            return _sin_plan(algoritmo, heuristica, "tope", expandidos, len(mejor_g))
        expandidos += 1
        for suc in sucesores(esc, estado):
            g2 = g + suc.costo
            if g2 < mejor_g.get(suc.estado, g2 + 1):
                mejor_g[suc.estado] = g2
                padres[suc.estado] = (estado, suc.accion)
                heapq.heappush(frontera, (g2 + h(esc, suc.estado), g2, next(contador),
                                          suc.estado))
    return _sin_plan(algoritmo, heuristica, "sin_solucion", expandidos, len(mejor_g))


def costo_uniforme(esc: Escenario, tope_nodos: Optional[int] = None) -> Resultado:
    return _mejor_primero_g(esc, h0, "ucs", "h0", tope_nodos)


def a_estrella(esc: Escenario, h: Heuristica, tope_nodos: Optional[int] = None) -> Resultado:
    return _mejor_primero_g(esc, h, "astar", h.__name__, tope_nodos)


def voraz(esc: Escenario, h: Heuristica, tope_nodos: Optional[int] = None) -> Resultado:
    """Mejor primero con clave (h, contador); cada estado se inserta una sola vez."""
    nombre = h.__name__
    contador = count()
    s0 = esc.inicial
    frontera = [(h(esc, s0), next(contador), s0)]
    g_de = {s0: 0}
    padres: Padres = {s0: None}
    expandidos = 0
    while frontera:
        _, _, estado = heapq.heappop(frontera)
        if es_meta(esc, estado):
            return Resultado("voraz", nombre, "resuelto", g_de[estado],
                             _reconstruir(padres, estado), expandidos, len(g_de))
        if tope_nodos is not None and expandidos == tope_nodos:
            return _sin_plan("voraz", nombre, "tope", expandidos, len(g_de))
        expandidos += 1
        for suc in sucesores(esc, estado):
            if suc.estado in g_de:
                continue
            g_de[suc.estado] = g_de[estado] + suc.costo
            padres[suc.estado] = (estado, suc.accion)
            heapq.heappush(frontera, (h(esc, suc.estado), next(contador), suc.estado))
    return _sin_plan("voraz", nombre, "sin_solucion", expandidos, len(g_de))


def ida_estrella(esc: Escenario, h: Heuristica, tope_nodos: Optional[int] = None,
                 transposicion: bool = True) -> Resultado:
    """IDA* con recorrido en profundidad iterativo (pila explicita).

    Con transposicion, una tabla de mejor g por iteracion (anadido a las diapositivas);
    sin ella, se omiten los estados que ya estan en el camino actual.
    """
    nombre = h.__name__
    s0 = esc.inicial
    cota = h(esc, s0)
    expandidos = 0
    guardados = 0
    iteraciones = 0
    while True:
        iteraciones += 1
        siguiente: Optional[int] = None
        tabla: dict[Estado, int] = {}
        en_camino: set[Estado] = set()
        pila: list[tuple[Estado, int, Iterator[Sucesor]]] = []
        acciones: list[Accion] = []

        def entrar(estado: Estado, g: int):
            """Evalua un nodo: None si se poda o se expande, o el Resultado si termina."""
            nonlocal siguiente, expandidos, guardados
            f = g + h(esc, estado)
            if f > cota:
                if siguiente is None or f < siguiente:
                    siguiente = f
                return None
            if not transposicion:
                guardados = max(guardados, len(pila) + 1)
            if es_meta(esc, estado):
                return Resultado("ida", nombre, "resuelto", g, tuple(acciones), expandidos,
                                 max(guardados, len(tabla)) if transposicion else guardados,
                                 iteraciones)
            if tope_nodos is not None and expandidos == tope_nodos:
                return _sin_plan("ida", nombre, "tope", expandidos,
                                 max(guardados, len(tabla)) if transposicion else guardados,
                                 iteraciones)
            expandidos += 1
            pila.append((estado, g, iter(sucesores(esc, estado))))
            en_camino.add(estado)
            return None

        fin = entrar(s0, 0)
        if fin is not None:
            return fin
        while pila:
            estado, g, pendientes = pila[-1]
            suc = next(pendientes, None)
            if suc is None:
                pila.pop()
                en_camino.discard(estado)
                if acciones:
                    acciones.pop()
                continue
            g2 = g + suc.costo
            if transposicion:
                previo = tabla.get(suc.estado)
                if previo is not None and previo <= g2:
                    continue
                tabla[suc.estado] = g2
            elif suc.estado in en_camino:
                continue
            acciones.append(suc.accion)
            profundidad = len(pila)
            fin = entrar(suc.estado, g2)
            if fin is not None:
                return fin
            if len(pila) == profundidad:
                acciones.pop()
        if transposicion:
            guardados = max(guardados, len(tabla))
        if siguiente is None:
            return _sin_plan("ida", nombre, "sin_solucion", expandidos, guardados,
                             iteraciones)
        cota = siguiente


_ALGORITMOS = ("ucs", "voraz", "astar", "ida")


def buscar(esc: Escenario, algoritmo: str, heuristica: str = "h2",
           tope_nodos: Optional[int] = None) -> Resultado:
    if algoritmo not in _ALGORITMOS:
        raise ValueError(f"algoritmo desconocido: {algoritmo!r}")
    if algoritmo == "ucs":
        return costo_uniforme(esc, tope_nodos)
    if heuristica not in HEURISTICAS:
        raise ValueError(f"heuristica desconocida: {heuristica!r}")
    h = HEURISTICAS[heuristica]
    if algoritmo == "voraz":
        return voraz(esc, h, tope_nodos)
    if algoritmo == "astar":
        return a_estrella(esc, h, tope_nodos)
    return ida_estrella(esc, h, tope_nodos, transposicion=True)
