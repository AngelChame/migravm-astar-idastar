import statistics

import pytest

from buscadores import Resultado, a_estrella, buscar, costo_uniforme, ida_estrella, voraz
from heuristicas import h0, h1, h2
from modelo import Accion, Escenario, validar_plan
from utilidades import _generar_cluster_provisional

EJEMPLO = Escenario(
    capacidades=(6, 6, 6, 6),
    tamanos=(2, 1, 3, 1, 4, 4),
    inicial=(3, 3, 0, 3, 2, 1),
    servidor_a_vaciar=0,
    nombre="ejemplo",
)
SIN_SOLUCION = Escenario(capacidades=(6, 2, 2), tamanos=(3,), inicial=(0,), servidor_a_vaciar=0)
SIN_SOLUCION_CON_CICLOS = Escenario((6, 3, 3), (4, 1), (0, 1), 0)

BUSCADORES = {
    "ucs": lambda esc, tope=None: costo_uniforme(esc, tope),
    "voraz": lambda esc, tope=None: voraz(esc, h2, tope),
    "astar": lambda esc, tope=None: a_estrella(esc, h2, tope),
    "ida": lambda esc, tope=None: ida_estrella(esc, h2, tope),
}


def _revisar_plan(esc: Escenario, r: Resultado) -> None:
    assert r.estado == "resuelto"
    assert isinstance(r.plan, tuple)
    assert validar_plan(esc, r.plan) == r.costo


@pytest.mark.parametrize("correr, costo, nodos, iteraciones", [
    (lambda: costo_uniforme(EJEMPLO), 4, 15, None),
    (lambda: a_estrella(EJEMPLO, h1), 4, 5, None),
    (lambda: a_estrella(EJEMPLO, h2), 4, 5, None),
    (lambda: ida_estrella(EJEMPLO, h2), 4, 2, 1),
    (lambda: voraz(EJEMPLO, h2), 5, 2, None),
], ids=["ucs", "astar_h1", "astar_h2", "ida_h2", "voraz_h2"])
def test_tabla_del_ejemplo(correr, costo, nodos, iteraciones):
    r = correr()
    assert r.estado == "resuelto"
    assert r.costo == costo
    assert r.nodos_expandidos == nodos
    assert r.iteraciones == iteraciones
    _revisar_plan(EJEMPLO, r)


def test_plan_optimo_del_ejemplo():
    plan = (Accion(1, 3, 1), Accion(2, 0, 3))
    assert a_estrella(EJEMPLO, h2).plan == plan
    assert ida_estrella(EJEMPLO, h2).plan == plan


@pytest.mark.parametrize("h", [h0, h1, h2])
@pytest.mark.parametrize("transposicion", [True, False])
def test_ida_optimo_con_toda_heuristica(h, transposicion):
    r = ida_estrella(EJEMPLO, h, transposicion=transposicion)
    assert r.costo == 4
    _revisar_plan(EJEMPLO, r)


@pytest.mark.parametrize("h", [h0, h1, h2])
def test_planes_validos_en_el_ejemplo(h):
    for r in (a_estrella(EJEMPLO, h), voraz(EJEMPLO, h), costo_uniforme(EJEMPLO)):
        _revisar_plan(EJEMPLO, r)


@pytest.mark.parametrize("nombre", BUSCADORES)
def test_caso_sin_solucion(nombre):
    r = BUSCADORES[nombre](SIN_SOLUCION)
    assert r.estado == "sin_solucion"
    assert r.nodos_expandidos == 1
    assert r.plan is None and r.costo is None
    assert r.iteraciones == (1 if nombre == "ida" else None)


def test_ida_sin_solucion_con_ciclos():
    con_tabla = ida_estrella(SIN_SOLUCION_CON_CICLOS, h2, transposicion=True)
    assert (con_tabla.estado, con_tabla.iteraciones, con_tabla.nodos_expandidos) == (
        "sin_solucion", 3, 6)
    sin_tabla = ida_estrella(SIN_SOLUCION_CON_CICLOS, h2, transposicion=False)
    assert (sin_tabla.estado, sin_tabla.iteraciones, sin_tabla.nodos_expandidos) == (
        "sin_solucion", 2, 3)


