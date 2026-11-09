from dataclasses import replace

import pytest

from modelo import (
    Accion,
    Escenario,
    EscenarioInvalido,
    PlanInvalido,
    Sucesor,
    aplicar,
    cargas,
    con_servidor_a_vaciar,
    costo_accion,
    es_meta,
    sucesores,
    validar_escenario,
    validar_plan,
)

EJEMPLO = Escenario(
    capacidades=(6, 6, 6, 6),
    tamanos=(2, 1, 3, 1, 4, 4),
    inicial=(3, 3, 0, 3, 2, 1),
    servidor_a_vaciar=0,
    nombre="ejemplo",
)


def test_ejemplo_es_valido():
    validar_escenario(EJEMPLO)


def test_cargas_del_ejemplo():
    assert cargas(EJEMPLO, EJEMPLO.inicial) == (3, 4, 4, 4)


def test_seis_sucesores_en_orden():
    esperado = [
        (Accion(0, 3, 1), 2),
        (Accion(0, 3, 2), 2),
        (Accion(1, 3, 1), 1),
        (Accion(1, 3, 2), 1),
        (Accion(3, 3, 1), 1),
        (Accion(3, 3, 2), 1),
    ]
    obtenidos = sucesores(EJEMPLO, EJEMPLO.inicial)
    assert [(s.accion, s.costo) for s in obtenidos] == esperado
    for s in obtenidos:
        assert isinstance(s, Sucesor)
        assert isinstance(s.estado, tuple)
        assert s.estado == aplicar(EJEMPLO, EJEMPLO.inicial, s.accion)


def test_es_meta_y_costo_accion():
    assert not es_meta(EJEMPLO, EJEMPLO.inicial)
    assert es_meta(EJEMPLO, (3, 1, 3, 3, 2, 1))
    assert costo_accion(EJEMPLO, Accion(2, 0, 3)) == 3


def test_aplicar_no_modifica_argumentos():
    inicial = EJEMPLO.inicial
    nuevo = aplicar(EJEMPLO, inicial, Accion(1, 3, 1))
    assert nuevo == (3, 1, 0, 3, 2, 1)
    assert inicial == (3, 3, 0, 3, 2, 1)
    assert isinstance(nuevo, tuple)


@pytest.mark.parametrize(
    "accion",
    [
        Accion(1, 2, 1),  # origen no coincide
        Accion(1, 3, 3),  # destino igual al origen
        Accion(1, 3, 0),  # destino es X
        Accion(2, 0, 1),  # excede la capacidad
        Accion(9, 3, 1),  # VM inexistente
        Accion(1, 3, 7),  # servidor inexistente
    ],
)
def test_aplicar_rechaza_acciones_invalidas(accion):
    with pytest.raises(ValueError):
        aplicar(EJEMPLO, EJEMPLO.inicial, accion)


def test_validar_plan_acepta_el_optimo():
    assert validar_plan(EJEMPLO, [Accion(1, 3, 1), Accion(2, 0, 3)]) == 4


@pytest.mark.parametrize(
    "plan",
    [
        [Accion(1, 3, 0)],                    # migra hacia X
        [Accion(2, 0, 1)],                    # excede una capacidad
        [Accion(1, 3, 1)],                    # no llega a la meta
        [Accion(1, 2, 1), Accion(2, 0, 3)],   # origen no coincide
        [],                                   # vacio y el inicial no es meta
    ],
)
def test_validar_plan_rechaza_planes_invalidos(plan):
    with pytest.raises(PlanInvalido):
        validar_plan(EJEMPLO, plan)


def test_plan_vacio_valido_si_el_inicial_es_meta():
    esc = replace(EJEMPLO, inicial=(3, 1, 3, 3, 2, 1))
    assert validar_plan(esc, []) == 0


@pytest.mark.parametrize(
    "cambios",
    [
        {"capacidades": (6,), "inicial": (0, 0, 0, 0, 0, 0), "tamanos": (1, 1, 1, 1, 1, 1)},
        {"tamanos": (2, 0, 3, 1, 4, 4)},
        {"capacidades": (6, 6, 0, 6)},
        {"inicial": (3, 3, 0, 3, 2)},
        {"inicial": (3, 3, 0, 3, 2, 4)},
        {"inicial": (3, 3, 0, 3, 2, -1)},
        {"servidor_a_vaciar": 4},
        {"servidor_a_vaciar": -1},
        {"inicial": (3, 3, 0, 3, 3, 1)},
    ],
    ids=[
        "menos_de_2_servidores",
        "tamano_menor_a_1",
        "capacidad_menor_a_1",
        "largos_distintos",
        "servidor_inicial_mayor",
        "servidor_inicial_negativo",
        "x_mayor",
        "x_negativo",
        "inicial_excede_capacidad",
    ],
)
def test_validar_escenario_rechaza_invalidos(cambios):
    with pytest.raises(EscenarioInvalido):
        validar_escenario(replace(EJEMPLO, **cambios))


def test_con_servidor_a_vaciar():
    otro = con_servidor_a_vaciar(EJEMPLO, 3)
    assert otro.servidor_a_vaciar == 3
    assert otro.inicial == EJEMPLO.inicial
    assert EJEMPLO.servidor_a_vaciar == 0
    with pytest.raises(EscenarioInvalido):
        con_servidor_a_vaciar(EJEMPLO, 4)
