from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from escenarios import cargar_escenario
from modelo import Accion, Escenario, validar_plan
from web.app import app

cliente = TestClient(app)

EJEMPLO = {"capacidades": [6, 6, 6, 6], "tamanos": [2, 1, 3, 1, 4, 4],
           "inicial": [3, 3, 0, 3, 2, 1], "servidor_a_vaciar": 0}
SIN_SOLUCION = {"capacidades": [6, 2, 2], "tamanos": [3], "inicial": [0],
                "servidor_a_vaciar": 0}
CLAVES_SOLUCION = {"algoritmo", "heuristica", "estado", "costo", "nodos_expandidos",
                   "estados_guardados", "iteraciones", "tiempo_cpu_s", "tope_nodos",
                   "inicial", "plan"}


def _buscar(**campos):
    pedido = {"escenario": EJEMPLO, "algoritmo": "astar", "heuristica": "h2"}
    pedido.update(campos)
    return cliente.post("/api/buscar", json=pedido)


# --- POST /api/buscar ---

def test_buscar_el_ejemplo():
    r = _buscar()
    assert r.status_code == 200
    s = r.json()
    assert set(s) == CLAVES_SOLUCION
    assert (s["algoritmo"], s["heuristica"], s["estado"], s["costo"]) == ("astar", "h2",
                                                                          "resuelto", 4)
    assert (s["nodos_expandidos"], s["iteraciones"], s["tope_nodos"]) == (5, None, 150_000)
    assert s["tiempo_cpu_s"] >= 0
    assert s["inicial"] == {"cargas": [3, 4, 4, 4], "h1": 3, "h2": 4}
    assert s["plan"] == [
        {"paso": 1, "vm": 1, "origen": 3, "destino": 1, "costo": 1,
         "cargas_despues": [3, 5, 4, 3], "g": 1, "h1": 3, "h2": 3},
        {"paso": 2, "vm": 2, "origen": 0, "destino": 3, "costo": 3,
         "cargas_despues": [0, 5, 4, 6], "g": 4, "h1": 0, "h2": 0},
    ]


@pytest.mark.parametrize("algoritmo, heuristica, costo, nodos, iteraciones", [
    ("ucs", "h2", 4, 15, None),
    ("voraz", "h2", 5, 2, None),
    ("astar", "h1", 4, 5, None),
    ("ida", "h2", 4, 2, 1),
])
def test_buscar_cada_algoritmo(algoritmo, heuristica, costo, nodos, iteraciones):
    s = _buscar(algoritmo=algoritmo, heuristica=heuristica).json()
    assert (s["costo"], s["nodos_expandidos"], s["iteraciones"]) == (costo, nodos, iteraciones)
    plan = [Accion(p["vm"], p["origen"], p["destino"]) for p in s["plan"]]
    esc = Escenario(*(tuple(EJEMPLO[k]) for k in ("capacidades", "tamanos", "inicial")),
                    EJEMPLO["servidor_a_vaciar"])
    assert validar_plan(esc, plan) == s["costo"] == s["plan"][-1]["g"]


def test_buscar_ucs_reporta_h0_y_heuristica_por_omision():
    assert _buscar(algoritmo="ucs", heuristica="h9").json()["heuristica"] == "h0"
    pedido = {"escenario": EJEMPLO, "algoritmo": "ida"}
    assert cliente.post("/api/buscar", json=pedido).json()["heuristica"] == "h2"


def test_buscar_sin_solucion_y_tope():
    s = _buscar(escenario=SIN_SOLUCION).json()
    assert (s["estado"], s["costo"], s["plan"], s["nodos_expandidos"]) == (
        "sin_solucion", None, None, 1)
    s = _buscar(tope_nodos=1).json()
    assert (s["estado"], s["costo"], s["plan"], s["nodos_expandidos"], s["tope_nodos"]) == (
        "tope", None, None, 1, 1)


@pytest.mark.parametrize("escenario", [
    {**EJEMPLO, "capacidades": [6, 6, 6, 2]},       # excede una capacidad
    {**EJEMPLO, "servidor_a_vaciar": 4},            # X fuera de rango
    {**EJEMPLO, "inicial": [3, 3, 0]},              # largo distinto
    {**EJEMPLO, "tamanos": [0, 1, 3, 1, 4, 4]},     # tamano < 1
    {**EJEMPLO, "capacidades": [6]},                # H < 2
], ids=["excede", "x_fuera", "largo", "tamano_cero", "un_servidor"])
def test_buscar_escenario_invalido_da_422(escenario):
    r = _buscar(escenario=escenario)
    assert r.status_code == 422
    assert "invalido" in r.json()["detail"]


@pytest.mark.parametrize("servidores, vms", [(9, 4), (4, 25), (10, 32)])
def test_buscar_tamano_mayor_que_8x24_da_422(servidores, vms):
    escenario = {"capacidades": [100] * servidores, "tamanos": [1] * vms,
                 "inicial": [1] * vms, "servidor_a_vaciar": 0}
    r = _buscar(escenario=escenario)
    assert r.status_code == 422
    assert "precalculado" in r.json()["detail"]


def test_buscar_8x24_si_se_acepta():
    escenario = {"capacidades": [100] * 8, "tamanos": [1] * 24, "inicial": [1] * 24,
                 "servidor_a_vaciar": 0}
    s = _buscar(escenario=escenario).json()
    assert (s["estado"], s["costo"]) == ("resuelto", 0)


