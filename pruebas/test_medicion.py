import csv
from dataclasses import fields, replace
from pathlib import Path

import pytest

from medicion import (
    COLUMNAS_MEDICION,
    Medicion,
    correr_lote,
    escribir_csv,
    medir,
    resumen_por_algoritmo,
)
from medicion.correr import CONFIGURACIONES, COLUMNAS_RESUMEN, cargar_tamano
from medicion.correr import main as correr_main
from medicion.nucleo import _leer_csv
from modelo import Escenario

EJEMPLO = Escenario((6, 6, 6, 6), (2, 1, 3, 1, 4, 4), (3, 3, 0, 3, 2, 1), 0, "ejemplo")
SIN_SOLUCION = Escenario((6, 2, 2), (3,), (0,), 0, "sin_solucion")
TOPE = 150_000
CINCO = [("ucs", "h0"), ("voraz", "h2"), ("astar", "h1"), ("astar", "h2"), ("ida", "h2")]


# --- medir ---

def test_medir_astar_en_el_ejemplo():
    m = medir(EJEMPLO, "astar", "h2", TOPE, tiempo_minimo_s=0)
    assert (m.escenario, m.servidores, m.vms, m.servidor_a_vaciar) == ("ejemplo", 4, 6, 0)
    assert (m.algoritmo, m.heuristica, m.estado) == ("astar", "h2", "resuelto")
    assert (m.costo, m.migraciones, m.nodos_expandidos) == (4, 2, 5)
    assert m.costo_optimo is None and m.iteraciones is None
    assert m.memoria_pico_kb is None
    assert m.tiempo_cpu_s >= 0 and isinstance(m.tiempo_cpu_s, float)
    assert m.tope_nodos == TOPE


def test_medir_con_memoria_no_cambia_los_conteos():
    sin = medir(EJEMPLO, "astar", "h2", tiempo_minimo_s=0)
    con = medir(EJEMPLO, "astar", "h2", con_memoria=True, tiempo_minimo_s=0)
    assert con.memoria_pico_kb > 0
    assert (con.nodos_expandidos, con.estados_guardados, con.costo) == (
        sin.nodos_expandidos, sin.estados_guardados, sin.costo)


def test_medir_repite_hasta_el_tiempo_minimo():
    una = medir(EJEMPLO, "ida", "h2", tiempo_minimo_s=0)
    repetida = medir(EJEMPLO, "ida", "h2", tiempo_minimo_s=0.05)
    assert repetida.tiempo_cpu_s > 0
    assert replace(repetida, tiempo_cpu_s=0.0) == replace(una, tiempo_cpu_s=0.0)


def test_medir_ucs_reporta_h0_e_ida_sus_iteraciones():
    assert medir(EJEMPLO, "ucs", "h2", tiempo_minimo_s=0).heuristica == "h0"
    assert medir(EJEMPLO, "ida", "h2", tiempo_minimo_s=0).iteraciones == 1


def test_medir_ida_sin_tabla():
    m = medir(EJEMPLO, "ida_sin_tabla", "h2", TOPE, tiempo_minimo_s=0)
    assert (m.algoritmo, m.heuristica, m.costo, m.iteraciones) == ("ida_sin_tabla", "h2", 4, 1)
    ciclos = Escenario((6, 3, 3), (4, 1), (0, 1), 0, "ciclos")
    sin_tabla = medir(ciclos, "ida_sin_tabla", "h2", TOPE, tiempo_minimo_s=0)
    con_tabla = medir(ciclos, "ida", "h2", TOPE, tiempo_minimo_s=0)
    assert (sin_tabla.algoritmo, sin_tabla.iteraciones, sin_tabla.nodos_expandidos) == (
        "ida_sin_tabla", 2, 3)
    assert (con_tabla.algoritmo, con_tabla.iteraciones, con_tabla.nodos_expandidos) == (
        "ida", 3, 6)


