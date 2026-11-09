from dataclasses import dataclass, replace
from typing import NamedTuple, Sequence

Estado = tuple[int, ...]  # Estado[i] = servidor que aloja la VM i


class Accion(NamedTuple):
    vm: int
    origen: int
    destino: int


class Sucesor(NamedTuple):
    accion: Accion
    estado: Estado
    costo: int


@dataclass(frozen=True)
class Escenario:
    capacidades: tuple[int, ...]  # largo H, GB
    tamanos: tuple[int, ...]      # largo V, GB, cada uno >= 1
    inicial: Estado               # largo V, valores en 0..H-1
    servidor_a_vaciar: int        # X, en 0..H-1
    nombre: str = ""


class EscenarioInvalido(ValueError):
    """Datos inconsistentes al construir un Escenario."""


class PlanInvalido(ValueError):
    """Un plan viola una regla del problema."""


def validar_escenario(esc: Escenario) -> None:
    h = len(esc.capacidades)
    if h < 2:
        raise EscenarioInvalido(f"se necesitan al menos 2 servidores, hay {h}")
    for j, cap in enumerate(esc.capacidades):
        if cap < 1:
            raise EscenarioInvalido(f"la capacidad del servidor {j} es {cap}, debe ser >= 1")
    for i, tam in enumerate(esc.tamanos):
        if tam < 1:
            raise EscenarioInvalido(f"el tamano de la VM {i} es {tam}, debe ser >= 1")
    if len(esc.inicial) != len(esc.tamanos):
        raise EscenarioInvalido(
            f"el estado inicial tiene {len(esc.inicial)} VM y hay {len(esc.tamanos)} tamanos"
        )
    for i, j in enumerate(esc.inicial):
        if not 0 <= j < h:
            raise EscenarioInvalido(f"la VM {i} esta en el servidor {j}, fuera de 0..{h - 1}")
    if not 0 <= esc.servidor_a_vaciar < h:
        raise EscenarioInvalido(
            f"el servidor a vaciar {esc.servidor_a_vaciar} esta fuera de 0..{h - 1}"
        )
    for j, (carga, cap) in enumerate(zip(cargas(esc, esc.inicial), esc.capacidades)):
        if carga > cap:
            raise EscenarioInvalido(
                f"el servidor {j} tiene carga {carga} y capacidad {cap} en el estado inicial"
            )


def cargas(esc: Escenario, estado: Estado) -> tuple[int, ...]:
    totales = [0] * len(esc.capacidades)
    for vm, servidor in enumerate(estado):
        totales[servidor] += esc.tamanos[vm]
    return tuple(totales)


def es_meta(esc: Escenario, estado: Estado) -> bool:
    return esc.servidor_a_vaciar not in estado


def costo_accion(esc: Escenario, accion: Accion) -> int:
    return esc.tamanos[accion.vm]


def _motivo_invalida(esc: Escenario, accion: Accion, carga_destino: int) -> str | None:
    if accion.destino == accion.origen:
        return f"la VM {accion.vm} ya esta en el servidor {accion.destino}"
    if accion.destino == esc.servidor_a_vaciar:
        return f"no se puede migrar hacia el servidor a vaciar {accion.destino}"
    if carga_destino + esc.tamanos[accion.vm] > esc.capacidades[accion.destino]:
        return (
            f"la VM {accion.vm} ({esc.tamanos[accion.vm]} GB) no cabe en el servidor "
            f"{accion.destino} (carga {carga_destino}, capacidad {esc.capacidades[accion.destino]})"
        )
    return None


def aplicar(esc: Escenario, estado: Estado, accion: Accion) -> Estado:
    if not 0 <= accion.vm < len(estado):
        raise ValueError(f"la VM {accion.vm} no existe")
    if not 0 <= accion.destino < len(esc.capacidades):
        raise ValueError(f"el servidor {accion.destino} no existe")
    if accion.origen != estado[accion.vm]:
        raise ValueError(
            f"la VM {accion.vm} esta en el servidor {estado[accion.vm]}, no en {accion.origen}"
        )
    motivo = _motivo_invalida(esc, accion, cargas(esc, estado)[accion.destino])
    if motivo:
        raise ValueError(motivo)
    nuevo = list(estado)
    nuevo[accion.vm] = accion.destino
    return tuple(nuevo)


def sucesores(esc: Escenario, estado: Estado) -> list[Sucesor]:
    actuales = cargas(esc, estado)
    resultado = []
    for vm, origen in enumerate(estado):
        for destino in range(len(esc.capacidades)):
            accion = Accion(vm, origen, destino)
            if _motivo_invalida(esc, accion, actuales[destino]) is None:
                nuevo = estado[:vm] + (destino,) + estado[vm + 1:]
                resultado.append(Sucesor(accion, nuevo, esc.tamanos[vm]))
    return resultado


def validar_plan(esc: Escenario, plan: Sequence[Accion]) -> int:
    estado = esc.inicial
    total = 0
    for paso, accion in enumerate(plan, start=1):
        try:
            estado = aplicar(esc, estado, accion)
        except ValueError as error:
            raise PlanInvalido(f"paso {paso}, {tuple(accion)}: {error}") from error
        total += costo_accion(esc, accion)
    if not es_meta(esc, estado):
        raise PlanInvalido(
            f"el plan termina con VM en el servidor a vaciar {esc.servidor_a_vaciar}"
        )
    return total


def con_servidor_a_vaciar(esc: Escenario, servidor: int) -> Escenario:
    if not 0 <= servidor < len(esc.capacidades):
        raise EscenarioInvalido(
            f"el servidor a vaciar {servidor} esta fuera de 0..{len(esc.capacidades) - 1}"
        )
    return replace(esc, servidor_a_vaciar=servidor)
