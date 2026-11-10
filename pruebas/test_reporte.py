import ast
import sys
from pathlib import Path

from reporte.generar_tablas import SALIDA, generar, main

RAIZ = Path(__file__).resolve().parent.parent


def _filas_de_seccion(texto: str, titulo: str) -> list[list[str]]:
    """Filas (celdas) de las tablas Markdown que siguen al encabezado dado."""
    lineas = texto.splitlines()
    inicio = lineas.index(titulo)
    filas = []
    resto = lineas[inicio + 1:] + [""]
    for linea, siguiente in zip(resto, resto[1:]):
        if linea.startswith("#"):
            break
        es_encabezado = siguiente.startswith("| ---")
        if linea.startswith("| ") and not linea.startswith("| ---") and not es_encabezado:
            filas.append([c.strip() for c in linea.strip("|").split("|")])
    return filas


def test_el_script_corre_y_escribe_el_archivo(tmp_path):
    salida = tmp_path / "tablas.md"
    main(["--salida", str(salida)])
    texto = salida.read_text(encoding="utf-8")
    for seccion in ("## a) Tabla comparativa por tamaño", "## b) Casos que llegaron al tope",
                    "## c) Memoria: A* con h2 contra IDA* con h2 (con tabla)",
                    "## d) Razón entre medianas de nodos expandidos"):
        assert seccion in texto
    for t in ("4x7", "5x10", "6x16", "8x24", "10x32"):
        assert f"### {t} (tope 150000 nodos)" in texto


def test_celdas_conocidas_de_ida_en_8x24():
    filas = _filas_de_seccion(generar(), "### 8x24 (tope 150000 nodos)")
    ida = next(f for f in filas if f[:2] == ["ida", "h2"])
    assert ida[2] == "30 / 30"
    assert ida[3] == "15.5 / 3365"
    assert ida[5] == "142088"
    assert ida[6] == "37370"


def test_no_medido_aparece_como_guion():
    filas = _filas_de_seccion(generar(), "### 10x32 (tope 150000 nodos)")
    astar_h2 = next(f for f in filas if f[:2] == ["astar", "h2"])
    assert astar_h2[2] == "29 / 30" and astar_h2[6] == "–"


def test_topes_memoria_y_razones():
    texto = generar()
    topes = _filas_de_seccion(texto, "## b) Casos que llegaron al tope")
    assert [(f[0], f[1], f[2], f[3]) for f in topes] == [
        ("6x16", "ucs", "h0", "4 / 30"), ("10x32", "astar", "h1", "2 / 30"),
        ("10x32", "astar", "h2", "1 / 30")]
    memoria = _filas_de_seccion(texto, "## c) Memoria: A* con h2 contra IDA* con h2 (con tabla)")
    assert ["8x24", "Estados guardados máx.", "1860797", "142088", "13.10"] in memoria
    assert memoria[1][:4] == ["8x24", "Memoria pico máx. (KB)", "1010000", "37370"]
    razones = _filas_de_seccion(texto, "## d) Razón entre medianas de nodos expandidos")
    assert razones[3][:7] == ["8x24", "663.5", "226.5", "15.5", "2.93", "14.61", "42.81"]


def test_el_archivo_versionado_esta_al_dia():
    assert SALIDA.read_text(encoding="utf-8") == generar()


def test_solo_biblioteca_estandar():
    arbol = ast.parse((RAIZ / "reporte" / "generar_tablas.py").read_text(encoding="utf-8"))
    modulos = {n.module.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.ImportFrom)}
    modulos |= {a.name.split(".")[0] for n in ast.walk(arbol) if isinstance(n, ast.Import)
                for a in n.names}
    assert modulos <= set(sys.stdlib_module_names), modulos - set(sys.stdlib_module_names)
