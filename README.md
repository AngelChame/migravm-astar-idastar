# MigraVM: migración de máquinas virtuales con A* e IDA*

Planificador de migraciones para vaciar un servidor de un clúster (por ejemplo, para darle mantenimiento) sin que ningún otro servidor exceda su memoria en ningún paso, con el menor costo total: migrar una máquina virtual (VM) cuesta su tamaño en GB. Se plantea como un problema de búsqueda en espacio de estados y se resuelve con costo uniforme, búsqueda voraz, A\* e IDA\*.

Proyecto de la materia de algoritmos de búsqueda, grupo 7-B:

- Ángel Eduardo Chamé Pérez
- Cesar Yair Toledo Villareal

## El problema

| Componente | Definición |
| --- | --- |
| Estado | Tupla `s` donde `s[i]` es el servidor que aloja la VM `i` |
| Meta | Ninguna VM en el servidor X (el que se vacía) |
| Acción | Migrar la VM `i` al servidor `j`, si `j` no es su servidor actual, `j` no es X y la VM cabe en `j` |
| Costo | Tamaño de la VM migrada, en GB (entero ≥ 1) |

Heurísticas, ambas admisibles y consistentes:

- **h1**: suma de los tamaños de las VM que siguen en X.
- **h2**: h1 más el tamaño de la VM más pequeña cuando alguna VM de X no cabe hoy en ningún otro servidor (habrá que mover otra VM antes).

## Estructura

```text
modelo/        estado, acciones, sucesores y validación de planes
heuristicas/   h0, h1 y h2
buscadores/    costo uniforme, voraz, A* e IDA* (con tabla de transposición por iteración)
escenarios/    carga y guarda clústeres en CSV; generador de escenarios no triviales
  datos/       150 escenarios: 30 por tamaño (4x7, 5x10, 6x16, 8x24, 10x32)
medicion/      medición por lotes (nodos, tiempo de CPU, estados guardados, memoria pico)
  resultados/  CSV de la corrida completa y resumen
web/           API (FastAPI) y pantalla para ver los planes paso a paso
reporte/       genera las tablas de resultados en Markdown
pruebas/       pruebas de todos los módulos (pytest)
```

El contrato entre módulos (firmas, formatos de archivo, convenciones de conteo y valores de verificación) está en [`ARQUITECTURA.md`](ARQUITECTURA.md).

## Instalación

Requiere Python 3.10 o superior. Los módulos de búsqueda, escenarios, medición y reporte usan solo la biblioteca estándar; la web y las pruebas necesitan las dependencias de `requirements.txt`.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; en Linux o macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Todos los comandos se corren desde la raíz del repositorio.

## Uso

### Desde Python

```python
from modelo import Escenario
from buscadores import buscar

ejemplo = Escenario(
    capacidades=(6, 6, 6, 6),
    tamanos=(2, 1, 3, 1, 4, 4),
    inicial=(3, 3, 0, 3, 2, 1),
    servidor_a_vaciar=0,
    nombre="ejemplo",
)
resultado = buscar(ejemplo, "astar", "h2")
print(resultado.estado, resultado.costo, resultado.plan)
# resuelto 4 (Accion(vm=1, origen=3, destino=1), Accion(vm=2, origen=0, destino=3))
```

Algoritmos: `"ucs"`, `"voraz"`, `"astar"` e `"ida"`. Heurísticas: `"h1"` y `"h2"` (costo uniforme usa `h0`). Se puede pasar `tope_nodos` para limitar la búsqueda; un caso que llega al tope puede tener solución.

### Pantalla web

```bash
uvicorn web.app:app --reload
```

Abrir <http://127.0.0.1:8000>. Se elige un escenario y un algoritmo, y la pantalla muestra los servidores, el plan paso a paso con g, h1, h2 y f, y una comparación entre algoritmos. Los escenarios de 10×32 no se buscan en vivo: se muestran sus resultados precalculados.

Rutas de la API: `GET /api/escenarios`, `POST /api/buscar`, `POST /api/comparar` y `GET /api/precalculado` (detalle en `ARQUITECTURA.md`, módulo 6).

### Generar escenarios

```bash
python -m escenarios.generar --servidores 8 --vms 24 --cantidad 30 --tope 150000 --salida escenarios/datos
```

Cada clúster queda en una carpeta `{H}x{V}_s{semilla}` con `servidores.csv`, `vms.csv` y `metas.csv` (servidores a vaciar no triviales y su costo óptimo). Un escenario es no trivial si su costo óptimo es mayor que h1 en el estado inicial.

### Medir y generar las tablas

```bash
python -m medicion.correr --tamanos 4x7 5x10 6x16 8x24 10x32 --tope 150000
python -m reporte.generar_tablas
```

El primero escribe `medicion/resultados/mediciones_{tamaño}.csv` y `resumen.csv` (la corrida completa tarda bastante); el segundo escribe [`reporte/tablas_resultados.md`](reporte/tablas_resultados.md) a partir de esos CSV.

### Pruebas

```bash
pytest
```

## Resultados

Mediana de nodos expandidos sobre los casos resueltos, con tope de 150 000 nodos (30 escenarios por tamaño):

| Tamaño | A\* h1 | A\* h2 | IDA\* h2 | A\* h2 / IDA\* h2 |
| --- | --- | --- | --- | --- |
| 4x7 | 12 | 9 | 4 | 2.25 |
| 5x10 | 30 | 17 | 4 | 4.25 |
| 6x16 | 105 | 48.5 | 7.5 | 6.47 |
| 8x24 | 663.5 | 226.5 | 15.5 | 14.61 |
| 10x32 | 1005 | 563 | 72 | 7.82 |

En 10×32, A\* llega al tope en 2 casos con h1 y en 1 con h2; IDA\* resuelve los 30. En 8×24, A\* con h2 guarda hasta 1 860 797 estados contra 142 088 de IDA\* con h2 (13 veces más), y su memoria pico es unas 27 veces mayor. Las tablas completas, con tiempos, memoria y casos que llegaron al tope, están en [`reporte/tablas_resultados.md`](reporte/tablas_resultados.md).