@pytest.mark.parametrize("nombre", ["ucs", "voraz", "astar"])
def test_sin_solucion_con_ciclos_otros(nombre):
    r = BUSCADORES[nombre](SIN_SOLUCION_CON_CICLOS)
    assert r.estado == "sin_solucion"
    assert r.plan is None and r.costo is None


@pytest.mark.parametrize("nombre", BUSCADORES)
def test_tope_uno_en_el_ejemplo(nombre):
    r = BUSCADORES[nombre](EJEMPLO, 1)
    assert r.estado == "tope"
    assert r.nodos_expandidos == 1
    assert r.plan is None and r.costo is None


@pytest.mark.parametrize("nombre", BUSCADORES)
def test_estado_inicial_ya_es_meta(nombre):
    esc = Escenario((6, 6, 6), (2, 1), (1, 2), 0)
    r = BUSCADORES[nombre](esc)
    assert (r.estado, r.costo, r.plan, r.nodos_expandidos) == ("resuelto", 0, (), 0)


def test_ida_sin_transposicion_guarda_profundidad():
    r = ida_estrella(EJEMPLO, h2, transposicion=False)
    assert r.estados_guardados == 3  # s0, el estado intermedio y la meta


def test_buscar_despacha_por_nombre():
    for algoritmo in ("ucs", "voraz", "astar", "ida"):
        r = buscar(EJEMPLO, algoritmo, "h1")
        assert r.algoritmo == algoritmo
        _revisar_plan(EJEMPLO, r)
    assert buscar(EJEMPLO, "ucs", "h1").heuristica == "h0"
    assert buscar(EJEMPLO, "astar", "h1").heuristica == "h1"
    assert buscar(EJEMPLO, "ida").heuristica == "h2"
    assert buscar(EJEMPLO, "ida").iteraciones == 1


def test_buscar_ida_usa_transposicion():
    r = buscar(SIN_SOLUCION_CON_CICLOS, "ida")
    # Con tabla: 3 iteraciones y 6 nodos; sin tabla serian 2 y 3.
    assert (r.estado, r.iteraciones, r.nodos_expandidos) == ("sin_solucion", 3, 6)


def test_buscar_nombres_desconocidos():
    with pytest.raises(ValueError):
        buscar(EJEMPLO, "dijkstra")
    with pytest.raises(ValueError):
        buscar(EJEMPLO, "astar", "h9")


# --- 12 no triviales de 8x24 (ARQUITECTURA.md seccion 6) ---

TOPE = 150_000


@pytest.fixture(scope="module")
def no_triviales_8x24():
    clusteres = []
    no_triviales = []
    for semilla in range(60):
        esc = _generar_cluster_provisional(semilla, 8, 24, factor=1.03, servidor_a_vaciar=0)
        if esc is None:
            continue
        clusteres.append(esc)
        r = a_estrella(esc, h2, TOPE)
        if r.estado == "resuelto" and r.costo > h1(esc, esc.inicial):
            no_triviales.append((semilla, esc, r))
    return clusteres, no_triviales


def test_doce_no_triviales_de_sesenta(no_triviales_8x24):
    clusteres, no_triviales = no_triviales_8x24
    assert len(clusteres) == 60
    assert len(no_triviales) == 12
    primeras = [(s, r.costo, h1(esc, esc.inicial)) for s, esc, r in no_triviales[:4]]
    assert primeras == [(0, 11, 10), (2, 9, 8), (4, 8, 6), (6, 9, 8)]


@pytest.mark.parametrize("correr, mediana, maximo", [
    (lambda esc: a_estrella(esc, h1, TOPE), 872, 45_731),
    (lambda esc: a_estrella(esc, h2, TOPE), 188.5, 10_493),
    (lambda esc: ida_estrella(esc, h2, TOPE, transposicion=True), 17.5, 3_365),
    (lambda esc: voraz(esc, h2, TOPE), 4, 16),
], ids=["astar_h1", "astar_h2", "ida_h2", "voraz_h2"])
def test_nodos_en_no_triviales(no_triviales_8x24, correr, mediana, maximo):
    _, no_triviales = no_triviales_8x24
    nodos = []
    for _, esc, optimo in no_triviales:
        r = correr(esc)
        _revisar_plan(esc, r)
        if r.algoritmo == "voraz":
            assert r.costo >= optimo.costo
        else:
            assert r.costo == optimo.costo
        nodos.append(r.nodos_expandidos)
    assert statistics.median(nodos) == mediana
    assert max(nodos) == maximo
