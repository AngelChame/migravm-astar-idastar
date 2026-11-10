import csv
from dataclasses import replace
from pathlib import Path

import pytest

from escenarios import (
    COLUMNAS_METAS,
    COLUMNAS_SERVIDORES,
    COLUMNAS_VMS,
    cargar_escenario,
    es_no_trivial,
    generar_cluster,
    generar_no_triviales,
    guardar_escenario,
)
from escenarios.generar import main as generar_main
from escenarios.nucleo import _generar_con_metas, _leer_metas
from heuristicas import h1
from modelo import Escenario, EscenarioInvalido

EJEMPLO = Escenario((6, 6, 6, 6), (2, 1, 3, 1, 4, 4), (3, 3, 0, 3, 2, 1), 0, "ejemplo")
TOPE = 150_000


def _escribir(ruta, filas):
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        csv.writer(archivo).writerows(filas)


# --- Guardar y cargar ---

def test_guardar_y_cargar_da_el_mismo_escenario(tmp_path):
    esc = replace(generar_cluster(0, 8, 24), nombre="8x24_s0_x0")
    guardar_escenario(esc, tmp_path / "8x24_s0")
    assert cargar_escenario(tmp_path / "8x24_s0", 0) == esc


def test_cargar_con_otro_servidor_a_vaciar(tmp_path):
    guardar_escenario(EJEMPLO, tmp_path / "ejemplo")
    esc = cargar_escenario(tmp_path / "ejemplo", 2)
    assert esc == replace(EJEMPLO, servidor_a_vaciar=2, nombre="ejemplo_x2")
    assert isinstance(esc.capacidades, tuple) and isinstance(esc.inicial, tuple)


def test_cargar_acepta_crlf_y_filas_desordenadas(tmp_path):
    carpeta = tmp_path / "c"
    carpeta.mkdir()
    with open(carpeta / "servidores.csv", "w", encoding="utf-8", newline="") as f:
        f.write("servidor,capacidad\r\n1,6\r\n0,6\r\n2,6\r\n3,6\r\n")
    _escribir(carpeta / "vms.csv", [COLUMNAS_VMS] + [
        (i, t, s) for i, (t, s) in reversed(list(enumerate(zip(EJEMPLO.tamanos,
                                                                  EJEMPLO.inicial))))])
    assert cargar_escenario(carpeta, 0) == replace(EJEMPLO, nombre="c_x0")


@pytest.mark.parametrize("servidores, vms", [
    ([("servidor", "cap"), (0, 6), (1, 6)], [COLUMNAS_VMS, (0, 1, 1)]),       # encabezado
    ([COLUMNAS_SERVIDORES, (0, 6), (1, "seis")], [COLUMNAS_VMS, (0, 1, 1)]),  # no entero
    ([COLUMNAS_SERVIDORES, (0, 6), (2, 6)], [COLUMNAS_VMS, (0, 1, 1)]),       # hueco
    ([COLUMNAS_SERVIDORES, (0, 6), (0, 6)], [COLUMNAS_VMS, (0, 1, 1)]),       # repetido
    ([COLUMNAS_SERVIDORES, (0, 6), (1, 6)], [COLUMNAS_VMS, (0, 1)]),          # faltan valores
    ([COLUMNAS_SERVIDORES, (0, 6), (1, 2)], [COLUMNAS_VMS, (0, 3, 1)]),       # excede capacidad
    ([COLUMNAS_SERVIDORES, (0, 6), (1, 6)], [COLUMNAS_VMS, (0, 1, 5)]),       # servidor fuera
    ([COLUMNAS_SERVIDORES, (0, 6)], [COLUMNAS_VMS, (0, 1, 0)]),               # H < 2
], ids=["encabezado", "no_entero", "hueco", "repetido", "faltan_valores", "excede",
        "servidor_fuera", "un_servidor"])
def test_cargar_rechaza_datos_invalidos(tmp_path, servidores, vms):
    _escribir(tmp_path / "servidores.csv", servidores)
    _escribir(tmp_path / "vms.csv", vms)
    with pytest.raises(EscenarioInvalido):
        cargar_escenario(tmp_path, 0)