def test_medir_rechaza_configuraciones_invalidas():
    with pytest.raises(ValueError):
        medir(EJEMPLO, "ida_sin_tabla", "h2", None, tiempo_minimo_s=0)
    with pytest.raises(ValueError):
        medir(EJEMPLO, "dijkstra", "h2", TOPE, tiempo_minimo_s=0)
    with pytest.raises(ValueError):
        medir(EJEMPLO, "astar", "h9", TOPE, tiempo_minimo_s=0)
    with pytest.raises(ValueError):
        medir(EJEMPLO, "ida_sin_tabla", "h9", TOPE, tiempo_minimo_s=0)


def test_medir_con_tope():
    m = medir(EJEMPLO, "astar", "h2", 1, tiempo_minimo_s=0)
    assert (m.estado, m.costo, m.migraciones, m.nodos_expandidos, m.tope_nodos) == (
        "tope", None, None, 1, 1)


# --- correr_lote ---

def test_correr_lote_orden_y_costo_optimo():
    mediciones = correr_lote([EJEMPLO, SIN_SOLUCION], CINCO, TOPE, tiempo_minimo_s=0)
    assert [(m.escenario, m.algoritmo, m.heuristica) for m in mediciones] == [
        (esc, a, h) for esc in ("ejemplo", "sin_solucion") for a, h in CINCO]
    ejemplo = [m for m in mediciones if m.escenario == "ejemplo"]
    assert all(m.costo_optimo == 4 for m in ejemplo)
    voraz = next(m for m in ejemplo if m.algoritmo == "voraz")
    assert (voraz.costo, voraz.costo_optimo) == (5, 4)
    assert all(m.costo_optimo is None for m in mediciones if m.escenario == "sin_solucion")
    assert all(m.memoria_pico_kb is None for m in mediciones)


def test_correr_lote_toma_el_optimo_de_cualquier_algoritmo_optimo():
    for config in (("ucs", "h0"), ("astar", "h1"), ("ida", "h2"), ("ida_sin_tabla", "h2")):
        m = correr_lote([EJEMPLO], [("voraz", "h2"), config], TOPE, tiempo_minimo_s=0)
        assert [f.costo_optimo for f in m] == [4, 4]
    solo_voraz = correr_lote([EJEMPLO], [("voraz", "h2")], TOPE, tiempo_minimo_s=0)
    assert solo_voraz[0].costo_optimo is None


def test_correr_lote_usa_el_mapa_y_detecta_discrepancias():
    m = correr_lote([EJEMPLO], [("voraz", "h2")], TOPE, costos_optimos={"ejemplo": 4},
                    tiempo_minimo_s=0)
    assert m[0].costo_optimo == 4
    m = correr_lote([EJEMPLO], [("ida", "h2")], TOPE, costos_optimos={"otro": 9},
                    tiempo_minimo_s=0)
    assert m[0].costo_optimo == 4
    with pytest.raises(ValueError):
        correr_lote([EJEMPLO], [("ida", "h2")], TOPE, costos_optimos={"ejemplo": 5},
                    tiempo_minimo_s=0)


def test_correr_lote_tope_no_aporta_optimo():
    m = correr_lote([EJEMPLO], [("astar", "h2")], 1, tiempo_minimo_s=0)
    assert (m[0].estado, m[0].costo_optimo) == ("tope", None)


def test_correr_lote_con_memoria():
    m = correr_lote([EJEMPLO], CINCO, TOPE, con_memoria=True, tiempo_minimo_s=0)
    assert all(f.memoria_pico_kb > 0 for f in m)


# --- CSV ---

def test_columnas_coinciden_con_medicion():
    assert COLUMNAS_MEDICION == tuple(f.name for f in fields(Medicion))