@pytest.mark.parametrize("campos", [
    {"algoritmo": "dijkstra"},
    {"heuristica": "h9"},
    {"tope_nodos": 0},
    {"tope_nodos": 150_001},
    {"tope_nodos": "100"},
    {"algoritmo": None},
    {"escenario": {**EJEMPLO, "inicial": ["3", 3, 0, 3, 2, 1]}},
    {"escenario": {k: v for k, v in EJEMPLO.items() if k != "tamanos"}},
], ids=["algoritmo", "heuristica", "tope_cero", "tope_grande", "tope_texto",
        "algoritmo_nulo", "estado_texto", "falta_tamanos"])
def test_buscar_entrada_invalida_da_422(campos):
    assert _buscar(**campos).status_code == 422


# --- POST /api/comparar ---

def test_comparar_cinco_soluciones():
    r = cliente.post("/api/comparar", json={"escenario": EJEMPLO})
    assert r.status_code == 200
    soluciones = r.json()
    assert [(s["algoritmo"], s["heuristica"], s["costo"], s["nodos_expandidos"])
            for s in soluciones] == [("ucs", "h0", 4, 15), ("voraz", "h2", 5, 2),
                                     ("astar", "h1", 4, 5), ("astar", "h2", 4, 5),
                                     ("ida", "h2", 4, 2)]
    assert all(set(s) == CLAVES_SOLUCION for s in soluciones)


def test_comparar_con_heuristicas():
    r = cliente.post("/api/comparar", json={"escenario": EJEMPLO, "heuristicas": ["h2", "h1"],
                                            "tope_nodos": 1000})
    assert [(s["algoritmo"], s["heuristica"]) for s in r.json()] == [
        ("ucs", "h0"), ("voraz", "h2"), ("voraz", "h1"), ("astar", "h2"), ("astar", "h1"),
        ("ida", "h2"), ("ida", "h1")]
    assert all(s["tope_nodos"] == 1000 for s in r.json())


@pytest.mark.parametrize("pedido", [
    {"escenario": EJEMPLO, "heuristicas": []},
    {"escenario": EJEMPLO, "heuristicas": ["h2", "h2"]},
    {"escenario": EJEMPLO, "heuristicas": ["h9"]},
    {"escenario": EJEMPLO, "tope_nodos": 0},
    {"escenario": {**EJEMPLO, "servidor_a_vaciar": 9}},
    {"escenario": {"capacidades": [100] * 9, "tamanos": [1], "inicial": [1],
                   "servidor_a_vaciar": 0}},
], ids=["vacia", "repetidas", "desconocida", "tope", "invalido", "grande"])
def test_comparar_entrada_invalida_da_422(pedido):
    assert cliente.post("/api/comparar", json=pedido).status_code == 422


# --- GET /api/escenarios ---

def test_escenarios_150():
    r = cliente.get("/api/escenarios")
    assert r.status_code == 200
    escenarios = r.json()
    assert len(escenarios) == 150
    assert len({e["nombre"] for e in escenarios}) == 150
    tamanos = [(e["servidores"], e["vms"]) for e in escenarios]
    assert tamanos == sorted(tamanos)
    for tamano in [(4, 7), (5, 10), (6, 16), (8, 24), (10, 32)]:
        assert tamanos.count(tamano) == 30
    assert all(e["en_vivo"] == (e["servidores"] <= 8 and e["vms"] <= 24) for e in escenarios)
    assert sum(not e["en_vivo"] for e in escenarios) == 30


def test_escenarios_traen_el_escenario_completo():
    escenarios = cliente.get("/api/escenarios").json()
    e = next(e for e in escenarios if e["nombre"] == "8x24_s0_x0")
    esc = cargar_escenario(Path(__file__).resolve().parent.parent / "escenarios" / "datos" / "8x24_s0", 0)
    assert e["escenario"] == {"capacidades": list(esc.capacidades),
                              "tamanos": list(esc.tamanos), "inicial": list(esc.inicial),
                              "servidor_a_vaciar": 0}
    assert (e["servidores"], e["vms"], e["en_vivo"]) == (8, 24, True)
    s = cliente.post("/api/buscar", json={"escenario": e["escenario"], "algoritmo": "ida"}).json()
    assert (s["estado"], s["costo"]) == ("resuelto", 11)


# --- GET /api/precalculado ---

def test_precalculado_devuelve_filas():
    r = cliente.get("/api/precalculado")
    assert r.status_code == 200
    datos = r.json()
    assert set(datos) == {"resumen", "mediciones"}
    assert len(datos["resumen"]) == 28
    assert len(datos["mediciones"]) == 150
    assert all((m["servidores"], m["vms"]) == (10, 32) for m in datos["mediciones"])
    fila = next(f for f in datos["resumen"] if (f["servidores"], f["vms"], f["algoritmo"])
                == (8, 24, "ida"))
    assert (fila["nodos_mediana"], fila["nodos_max"], fila["estados_guardados_max"]) == (
        15.5, 3365, 142088)
    sin_memoria = next(f for f in datos["resumen"] if (f["servidores"], f["algoritmo"],
                                                      f["heuristica"]) == (10, "astar", "h2"))
    assert sin_memoria["memoria_pico_max_kb"] is None
    assert isinstance(datos["mediciones"][0]["tiempo_cpu_s"], float)
