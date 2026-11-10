import csv
import random
from dataclasses import replace
from pathlib import Path
from typing import Iterator, NamedTuple, Optional

from buscadores import buscar
from heuristicas import h1
from modelo import (
    Escenario,
    EscenarioInvalido,
    cargas,
    con_servidor_a_vaciar,
    validar_escenario,
)

COLUMNAS_SERVIDORES = ("servidor", "capacidad")
COLUMNAS_VMS = ("vm", "tamano", "servidor")
COLUMNAS_METAS = ("servidor_a_vaciar", "h1_inicial", "costo_optimo")

_ALGORITMOS_OPTIMOS = ("astar", "ida", "ucs")


class _Meta(NamedTuple):
    """Un escenario no trivial generado, con los datos de su fila en metas.csv."""
    semilla: int
    escenario: Escenario
    h1_inicial: int
    costo_optimo: int


# --- CSV ---

def _escribir_tabla(ruta: Path, columnas: tuple[str, ...], filas) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo, lineterminator="\n")
        escritor.writerow(columnas)
        escritor.writerows(filas)


def _leer_tabla(ruta: Path, columnas: tuple[str, ...]) -> list[tuple[int, ...]]:
    """Lee un CSV de enteros con encabezado exacto; lanza EscenarioInvalido si no cuadra."""
    with open(ruta, encoding="utf-8", newline="") as archivo:
        lector = csv.reader(archivo)
        encabezado = next(lector, None)
        if encabezado is None or tuple(encabezado) != columnas:
            raise EscenarioInvalido(f"{ruta.name}: se esperaban las columnas {columnas}, "
                                    f"se leyo {encabezado}")
        filas = []
        for numero, fila in enumerate(lector, start=2):
            if not fila:
                continue
            if len(fila) != len(columnas):
                raise EscenarioInvalido(f"{ruta.name}, linea {numero}: se esperaban "
                                        f"{len(columnas)} valores, hay {len(fila)}")
            try:
                filas.append(tuple(int(valor) for valor in fila))
            except ValueError:
                raise EscenarioInvalido(f"{ruta.name}, linea {numero}: valor no entero "
                                        f"en {fila}") from None
    return filas