def test_escribir_csv_columnas_exactas_y_valores(tmp_path):
    mediciones = correr_lote([EJEMPLO, SIN_SOLUCION], CINCO, TOPE, con_memoria=True,
                             tiempo_minimo_s=0)
    ruta = tmp_path / "sub" / "mediciones.csv"
    escribir_csv(mediciones, ruta)
    with open(ruta, encoding="utf-8", newline="") as archivo:
        filas = list(csv.reader(archivo))
    assert tuple(filas[0]) == COLUMNAS_MEDICION
    assert len(filas) == 1 + len(mediciones)
    sin_plan = next(f for f in filas[1:] if f[0] == "sin_solucion")
    assert sin_plan[COLUMNAS_MEDICION.index("costo")] == ""
    assert _leer_csv(ruta) == mediciones


# --- resumen_por_algoritmo ---

def _m(algoritmo, estado, nodos, tiempo, guardados, memoria=None):
    return Medicion("e", 4, 6, 0, algoritmo, "h2", estado, None, None, None, nodos, guardados,
                    None, tiempo, memoria, 100)


def test_resumen_por_algoritmo():
    mediciones = [
        _m("astar", "resuelto", 10, 0.1, 50, 2.0),
        _m("ida", "resuelto", 3, 0.5, 7),
        _m("astar", "resuelto", 20, 0.3, 80, 5.0),
        _m("astar", "tope", 100, 9.0, 900),
        _m("ida", "sin_solucion", 1, 0.0, 1),
        _m("voraz", "tope", 100, 1.0, 40),
    ]
    filas = resumen_por_algoritmo(mediciones)
    assert [f["algoritmo"] for f in filas] == ["astar", "ida", "voraz"]
    astar, ida, voraz = filas
    assert astar == {"algoritmo": "astar", "heuristica": "h2", "casos": 3, "resueltos": 2,
                     "nodos_mediana": 15, "nodos_max": 20, "tiempo_mediana_s": 0.2,
                     "estados_guardados_max": 900, "memoria_pico_max_kb": 5.0,
                     "casos_con_memoria": 2}
    assert (ida["resueltos"], ida["nodos_mediana"], ida["memoria_pico_max_kb"],
            ida["casos_con_memoria"]) == (1, 3, None, 0)
    assert (voraz["resueltos"], voraz["nodos_mediana"], voraz["nodos_max"],
            voraz["tiempo_mediana_s"], voraz["estados_guardados_max"]) == (0, None, None, None, 40)


def test_resumen_separa_heuristicas():
    a = _m("astar", "resuelto", 1, 0.0, 1)
    filas = resumen_por_algoritmo([a, replace(a, heuristica="h1")])
    assert [(f["algoritmo"], f["heuristica"]) for f in filas] == [("astar", "h2"), ("astar", "h1")]


# --- Linea de comandos ---

def test_configuraciones_por_tamano():
    assert sum(len(c) for c in CONFIGURACIONES.values()) == 28
    memoria = {t: [(a, h) for a, h, m in c if m] for t, c in CONFIGURACIONES.items()}
    assert memoria["6x16"] == [("voraz", "h2"), ("astar", "h1"), ("astar", "h2"), ("ida", "h2"),
                               ("ida_sin_tabla", "h2")]
    assert memoria["8x24"] == [("voraz", "h2"), ("astar", "h2"), ("ida", "h2")]
    assert memoria["10x32"] == [("voraz", "h2"), ("ida", "h2")]


def test_linea_de_comandos_4x7(tmp_path):
    correr_main(["--tamanos", "4x7", "--tiempo-minimo", "0", "--salida", str(tmp_path)])
    mediciones = _leer_csv(tmp_path / "mediciones_4x7.csv")
    assert len(mediciones) == 30 * 6
    assert all(m.tope_nodos == TOPE for m in mediciones)
    optimos = [m for m in mediciones if m.algoritmo != "voraz" and m.estado == "resuelto"]
    assert all(m.costo == m.costo_optimo for m in optimos)
    with open(tmp_path / "resumen.csv", encoding="utf-8", newline="") as archivo:
        filas = list(csv.DictReader(archivo))
    assert tuple(filas[0]) == COLUMNAS_RESUMEN
    assert [(f["algoritmo"], f["heuristica"], f["casos"]) for f in filas] == [
        (a, h, "30") for a, h, _ in CONFIGURACIONES["4x7"]]