def test_cargar_rechaza_servidor_a_vaciar_fuera_de_rango(tmp_path):
    guardar_escenario(EJEMPLO, tmp_path)
    with pytest.raises(EscenarioInvalido):
        cargar_escenario(tmp_path, 4)


# --- generar_cluster ---

def test_semilla_0_de_8x24():
    esc = generar_cluster(0, 8, 24)
    assert esc.capacidades == (10,) * 8
    assert esc.tamanos[:6] == (4, 4, 1, 3, 4, 4)
    assert esc.inicial[:6] == (4, 0, 3, 5, 6, 5)
    assert (esc.servidor_a_vaciar, esc.nombre) == (0, "")


def test_generar_cluster_es_determinista_y_respeta_ocupados():
    for semilla in range(20):
        a = generar_cluster(semilla, 6, 16, ocupados=(0, 1, 2))
        assert a == generar_cluster(semilla, 6, 16, ocupados=(0, 1, 2))
        if a is not None:
            assert all(servidor in a.inicial for servidor in (0, 1, 2))


def test_generar_cluster_devuelve_none_sin_asignacion():
    # Con un solo intento casi nunca quedan ocupados los 8 servidores con 8 VM.
    resultados = [generar_cluster(s, 8, 8, ocupados=tuple(range(8)), max_intentos=1)
                  for s in range(20)]
    assert None in resultados


@pytest.mark.parametrize("argumentos", [
    dict(n_servidores=1, n_vms=3),
    dict(n_servidores=0, n_vms=3),
    dict(n_servidores=4, n_vms=0),
    dict(n_servidores=4, n_vms=3, servidor_a_vaciar=4),
    dict(n_servidores=4, n_vms=3, servidor_a_vaciar=-1),
    dict(n_servidores=4, n_vms=3, ocupados=(0, 4)),
    dict(n_servidores=4, n_vms=3, ocupados=(-1,)),
], ids=["H1", "H0", "V0", "X_fuera", "X_negativo", "ocupado_fuera", "ocupado_negativo"])
def test_generar_cluster_valida_parametros(argumentos):
    with pytest.raises(EscenarioInvalido):
        generar_cluster(0, **argumentos)


# --- es_no_trivial ---

def test_es_no_trivial_en_el_ejemplo():
    assert es_no_trivial(EJEMPLO, TOPE) is True             # optimo 4 > h1 3
    assert es_no_trivial(EJEMPLO, TOPE, "ida") is True
    assert es_no_trivial(EJEMPLO, 1) is None                # llega al tope


def test_es_no_trivial_trivial_y_sin_solucion():
    trivial = Escenario((6, 6, 6), (2, 1), (0, 1), 0)
    assert es_no_trivial(trivial, TOPE) is False
    x_vacio = Escenario((6, 6, 6), (2, 1), (1, 2), 0)
    assert es_no_trivial(x_vacio, TOPE) is False
    sin_solucion = Escenario((6, 2, 2), (3,), (0,), 0)
    assert es_no_trivial(sin_solucion, TOPE) is None
    assert es_no_trivial(sin_solucion, TOPE, "ida") is None


@pytest.mark.parametrize("algoritmo", ["voraz", "dijkstra"])
def test_es_no_trivial_rechaza_algoritmos_no_optimos(algoritmo):
    with pytest.raises(ValueError):
        es_no_trivial(EJEMPLO, TOPE, algoritmo)


def test_doce_no_triviales_de_sesenta_8x24():
    no_triviales = []
    for semilla in range(60):
        esc = generar_cluster(semilla, 8, 24)
        assert esc is not None
        if es_no_trivial(esc, TOPE):
            no_triviales.append(semilla)
    assert len(no_triviales) == 12
    assert no_triviales[:4] == [0, 2, 4, 6]


# --- generar_no_triviales ---

def test_generar_no_triviales_nombres_y_orden():
    escenarios = generar_no_triviales(4, 7, 10, TOPE)
    assert len(escenarios) == 10
    assert escenarios == generar_no_triviales(4, 7, 10, TOPE)
    claves = []
    for esc in escenarios:
        semilla = int(esc.nombre.split("_s")[1].split("_x")[0])
        assert esc.nombre == f"4x7_s{semilla}_x{esc.servidor_a_vaciar}"
        assert replace(esc, nombre="") == replace(
            generar_cluster(semilla, 4, 7), servidor_a_vaciar=esc.servidor_a_vaciar)
        assert es_no_trivial(esc, TOPE) is True
        claves.append((semilla, esc.servidor_a_vaciar))
    assert claves == sorted(claves)
    assert len(set(claves)) == len(claves)


