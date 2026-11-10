"""Genera reporte/tablas_resultados.md a partir de los CSV de medicion/resultados/.

Uso, desde la raiz del repositorio:

    python -m reporte.generar_tablas

Solo usa la biblioteca estandar y solo lee los CSV versionados (mediciones_*.csv y
resumen.csv); toda cifra de las tablas sale de ahi.
"""
import argparse
import csv
from pathlib import Path
from typing import Optional, Sequence

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "medicion" / "resultados"
SALIDA = RAIZ / "reporte" / "tablas_resultados.md"
SIN_DATO = "–"


# --- Lectura ---

def _numero(texto: str):
    if texto == "":
        return None
    for convertir in (int, float):
        try:
            return convertir(texto)
        except ValueError:
            pass
    return texto


def leer_csv(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8", newline="") as archivo:
        return [{k: _numero(v) for k, v in fila.items()} for fila in csv.DictReader(archivo)]


def leer_resultados(directorio: Path) -> tuple[list[dict], list[dict]]:
    resumen = leer_csv(directorio / "resumen.csv")
    mediciones = []
    for ruta in sorted(directorio.glob("mediciones_*.csv")):
        mediciones.extend(leer_csv(ruta))
    return resumen, mediciones


# --- Formato ---

def entero(valor) -> str:
    return SIN_DATO if valor is None else str(int(round(valor)))


def mediana(valor) -> str:
    """Medianas: enteras sin decimales; las de numero par de casos, con .5."""
    if valor is None:
        return SIN_DATO
    return str(int(valor)) if float(valor).is_integer() else f"{valor:g}"


def cifras(valor, significativas: int = 4) -> str:
    """Redondeo a cifras significativas (tiempo y memoria)."""
    if valor is None:
        return SIN_DATO
    texto = f"{valor:.{significativas}g}"
    if "e" in texto:
        return str(int(float(texto)))
    return texto


def razon(a, b) -> str:
    if a is None or b is None or b == 0:
        return SIN_DATO
    return f"{a / b:.2f}"


def tamano(fila: dict) -> str:
    return f"{fila['servidores']}x{fila['vms']}"


def tabla_md(encabezados: Sequence[str], filas: Sequence[Sequence[str]]) -> list[str]:
    lineas = ["| " + " | ".join(encabezados) + " |",
              "| " + " | ".join("---" for _ in encabezados) + " |"]
    lineas += ["| " + " | ".join(fila) + " |" for fila in filas]
    return lineas


def _buscar(resumen: list[dict], t: str, algoritmo: str, heuristica: str) -> Optional[dict]:
    for fila in resumen:
        if tamano(fila) == t and (fila["algoritmo"], fila["heuristica"]) == (algoritmo, heuristica):
            return fila
    return None


def _tamanos(resumen: list[dict]) -> list[str]:
    vistos = []
    for fila in sorted(resumen, key=lambda f: (f["servidores"], f["vms"])):
        if tamano(fila) not in vistos:
            vistos.append(tamano(fila))
    return vistos


# --- Secciones ---

def seccion_comparativa(resumen: list[dict]) -> list[str]:
    lineas = ["## a) Tabla comparativa por tamaño", ""]
    for t in _tamanos(resumen):
        filas = [f for f in resumen if tamano(f) == t]
        lineas += [f"### {t} (tope {filas[0]['tope_nodos']} nodos)", ""]
        lineas += tabla_md(
            ["Algoritmo", "Heurística", "Resueltos / casos", "Nodos (mediana / máx.)",
             "Tiempo mediano (s)", "Estados guardados máx.", "Memoria pico máx. (KB)"],
            [[f["algoritmo"], f["heuristica"], f"{f['resueltos']} / {f['casos']}",
              f"{mediana(f['nodos_mediana'])} / {entero(f['nodos_max'])}",
              cifras(f["tiempo_mediana_s"]), entero(f["estados_guardados_max"]),
              cifras(f["memoria_pico_max_kb"])] for f in filas])
        lineas.append("")
    return lineas


def seccion_topes(mediciones: list[dict]) -> list[str]:
    lineas = ["## b) Casos que llegaron al tope", ""]
    topes = [m for m in mediciones if m["estado"] == "tope"]
    if not topes:
        return lineas + ["Ningún caso llegó al tope.", ""]
    conteo: dict[tuple, list[str]] = {}
    for m in sorted(topes, key=lambda m: (m["servidores"], m["vms"], m["algoritmo"],
                                          m["heuristica"], m["escenario"])):
        clave = (tamano(m), m["algoritmo"], m["heuristica"], m["tope_nodos"])
        conteo.setdefault(clave, []).append(m["escenario"])
    casos = {}
    for m in mediciones:
        clave = (tamano(m), m["algoritmo"], m["heuristica"])
        casos[clave] = casos.get(clave, 0) + 1
    lineas += tabla_md(
        ["Tamaño", "Algoritmo", "Heurística", "Topes / casos", "Tope (nodos)", "Escenarios"],
        [[t, a, h, f"{len(nombres)} / {casos[(t, a, h)]}", str(tope), ", ".join(nombres)]
         for (t, a, h, tope), nombres in conteo.items()])
    return lineas + [""]


def seccion_memoria(resumen: list[dict]) -> list[str]:
    lineas = ["## c) Memoria: A* con h2 contra IDA* con h2 (con tabla)", ""]
    filas = []
    for t in ("8x24", "10x32"):
        a = _buscar(resumen, t, "astar", "h2")
        i = _buscar(resumen, t, "ida", "h2")
        if a is None or i is None:
            continue
        filas.append([t, "Estados guardados máx.", entero(a["estados_guardados_max"]),
                      entero(i["estados_guardados_max"]),
                      razon(a["estados_guardados_max"], i["estados_guardados_max"])])
        if t == "8x24":
            filas.append([t, "Memoria pico máx. (KB)", cifras(a["memoria_pico_max_kb"]),
                          cifras(i["memoria_pico_max_kb"]),
                          razon(a["memoria_pico_max_kb"], i["memoria_pico_max_kb"])])
    lineas += tabla_md(["Tamaño", "Medida", "A* h2", "IDA* h2", "Razón A* / IDA*"], filas)
    return lineas + [""]


def seccion_nodos(resumen: list[dict]) -> list[str]:
    lineas = ["## d) Razón entre medianas de nodos expandidos", ""]
    filas = []
    for t in _tamanos(resumen):
        a1 = _buscar(resumen, t, "astar", "h1")
        a2 = _buscar(resumen, t, "astar", "h2")
        i2 = _buscar(resumen, t, "ida", "h2")
        if a1 is None or a2 is None or i2 is None:
            continue
        m1, m2, mi = a1["nodos_mediana"], a2["nodos_mediana"], i2["nodos_mediana"]
        filas.append([t, mediana(m1), mediana(m2), mediana(mi), razon(m1, m2), razon(m2, mi),
                      razon(m1, mi),
                      f"{a1['resueltos']} / {a2['resueltos']} / {i2['resueltos']}"])
    lineas += tabla_md(["Tamaño", "A* h1", "A* h2", "IDA* h2", "A* h1 / A* h2",
                        "A* h2 / IDA* h2", "A* h1 / IDA* h2",
                        "Resueltos (A* h1 / A* h2 / IDA* h2)"], filas)
    lineas += ["", "Medianas sobre los casos resueltos de cada configuración.", ""]
    return lineas


def generar(directorio: Path = RESULTADOS) -> str:
    resumen, mediciones = leer_resultados(directorio)
    lineas = ["# Tablas de resultados", "",
              "Generado por `reporte/generar_tablas.py` a partir de `medicion/resultados/` "
              "(`resumen.csv` y `mediciones_*.csv`). No editar a mano: volver a correr el "
              f"script. {SIN_DATO} = no medido o sin casos resueltos.", ""]
    lineas += seccion_comparativa(resumen)
    lineas += seccion_topes(mediciones)
    lineas += seccion_memoria(resumen)
    lineas += seccion_nodos(resumen)
    return "\n".join(lineas).rstrip("\n") + "\n"


def main(argumentos: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m reporte.generar_tablas",
                                     description="Escribe las tablas del reporte desde los CSV.")
    parser.add_argument("--resultados", type=Path, default=RESULTADOS)
    parser.add_argument("--salida", type=Path, default=SALIDA)
    args = parser.parse_args(argumentos)
    texto = generar(args.resultados)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    with open(args.salida, "w", encoding="utf-8", newline="\n") as archivo:
        archivo.write(texto)
    print(f"Tablas escritas en {args.salida}")


if __name__ == "__main__":
    main()