# --- Tabla de cinco tamanos (medicion/resultados/ versionado) ---

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "medicion" / "resultados"
DATOS = RAIZ / "escenarios" / "datos"
TAMANOS = list(CONFIGURACIONES)


def _mediciones(tamano):
    return _leer_csv(RESULTADOS / f"mediciones_{tamano}.csv")


def test_resultados_archivos_exactos():
    esperados = {f"mediciones_{t}.csv" for t in TAMANOS} | {"resumen.csv"}
    assert {p.name for p in RESULTADOS.iterdir()} == esperados
    assert sum(len(_mediciones(t)) for t in TAMANOS) == 840


@pytest.mark.parametrize("tamano", TAMANOS)
def test_resultados_filas_por_tamano(tamano):
    mediciones = _mediciones(tamano)
    escenarios, optimos = cargar_tamano(DATOS, tamano)
    configs = CONFIGURACIONES[tamano]
    assert [(m.escenario, m.algoritmo, m.heuristica) for m in mediciones] == [
        (esc.nombre, a, h) for esc in escenarios for a, h, _ in configs]
    con_memoria = {(a, h) for a, h, m in configs if m}
    for m in mediciones:
        assert m.tope_nodos == TOPE
        assert m.costo_optimo == optimos[m.escenario]
        assert (m.memoria_pico_kb is not None) == ((m.algoritmo, m.heuristica) in con_memoria)
        assert m.tiempo_cpu_s > 0
        if m.estado == "resuelto":
            assert m.migraciones is not None and m.migraciones >= 1
            if m.algoritmo == "voraz":
                assert m.costo >= m.costo_optimo
            else:
                assert m.costo == m.costo_optimo
        else:
            assert m.estado == "tope"
            assert (m.costo, m.migraciones, m.nodos_expandidos) == (None, None, TOPE)


@pytest.mark.parametrize("tamano", TAMANOS)
def test_resultados_se_reproducen_en_las_configuraciones_baratas(tamano):
    baratas = [("voraz", "h2"), ("ida", "h2")]
    if tamano in ("4x7", "5x10", "6x16"):
        baratas.append(("astar", "h2"))
    guardadas = {(m.escenario, m.algoritmo, m.heuristica): m for m in _mediciones(tamano)}
    escenarios, optimos = cargar_tamano(DATOS, tamano)
    for m in correr_lote(escenarios, baratas, TOPE, costos_optimos=optimos, tiempo_minimo_s=0):
        g = guardadas[(m.escenario, m.algoritmo, m.heuristica)]
        assert replace(m, tiempo_cpu_s=0.0, memoria_pico_kb=None) == replace(
            g, tiempo_cpu_s=0.0, memoria_pico_kb=None)


def test_resumen_coincide_con_las_mediciones():
    with open(RESULTADOS / "resumen.csv", encoding="utf-8", newline="") as archivo:
        lector = csv.DictReader(archivo)
        assert tuple(lector.fieldnames) == COLUMNAS_RESUMEN
        leidas = list(lector)
    esperadas = []
    for tamano in TAMANOS:
        mediciones = _mediciones(tamano)
        for fila in resumen_por_algoritmo(mediciones):
            esperadas.append({"servidores": mediciones[0].servidores,
                              "vms": mediciones[0].vms, "tope_nodos": TOPE, **fila})
    assert len(leidas) == len(esperadas) == 28
    for leida, esperada in zip(leidas, esperadas):
        for clave in COLUMNAS_RESUMEN:
            valor = esperada[clave]
            if valor is None:
                assert leida[clave] == ""
            elif isinstance(valor, (int, float)):
                assert float(leida[clave]) == pytest.approx(valor)
            else:
                assert leida[clave] == valor
