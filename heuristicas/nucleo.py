from typing import Callable

from modelo import Escenario, Estado, cargas

Heuristica = Callable[[Escenario, Estado], int]


def h0(esc: Escenario, estado: Estado) -> int:
    """Heuristica nula: costo uniforme."""
    return 0


def h1(esc: Escenario, estado: Estado) -> int:
    """Suma de los tamanos de las VM que siguen en el servidor a vaciar."""
    x = esc.servidor_a_vaciar
    return sum(tam for tam, servidor in zip(esc.tamanos, estado) if servidor == x)


def h2(esc: Escenario, estado: Estado) -> int:
    """h1 mas el menor tamano de VM si alguna VM de X no cabe en ningun otro servidor."""
    base = h1(esc, estado)
    if base == 0:
        return 0
    x = esc.servidor_a_vaciar
    carga = cargas(esc, estado)
    libre_max = max(
        cap - c for j, (cap, c) in enumerate(zip(esc.capacidades, carga)) if j != x
    )
    atorada = any(
        servidor == x and tam > libre_max for tam, servidor in zip(esc.tamanos, estado)
    )
    return base + min(esc.tamanos) if atorada else base


HEURISTICAS: dict[str, Heuristica] = {"h0": h0, "h1": h1, "h2": h2}
