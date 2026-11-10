import pytest

from heuristicas import HEURISTICAS, h0, h1, h2
from modelo import Accion, Escenario, aplicar, es_meta
from utilidades import _generar_cluster_provisional, costos_optimos, espacio_completo

EJEMPLO = Escenario(
    capacidades=(6, 6, 6, 6),
    tamanos=(2, 1, 3, 1, 4, 4),
    inicial=(3, 3, 0, 3, 2, 1),
    servidor_a_vaciar=0,
    nombre="ejemplo",
)


def test_valores_en_el_ejemplo():
    assert (h0(EJEMPLO, EJEMPLO.inicial), h1(EJEMPLO, EJEMPLO.inicial),
            h2(EJEMPLO, EJEMPLO.inicial)) == (0, 3, 4)


@pytest.mark.parametrize("nombre", ["h0", "h1", "h2"])
def test_cero_en_la_meta(nombre):
    estado = EJEMPLO.inicial
    for accion in (Accion(1, 3, 1), Accion(2, 0, 3)):
        estado = aplicar(EJEMPLO, estado, accion)
    assert es_meta(EJEMPLO, estado)
    assert HEURISTICAS[nombre](EJEMPLO, estado) == 0


def test_diccionario_nombres_y_tipos():
    assert set(HEURISTICAS) == {"h0", "h1", "h2"}
    for nombre, h in HEURISTICAS.items():
        assert h.__name__ == nombre
        assert type(h(EJEMPLO, EJEMPLO.inicial)) is int


def test_h2_igual_a_h1_si_todo_cabe():
    esc = Escenario(capacidades=(6, 6, 6), tamanos=(3, 1), inicial=(0, 1), servidor_a_vaciar=0)
    assert h1(esc, esc.inicial) == 3
    assert h2(esc, esc.inicial) == 3


def test_h2_suma_el_menor_tamano_de_todas_las_vm():
    # La VM de 3 GB en X no cabe (libre maximo 2); el menor tamano esta fuera de X.
    esc = Escenario(capacidades=(6, 3, 3), tamanos=(3, 1, 1), inicial=(0, 1, 2),
                    servidor_a_vaciar=0)
    assert h2(esc, esc.inicial) == 3 + 1


def test_generador_provisional_semilla_0():
    esc = _generar_cluster_provisional(0, 8, 24)
    assert esc is not None
    assert esc.capacidades == (10,) * 8
    assert esc.tamanos[:6] == (4, 4, 1, 3, 4, 4)
    assert esc.inicial[:6] == (4, 0, 3, 5, 6, 5)


def test_verificacion_espacio_completo():
    t = dict(escenarios=0, estados=0, sin_solucion=0, viol_adm_h1=0, viol_adm_h2=0,
             viol_cons_h1=0, viol_cons_h2=0, h2_mayor_h1=0)
    for semilla in range(40):
        esc = _generar_cluster_provisional(semilla, 4, 7, factor=1.15)
        if esc is None:
            continue
        vistos, aristas = espacio_completo(esc)
        hs = costos_optimos(esc, vistos, aristas)
        if esc.inicial not in hs:
            t["sin_solucion"] += 1
            continue
        t["escenarios"] += 1
        t["estados"] += len(vistos)
        for s in vistos:
            if s not in hs:
                continue
            t["viol_adm_h1"] += h1(esc, s) > hs[s]
            t["viol_adm_h2"] += h2(esc, s) > hs[s]
            t["h2_mayor_h1"] += h2(esc, s) > h1(esc, s)
        for a, b, c in aristas:
            if a in hs and b in hs:
                t["viol_cons_h1"] += h1(esc, a) > c + h1(esc, b)
                t["viol_cons_h2"] += h2(esc, a) > c + h2(esc, b)
    assert t == dict(escenarios=40, estados=45690, sin_solucion=0, viol_adm_h1=0,
                     viol_adm_h2=0, viol_cons_h1=0, viol_cons_h2=0, h2_mayor_h1=888)