def _ordenar_por_indice(ruta: Path, filas: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    """Ordena por la primera columna y exige indices 0..n-1 sin huecos ni repetidos."""
    ordenadas = sorted(filas)
    indices = [fila[0] for fila in ordenadas]
    if indices != list(range(len(ordenadas))):
        raise EscenarioInvalido(f"{ruta.name}: los indices deben ser 0..{len(ordenadas) - 1} "
                                f"sin huecos ni repetidos, se leyo {sorted(indices)}")
    return ordenadas


def guardar_escenario(esc: Escenario, directorio: "Path | str") -> None:
    carpeta = Path(directorio)
    carpeta.mkdir(parents=True, exist_ok=True)
    _escribir_tabla(carpeta / "servidores.csv", COLUMNAS_SERVIDORES,
                    enumerate(esc.capacidades))
    _escribir_tabla(carpeta / "vms.csv", COLUMNAS_VMS,
                    ((vm, tam, servidor)
                     for vm, (tam, servidor) in enumerate(zip(esc.tamanos, esc.inicial))))


def cargar_escenario(directorio: "Path | str", servidor_a_vaciar: int) -> Escenario:
    carpeta = Path(directorio)
    ruta_servidores = carpeta / "servidores.csv"
    ruta_vms = carpeta / "vms.csv"
    servidores = _ordenar_por_indice(ruta_servidores,
                                     _leer_tabla(ruta_servidores, COLUMNAS_SERVIDORES))
    vms = _ordenar_por_indice(ruta_vms, _leer_tabla(ruta_vms, COLUMNAS_VMS))
    esc = Escenario(
        capacidades=tuple(capacidad for _, capacidad in servidores),
        tamanos=tuple(tam for _, tam, _ in vms),
        inicial=tuple(servidor for _, _, servidor in vms),
        servidor_a_vaciar=servidor_a_vaciar,
        nombre=f"{carpeta.name}_x{servidor_a_vaciar}",
    )
    validar_escenario(esc)
    return esc


def _guardar_metas(directorio: "Path | str", filas: list[tuple[int, int, int]]) -> None:
    """Escribe metas.csv: una fila (servidor_a_vaciar, h1_inicial, costo_optimo) por X."""
    _escribir_tabla(Path(directorio) / "metas.csv", COLUMNAS_METAS, sorted(filas))


def leer_metas(directorio: "Path | str") -> list[tuple[int, int, int]]:
    """Filas de metas.csv (servidor_a_vaciar, h1_inicial, costo_optimo), ordenadas.

    Devuelve una lista vacia si el archivo no existe.
    """
    ruta = Path(directorio) / "metas.csv"
    if not ruta.exists():
        return []
    return sorted(_leer_tabla(ruta, COLUMNAS_METAS))


# --- Generador ---

def generar_cluster(semilla: int, n_servidores: int, n_vms: int, factor: float = 1.03,
                    servidor_a_vaciar: int = 0, ocupados: tuple[int, ...] = (0,),
                    max_intentos: int = 4000) -> Optional[Escenario]:
    if n_servidores < 2:
        raise EscenarioInvalido(f"se necesitan al menos 2 servidores, se pidieron {n_servidores}")
    if n_vms < 1:
        raise EscenarioInvalido(f"se necesita al menos 1 VM, se pidieron {n_vms}")
    if not 0 <= servidor_a_vaciar < n_servidores:
        raise EscenarioInvalido(f"servidor a vaciar {servidor_a_vaciar} fuera de "
                                f"0..{n_servidores - 1}")
    fuera = [j for j in ocupados if not 0 <= j < n_servidores]
    if fuera:
        raise EscenarioInvalido(f"servidores ocupados fuera de 0..{n_servidores - 1}: {fuera}")
    rnd = random.Random(semilla)
    tamanos = tuple(rnd.randint(1, 4) for _ in range(n_vms))
    capacidad = int(sum(tamanos) / (n_servidores - 1) * factor) + 1
    capacidades = (capacidad,) * n_servidores
    for _ in range(max_intentos):
        inicial = tuple(rnd.randrange(n_servidores) for _ in range(n_vms))
        esc = Escenario(capacidades, tamanos, inicial, servidor_a_vaciar)
        carga = cargas(esc, inicial)
        if max(carga) <= capacidad and all(carga[j] > 0 for j in ocupados):
            validar_escenario(esc)
            return esc
    return None


def _clasificar(esc: Escenario, tope_nodos: int,
                algoritmo: str) -> tuple[Optional[bool], Optional[int]]:
    """(no trivial, costo optimo); (None, None) si llego al tope o no hay solucion."""
    if algoritmo not in _ALGORITMOS_OPTIMOS:
        raise ValueError(f"algoritmo no optimo o desconocido: {algoritmo!r}; "
                         f"use uno de {_ALGORITMOS_OPTIMOS}")
    r = buscar(esc, algoritmo, "h2", tope_nodos)
    if r.estado != "resuelto":
        return None, None
    return r.costo > h1(esc, esc.inicial), r.costo


def es_no_trivial(esc: Escenario, tope_nodos: int, algoritmo: str = "astar") -> Optional[bool]:
    return _clasificar(esc, tope_nodos, algoritmo)[0]


def _generar_con_metas(n_servidores: int, n_vms: int, cantidad: int, tope_nodos: int,
                       semilla_inicial: int = 0, factor: float = 1.03,
                       servidores_a_vaciar: tuple[int, ...] = (0, 1, 2),
                       algoritmo: str = "ida") -> Iterator[_Meta]:
    """Genera en orden los escenarios no triviales, con h1 inicial y costo optimo.

    Recorre semillas sin limite: con parametros en que nunca aparece un caso no trivial
    (por ejemplo, 2 servidores) no termina.
    """
    encontrados = 0
    semilla = semilla_inicial
    while encontrados < cantidad:
        base = generar_cluster(semilla, n_servidores, n_vms, factor)
        if base is not None:
            for x in servidores_a_vaciar:
                esc = replace(con_servidor_a_vaciar(base, x),
                              nombre=f"{n_servidores}x{n_vms}_s{semilla}_x{x}")
                no_trivial, costo = _clasificar(esc, tope_nodos, algoritmo)
                if no_trivial:
                    yield _Meta(semilla, esc, h1(esc, esc.inicial), costo)
                    encontrados += 1
                    if encontrados == cantidad:
                        return
        semilla += 1


def generar_no_triviales(n_servidores: int, n_vms: int, cantidad: int, tope_nodos: int,
                         semilla_inicial: int = 0, factor: float = 1.03,
                         servidores_a_vaciar: tuple[int, ...] = (0, 1, 2),
                         algoritmo: str = "ida") -> list[Escenario]:
    return [meta.escenario for meta in _generar_con_metas(
        n_servidores, n_vms, cantidad, tope_nodos, semilla_inicial, factor,
        servidores_a_vaciar, algoritmo)]