def test_generar_no_triviales_ida_y_astar_coinciden_en_6x16():
    assert generar_no_triviales(6, 16, 30, TOPE, algoritmo="astar") == \
        generar_no_triviales(6, 16, 30, TOPE, algoritmo="ida")


def test_generar_no_triviales_respeta_semilla_y_servidores():
    escenarios = generar_no_triviales(5, 10, 5, TOPE, semilla_inicial=10,
                                      servidores_a_vaciar=(3, 4))
    assert len(escenarios) == 5
    for esc in escenarios:
        assert esc.servidor_a_vaciar in (3, 4)
        assert int(esc.nombre.split("_s")[1].split("_x")[0]) >= 10


def test_generar_con_metas_coincide_con_la_busqueda():
    for meta in _generar_con_metas(5, 10, 8, TOPE):
        esc = meta.escenario
        assert meta.h1_inicial == h1(esc, esc.inicial)
        assert meta.costo_optimo > meta.h1_inicial


# --- Linea de comandos ---

def test_linea_de_comandos(tmp_path):
    generar_main(["--servidores", "4", "--vms", "7", "--cantidad", "6", "--tope", str(TOPE),
                  "--salida", str(tmp_path)])
    esperados = generar_no_triviales(4, 7, 6, TOPE)
    leidos = []
    for carpeta in sorted(tmp_path.iterdir()):
        metas = _leer_metas(carpeta)
        assert metas
        for x, h1_inicial, costo in metas:
            esc = cargar_escenario(carpeta, x)
            assert h1(esc, esc.inicial) == h1_inicial
            assert es_no_trivial(esc, TOPE) is True
            leidos.append(esc)
    assert sorted(leidos, key=lambda e: e.nombre) == sorted(esperados, key=lambda e: e.nombre)
    assert COLUMNAS_METAS == ("servidor_a_vaciar", "h1_inicial", "costo_optimo")


# --- Datos versionados en escenarios/datos/ ---

DATOS = Path(__file__).resolve().parent.parent / "escenarios" / "datos"
TAMANOS = [(4, 7), (5, 10), (6, 16), (8, 24), (10, 32)]


def _carpetas(n_servidores, n_vms):
    return sorted(DATOS.glob(f"{n_servidores}x{n_vms}_s*"))


@pytest.mark.parametrize("n_servidores, n_vms", TAMANOS, ids=[f"{h}x{v}" for h, v in TAMANOS])
def test_datos_treinta_o_mas_por_tamano(n_servidores, n_vms):
    filas = 0
    for carpeta in _carpetas(n_servidores, n_vms):
        semilla = int(carpeta.name.split("_s")[1])
        base = generar_cluster(semilla, n_servidores, n_vms)
        metas = _leer_metas(carpeta)
        assert metas, carpeta.name
        for x, h1_inicial, costo in metas:
            esc = cargar_escenario(carpeta, x)
            assert esc == replace(base, servidor_a_vaciar=x, nombre=f"{carpeta.name}_x{x}")
            assert h1(esc, esc.inicial) == h1_inicial
            assert costo > h1_inicial
            filas += 1
    assert filas >= 30


@pytest.mark.parametrize("n_servidores, n_vms", TAMANOS, ids=[f"{h}x{v}" for h, v in TAMANOS])
def test_datos_se_regeneran_igual(n_servidores, n_vms):
    generados = {(m.escenario.nombre, m.h1_inicial, m.costo_optimo): m.escenario
                 for m in _generar_con_metas(n_servidores, n_vms, 30, TOPE)}
    leidos = {}
    for carpeta in _carpetas(n_servidores, n_vms):
        for x, h1_inicial, costo in _leer_metas(carpeta):
            esc = cargar_escenario(carpeta, x)
            leidos[(esc.nombre, h1_inicial, costo)] = esc
    assert leidos == generados
