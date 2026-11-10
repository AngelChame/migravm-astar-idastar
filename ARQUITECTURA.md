# ARQUITECTURA: MigraVM

Contrato entre módulos. Fija nombres, firmas, formatos de archivo, convenciones de conteo y valores de verificación **antes** de escribir el código. Si una firma cambia, se cambia primero este archivo.

## 1. Problema en breve

Un clúster tiene H servidores con capacidad de memoria (GB enteros) y V máquinas virtuales (VM) con tamaño (GB enteros). Hay que vaciar un servidor X migrando VM, sin que ningún servidor supere su capacidad en ningún paso, con el menor costo total, donde migrar una VM cuesta su tamaño en GB.

| Componente | Definición |
| --- | --- |
| Estado | Tupla `s` de largo V; `s[i]` es el servidor que aloja la VM `i` |
| Estado inicial | `Escenario.inicial` |
| Meta | Ninguna VM en X: `all(s[i] != X)` |
| Acción | `Accion(vm, origen, destino)`: válida si `destino != origen`, `destino != X` y `carga(destino) + tamano[vm] <= capacidad[destino]` |
| Costo de una acción | `tamanos[vm]` (entero >= 1) |
| Plan | Secuencia de acciones desde el estado inicial hasta un estado meta, válida en cada paso |

Los índices de servidores y de VM empiezan en 0.

## 2. Estructura del repositorio

```text
migravm-astar-idastar/
  ARQUITECTURA.md
  pytest.ini               # [pytest] pythonpath = .   testpaths = pruebas
  requirements.txt         # pytest; fastapi y uvicorn desde el módulo 6
  modelo/                  # módulo 1
  heuristicas/             # módulo 2
  buscadores/              # módulo 3
  escenarios/              # módulo 4 (código) y escenarios/datos/ (CSV)
  medicion/                # módulo 5 (código) y medicion/resultados/ (CSV)
  web/                     # módulo 6 (API) y web/estatico/ (HTML, CSS, JS)
  pruebas/                 # pruebas de todos los módulos
  reporte/                 # módulo 7
```

Los paquetes se importan desde la raíz del repositorio: `from modelo import Escenario`.

**Dependencias permitidas** (una flecha significa "puede importar"; nada más):

```text
modelo        <- (nada del repositorio)
heuristicas   <- modelo
buscadores    <- modelo, heuristicas
escenarios    <- modelo, heuristicas, buscadores
medicion      <- modelo, heuristicas, buscadores, escenarios
web           <- todos los anteriores
```

## 3. Convenciones generales

- Python 3.10 o superior. Los módulos 1 a 5 usan solo la biblioteca estándar; las pruebas usan `pytest`; la web usa `fastapi` y `uvicorn`.
- Estados, capacidades y tamaños son tuplas de `int`; nunca listas. Los estados son hashables.
- Las funciones de los módulos 1 a 4 son puras: no imprimen, no leen archivos (salvo `escenarios`) y no modifican sus argumentos.
- Identificadores en español, en ASCII y sin acentos (`tamanos`, `iteraciones`).
- Archivos CSV en UTF-8, con `newline=""` al abrirlos, y rutas con `pathlib`.
- Cada módulo se termina con sus pruebas pasando (sección 7).

## 4. Contrato (código)

Estos bloques son la fuente de verdad de nombres y firmas. Los cuerpos `...` los escribe cada módulo. Las pruebas del módulo 0 ejecutan estos bloques para detectar errores de nombre o de tipo.

### Módulo 1: `modelo/`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Mapping, NamedTuple, Optional, Sequence

Estado = tuple[int, ...]  # Estado[i] = servidor que aloja la VM i


class Accion(NamedTuple):
    vm: int
    origen: int
    destino: int


class Sucesor(NamedTuple):
    accion: Accion
    estado: Estado
    costo: int


@dataclass(frozen=True)
class Escenario:
    capacidades: tuple[int, ...]  # largo H, GB
    tamanos: tuple[int, ...]      # largo V, GB, cada uno >= 1
    inicial: Estado               # largo V, valores en 0..H-1
    servidor_a_vaciar: int        # X, en 0..H-1
    nombre: str = ""


class EscenarioInvalido(ValueError):
    """Datos inconsistentes al construir un Escenario."""


class PlanInvalido(ValueError):
    """Un plan viola una regla del problema."""


def validar_escenario(esc: Escenario) -> None: ...
def cargas(esc: Escenario, estado: Estado) -> tuple[int, ...]: ...
def es_meta(esc: Escenario, estado: Estado) -> bool: ...
def costo_accion(esc: Escenario, accion: Accion) -> int: ...
def aplicar(esc: Escenario, estado: Estado, accion: Accion) -> Estado: ...
def sucesores(esc: Escenario, estado: Estado) -> list[Sucesor]: ...
def validar_plan(esc: Escenario, plan: Sequence[Accion]) -> int: ...
def con_servidor_a_vaciar(esc: Escenario, servidor: int) -> Escenario: ...
```

Comportamiento:

- `validar_escenario` lanza `EscenarioInvalido` si: H < 2; algún tamaño o capacidad < 1; `len(inicial) != len(tamanos)`; algún servidor de `inicial` fuera de rango; X fuera de rango; o el estado inicial excede la capacidad de algún servidor. `Escenario` no valida solo; `cargar_escenario` y el generador llaman a `validar_escenario`.
- `aplicar` lanza `ValueError` si la acción no es válida en ese estado o si `accion.origen` no coincide con `estado[accion.vm]`.
- `sucesores` devuelve las acciones válidas **en este orden fijo**: `vm` ascendente y, dentro de cada VM, `destino` ascendente. El orden importa porque determina el desempate y los conteos de nodos (sección 5).
- `validar_plan` devuelve el costo total si el plan es válido y lanza `PlanInvalido` con un mensaje si: alguna acción no es aplicable en su paso (incluye exceder una capacidad o migrar hacia X) o el estado final no es meta. Un plan vacío es válido solo si el estado inicial ya es meta (costo 0).
- `con_servidor_a_vaciar` devuelve una copia del escenario con otro X y lanza `EscenarioInvalido` si `servidor` está fuera de `0..H-1`. No cambia capacidades, tamaños ni estado inicial. El nombre no cambia.

### Módulo 2: `heuristicas/`

```python
Heuristica = Callable[[Escenario, Estado], int]


def h0(esc: Escenario, estado: Estado) -> int: ...
def h1(esc: Escenario, estado: Estado) -> int: ...
def h2(esc: Escenario, estado: Estado) -> int: ...


HEURISTICAS: dict[str, Heuristica] = {}  # "h0", "h1", "h2" -> función
```

Definiciones (`X` es `esc.servidor_a_vaciar`):

- `h0(s) = 0`.
- `h1(s)` = suma de `tamanos[i]` de las VM con `s[i] == X`.
- `h2(s)`: si `h1(s) == 0`, devuelve 0. Si no, sea `libre_max` la mayor memoria libre entre los servidores distintos de X y `m_min` el menor tamaño entre **todas** las VM. Si alguna VM en X tiene tamaño > `libre_max`, devuelve `h1(s) + m_min`; si no, `h1(s)`.
- Las tres devuelven `int`, valen 0 en todo estado meta, son admisibles y consistentes. `h.__name__` es el nombre que usan los resultados.

### Módulo 3: `buscadores/`

```python
EstadoBusqueda = Literal["resuelto", "sin_solucion", "tope"]


@dataclass(frozen=True)
class Resultado:
    algoritmo: str                      # "ucs", "voraz", "astar" o "ida"
    heuristica: str                     # "h0", "h1" o "h2"
    estado: EstadoBusqueda
    costo: Optional[int]                # None si no hay plan
    plan: Optional[tuple[Accion, ...]]  # None si no hay plan
    nodos_expandidos: int
    estados_guardados: int
    iteraciones: Optional[int] = None   # solo IDA*


def costo_uniforme(esc: Escenario, tope_nodos: Optional[int] = None) -> Resultado: ...
def voraz(esc: Escenario, h: Heuristica, tope_nodos: Optional[int] = None) -> Resultado: ...
def a_estrella(esc: Escenario, h: Heuristica, tope_nodos: Optional[int] = None) -> Resultado: ...
def ida_estrella(esc: Escenario, h: Heuristica, tope_nodos: Optional[int] = None,
                 transposicion: bool = True) -> Resultado: ...
def buscar(esc: Escenario, algoritmo: str, heuristica: str = "h2",
           tope_nodos: Optional[int] = None) -> Resultado: ...
```

Comportamiento:

- `buscar` despacha por nombre: `"ucs"` (ignora `heuristica` y reporta `"h0"`), `"voraz"`, `"astar"`, `"ida"`. Un nombre desconocido lanza `ValueError`.
- `estado == "resuelto"`: `plan` es una tupla de acciones que `validar_plan` acepta y `costo` es su costo. `"sin_solucion"`: se agotó la búsqueda sin meta; `plan` y `costo` son `None`. `"tope"`: se alcanzó `tope_nodos`; `plan` y `costo` son `None`.
- A* y costo uniforme son óptimos; IDA* con `h0`, `h1` o `h2` también. Voraz no garantiza optimalidad.
- `transposicion=True` agrega una tabla de transposición **por iteración** a IDA*. No está en las diapositivas de la materia: es un añadido, y no hace falta para resolver; recorta el peor caso.

### Módulo 4: `escenarios/`

```python
COLUMNAS_SERVIDORES = ("servidor", "capacidad")
COLUMNAS_VMS = ("vm", "tamano", "servidor")
COLUMNAS_METAS = ("servidor_a_vaciar", "h1_inicial", "costo_optimo")


def cargar_escenario(directorio: "Path | str", servidor_a_vaciar: int) -> Escenario: ...
def leer_metas(directorio: "Path | str") -> list[tuple[int, int, int]]: ...
def guardar_escenario(esc: Escenario, directorio: "Path | str") -> None: ...
def generar_cluster(semilla: int, n_servidores: int, n_vms: int, factor: float = 1.03,
                    servidor_a_vaciar: int = 0, ocupados: tuple[int, ...] = (0,),
                    max_intentos: int = 4000) -> Optional[Escenario]: ...
def es_no_trivial(esc: Escenario, tope_nodos: int, algoritmo: str = "astar") -> Optional[bool]: ...
def generar_no_triviales(n_servidores: int, n_vms: int, cantidad: int, tope_nodos: int,
                         semilla_inicial: int = 0, factor: float = 1.03,
                         servidores_a_vaciar: tuple[int, ...] = (0, 1, 2),
                         algoritmo: str = "ida") -> list[Escenario]: ...
```

Comportamiento:

- **Formato en disco.** Un clúster es una carpeta con `servidores.csv` (columnas `servidor,capacidad`) y `vms.csv` (columnas `vm,tamano,servidor`). El servidor a vaciar **no** se guarda ahí: lo recibe `cargar_escenario`, para poder vaciar distintos servidores del mismo clúster. `metas.csv` es opcional y lo escribe el generador: una fila por servidor a vaciar que resultó no trivial, con `h1_inicial` y `costo_optimo`. La carpeta de un clúster generado se llama `{H}x{V}_s{semilla}`. `cargar_escenario` le pone al escenario `nombre = "{carpeta}_x{X}"`, donde `carpeta` es el nombre de la carpeta; así, un escenario generado que se guarda en su carpeta se carga igual, nombre incluido. `leer_metas` devuelve las filas de `metas.csv` como tuplas `(servidor_a_vaciar, h1_inicial, costo_optimo)` ordenadas, o una lista vacía si el archivo no existe; un archivo mal formado lanza `EscenarioInvalido`.
- **Generador.** `generar_cluster` usa `random.Random(semilla)` y este orden de sorteos: primero los V tamaños con `randint(1, 4)`; luego, hasta `max_intentos` veces, una asignación con `randrange(H)` por VM. Capacidad de todos los servidores: `int(suma_de_tamanos / (H - 1) * factor) + 1`. Acepta la primera asignación en que ninguna carga supera la capacidad y todos los servidores de `ocupados` tienen carga > 0. Devuelve `None` si no la encuentra. Con los valores por omisión, el resultado es el mismo para la misma semilla.
- **No trivial.** `es_no_trivial` devuelve `True` si el costo óptimo es mayor que `h1(estado inicial)`, `False` si es igual, y `None` si la búsqueda llegó al tope o no hay solución (se descarta el escenario). Con `algoritmo="astar"` usa A* con `h2`; para 10×32 se puede pasar `"ida"`.
- `generar_no_triviales` recorre semillas desde `semilla_inicial` y, para cada clúster generado, prueba cada servidor de `servidores_a_vaciar`. Devuelve `cantidad` escenarios (pares clúster y servidor), con `nombre` de la forma `"{H}x{V}_s{semilla}_x{X}"`. Un clúster cuenta una vez por cada servidor a vaciar que resulte no trivial. `algoritmo` se pasa a `es_no_trivial` y por omisión es `"ida"`: es óptimo como `"astar"` y clasifica igual siempre que ambos resuelvan, y es mucho más rápido. Con tope de 150 000 da el mismo conjunto que `"astar"` en 4×7, 5×10, 6×16 y 8×24; en 10×32, `"astar"` llega al tope en `10x32_s39_x0` y descarta ese caso, que `"ida"` resuelve como no trivial.
- Línea de comandos: `python -m escenarios.generar --servidores 8 --vms 24 --cantidad 30 --tope 150000 --algoritmo ida --salida escenarios/datos`. `--algoritmo` es opcional (por omisión `ida`).

### Módulo 5: `medicion/`

```python
COLUMNAS_MEDICION = (
    "escenario", "servidores", "vms", "servidor_a_vaciar", "algoritmo", "heuristica",
    "estado", "costo", "costo_optimo", "migraciones", "nodos_expandidos",
    "estados_guardados", "iteraciones", "tiempo_cpu_s", "memoria_pico_kb", "tope_nodos",
)


@dataclass(frozen=True)
class Medicion:
    escenario: str
    servidores: int
    vms: int
    servidor_a_vaciar: int
    algoritmo: str
    heuristica: str
    estado: EstadoBusqueda
    costo: Optional[int]
    costo_optimo: Optional[int]
    migraciones: Optional[int]
    nodos_expandidos: int
    estados_guardados: int
    iteraciones: Optional[int]
    tiempo_cpu_s: float
    memoria_pico_kb: Optional[float]
    tope_nodos: Optional[int]


def medir(esc: Escenario, algoritmo: str, heuristica: str = "h2",
          tope_nodos: Optional[int] = None, con_memoria: bool = False,
          tiempo_minimo_s: float = 0.2) -> Medicion: ...
def correr_lote(escenarios: Sequence[Escenario], configuraciones: Sequence[tuple[str, str]],
                tope_nodos: int, con_memoria: bool = False,
                costos_optimos: Optional[Mapping[str, int]] = None,
                tiempo_minimo_s: float = 0.2) -> list[Medicion]: ...
def escribir_csv(mediciones: Sequence[Medicion], ruta: "Path | str") -> None: ...
def resumen_por_algoritmo(mediciones: Sequence[Medicion]) -> list[dict]: ...
```

Comportamiento:

- `medir` acepta los algoritmos de `buscar` (`"ucs"`, `"voraz"`, `"astar"`, `"ida"`) y además `"ida_sin_tabla"`, que llama a `ida_estrella(..., transposicion=False)`; la columna `algoritmo` dice `"ida_sin_tabla"`. `"ida_sin_tabla"` exige `tope_nodos` (lanza `ValueError` si es `None`) porque puede ser exponencial. Un algoritmo desconocido lanza `ValueError`.
- `tiempo_cpu_s` se mide con `time.process_time()` alrededor de la búsqueda. Como en Windows ese reloj avanza en pasos de unos 15.6 ms, la búsqueda se repite hasta acumular `tiempo_minimo_s` y se reporta el promedio por búsqueda; con `tiempo_minimo_s=0` se corre una sola vez. Nodos, costo, plan y `estados_guardados` salen de la primera repetición. `memoria_pico_kb` usa `tracemalloc` y solo se llena si `con_memoria=True`; se corre en una pasada **aparte** de la del tiempo porque `tracemalloc` hace más lenta la ejecución.
- `estados_guardados` viene del `Resultado` y es la medida de memoria que no depende de la herramienta.
- `configuraciones` es una lista de pares `(algoritmo, heuristica)`; las filas salen por escenario y, dentro de cada uno, en el orden de `configuraciones`. `costo_optimo` es un valor por escenario que `correr_lote` repite en todas sus filas (también en las de voraz): si `costos_optimos` (nombre del escenario -> costo) tiene el escenario, se usa ese valor; si no, el costo de cualquier algoritmo óptimo de la corrida que haya resuelto (`"ucs"`, `"astar"`, `"ida"`, `"ida_sin_tabla"`); si ninguno resolvió, `None`. Si dos fuentes no coinciden, lanza `ValueError`.
- `migraciones` es `len(plan)`. Las columnas del CSV son exactamente `COLUMNAS_MEDICION`, en ese orden, y coinciden con los campos de `Medicion`.
- `resumen_por_algoritmo` devuelve una fila por algoritmo y heurística, en orden de primera aparición, con las claves `algoritmo`, `heuristica`, `casos`, `resueltos`, `nodos_mediana` y `nodos_max` (solo resueltos), `tiempo_mediana_s` (solo resueltos), `estados_guardados_max` (todos los casos), `memoria_pico_max_kb` y `casos_con_memoria` (casos con `memoria_pico_kb` medido). Sin resueltos o sin memoria medida, el valor correspondiente es `None`. No agrupa por tamaño: la tabla de cinco tamaños la arma la línea de comandos llamándola una vez por tamaño.

### Módulo 6: `web/`

Aplicación FastAPI en `web/app.py` (objeto `app`). Sirve `web/estatico/` en `/`. Todas las respuestas son JSON.

| Ruta | Entrada | Salida |
| --- | --- | --- |
| `GET /api/escenarios` | | Lista de `{nombre, servidores, vms}` de las carpetas de `escenarios/datos/` |
| `POST /api/buscar` | `{escenario, algoritmo, heuristica, tope_nodos}` | Una solución (ver abajo) |
| `POST /api/comparar` | `{escenario, tope_nodos}` | Lista de soluciones: costo uniforme, voraz, A* con `h1` y `h2`, IDA* con `h2` |
| `GET /api/precalculado` | | Filas de `medicion/resultados/` para los tamaños que no se calculan en vivo |

`escenario` es un objeto `{capacidades, tamanos, inicial, servidor_a_vaciar}` con los mismos nombres y tipos que `Escenario` (listas JSON en lugar de tuplas). La API lo convierte a `Escenario`, llama a `validar_escenario` y responde 422 con el mensaje si es inválido.

Solución:

```json
{
  "algoritmo": "astar", "heuristica": "h2", "estado": "resuelto",
  "costo": 4, "nodos_expandidos": 5, "estados_guardados": 17,
  "iteraciones": null, "tiempo_cpu_s": 0.0004,
  "plan": [
    {"paso": 1, "vm": 1, "origen": 3, "destino": 1, "costo": 1, "cargas_despues": [3, 5, 4, 3]},
    {"paso": 2, "vm": 2, "origen": 0, "destino": 3, "costo": 3, "cargas_despues": [0, 5, 4, 6]}
  ]
}
```

(Los valores de `estados_guardados` y `tiempo_cpu_s` son ilustrativos; el resto es el ejemplo de la sección 6.)

- En vivo se aceptan escenarios de hasta 8 servidores y 24 VM; con más, la API responde 422 y la pantalla muestra los resultados de `/api/precalculado`.
- La búsqueda corre en el servidor con un `tope_nodos` obligatorio (valor por omisión 150 000) y devuelve `estado: "tope"` si lo alcanza.

## 5. Conteo, desempate y orden (fijan los números de verificación)

Los conteos de nodos dependen de estos detalles. Si se cambian, los valores de la sección 6 dejan de coincidir.

- **Orden de sucesores:** `vm` ascendente, luego `destino` ascendente (módulo 1).
- **Frontera de costo uniforme y A\*:** cola de prioridad con la clave `(f, g, contador)`: menor `f`, luego menor `g`, luego el que entró primero. `contador` crece con cada inserción y evita comparar estados. En costo uniforme, `f = g`.
- **Frontera de voraz:** clave `(h, contador)`.
- **A\* y costo uniforme sin conjunto cerrado:** se guarda el mejor `g` por estado; al sacar un nodo con `g` mayor que el guardado se descarta sin contarlo; un sucesor se inserta solo si mejora el `g` guardado. Termina al **sacar** la meta, no al generarla.
- **Voraz:** conjunto de estados vistos; un estado se inserta una sola vez.
- **`nodos_expandidos`:** cantidad de nodos **no meta** a los que se les generaron sucesores. El nodo meta no cuenta. En IDA\*, es el total acumulado de todas las iteraciones. Un nodo cuenta al entrar con `f <= cota`.
- **`tope_nodos`:** si la siguiente expansión superaría el tope, se devuelve `estado = "tope"` y `nodos_expandidos == tope_nodos`.
- **`estados_guardados`:** en costo uniforme y A\*, el número de estados con un `g` guardado al terminar; en voraz, el número de estados vistos; en IDA\*, el mayor tamaño de la tabla de transposición en una iteración (sin transposición, la mayor profundidad del camino actual).
- **IDA\*:** la cota inicial es `h(s0)`; la nueva cota es el menor `f` que excedió la anterior; si no excedió ninguno, no hay solución. Los sucesores se recorren en el orden del módulo 1. Con transposición, un sucesor se omite si la tabla ya tiene un `g` menor o igual para ese estado en la iteración actual. Sin transposición, un sucesor se omite si su estado ya está en el camino actual (de lo contrario IDA\* no termina en escenarios sin solución con ciclos).
- **Sin solución:** si la frontera se vacía (o IDA\* no tiene nuevo `f`), se devuelve `"sin_solucion"`.

## 6. Valores de verificación

### Ejemplo base

4 servidores de 6 GB, X = 0. VM A, B, C, D, E, F de 2, 1, 3, 1, 4 y 4 GB. Estado inicial `(3, 3, 0, 3, 2, 1)`.

```python
ejemplo = Escenario(
    capacidades=(6, 6, 6, 6),
    tamanos=(2, 1, 3, 1, 4, 4),
    inicial=(3, 3, 0, 3, 2, 1),
    servidor_a_vaciar=0,
    nombre="ejemplo",
)
```

| Cantidad | Valor |
| --- | --- |
| `cargas(ejemplo, inicial)` | `(3, 4, 4, 4)` |
| Sucesores del estado inicial | 6, en este orden: `Accion(0,3,1)` y `Accion(0,3,2)` con costo 2; `Accion(1,3,1)` y `Accion(1,3,2)` con costo 1; `Accion(3,3,1)` y `Accion(3,3,2)` con costo 1 |
| `h0`, `h1`, `h2` en el estado inicial | 0, 3, 4 |
| Plan óptimo | `Accion(1,3,1)` y `Accion(2,0,3)`, costo 4 |

| Algoritmo | Costo | Nodos expandidos |
| --- | --- | --- |
| Costo uniforme | 4 | 15 |
| A\* con `h1` | 4 | 5 |
| A\* con `h2` | 4 | 5 |
| IDA\* con `h2` | 4 | 2 (1 iteración) |
| Voraz con `h2` | 5 | 2 |

La regla simple (mover cada VM de X, la mayor primero, a un servidor donde quepa) se atora en este ejemplo porque la VM C no cabe en ningún servidor.

### Caso sin solución

`Escenario(capacidades=(6, 2, 2), tamanos=(3,), inicial=(0,), servidor_a_vaciar=0)`: la VM de 3 GB no cabe en ningún otro servidor. Costo uniforme, voraz, A\* e IDA\* devuelven `"sin_solucion"` con 1 nodo expandido (IDA\* con 1 iteración).

### Heurísticas (módulo 2)

Para las semillas 0 a 39, `generar_cluster(semilla, 4, 7, factor=1.15)` (si devuelve un clúster) se enumera completo: búsqueda en anchura desde `inicial` sin expandir estados meta, y `h*` por Dijkstra sobre el grafo invertido desde los estados meta. Resultado esperado:

| Cantidad | Valor |
| --- | --- |
| Escenarios | 40 |
| Estados | 45 690 |
| Violaciones de admisibilidad, `h1` y `h2` | 0 |
| Violaciones de consistencia, `h1` y `h2` | 0 |
| Estados con `h2 > h1` | 888 |

### Generador (módulo 4)

- `generar_cluster(0, 8, 24)`: capacidad 10 en los 8 servidores; tamaños que empiezan con `(4, 4, 1, 3, 4, 4)`; asignación inicial que empieza con `(4, 0, 3, 5, 6, 5)`.
- Semillas 0 a 59 con 8 servidores, 24 VM, factor 1.03 y X = 0: 60 clústeres, **12 no triviales**. Las primeras son: semilla 0 (óptimo 11, `h1` 10), semilla 2 (óptimo 9, `h1` 8), semilla 4 (óptimo 8, `h1` 6) y semilla 6 (óptimo 9, `h1` 8).
- Las 12 no triviales dan, con tope de 150 000 nodos:

| Algoritmo | Nodos, mediana | Nodos, máximo |
| --- | --- | --- |
| A\* con `h1` | 872 | 45 731 |
| A\* con `h2` | 188.5 | 10 493 |
| IDA\* con `h2` y transposición | 17.5 | 3 365 |
| Voraz con `h2` | 4 | 16 |

### Cobertura de tamaños (módulo 4 y módulo 5)

Cinco tamaños (servidores por VM): 4×7, 5×10, 6×16, 8×24 y 10×32. Al menos 30 escenarios no triviales por tamaño, probando 3 o más servidores a vaciar por clúster. Cada corrida declara su `tope_nodos`.

## 7. Cómo se termina cada módulo

| Módulo | Pruebas que deben pasar |
| --- | --- |
| 1 `modelo/` | Cargas, 6 sucesores en orden, `validar_plan` acepta el plan óptimo del ejemplo (costo 4) y rechaza un plan que migra hacia X, uno que excede una capacidad y uno que no llega a la meta; `validar_escenario` rechaza cada caso inválido listado |
| 2 `heuristicas/` | `h0`, `h1`, `h2` del ejemplo (0, 3, 4); valen 0 en la meta; verificación de la sección 6 con 0 violaciones |
| 3 `buscadores/` | Tabla del ejemplo (costos y nodos); caso sin solución; `tope_nodos=1` en el ejemplo da `"tope"`; todo plan devuelto pasa `validar_plan`; las 12 no triviales de 8×24 reproducen la tabla de la sección 6 |
| 4 `escenarios/` | Guardar y cargar un escenario da el mismo `Escenario`; el generador reproduce la semilla 0 y las 12 no triviales de 60; 30 o más no triviales por tamaño |
| 5 `medicion/` | `medir` y `correr_lote` sobre el ejemplo; el CSV tiene exactamente `COLUMNAS_MEDICION`; tabla comparativa de los cinco tamaños |
| 6 `web/` | Con `TestClient`: `POST /api/buscar` sobre el ejemplo devuelve costo 4 y un plan de 2 pasos; un escenario inválido responde 422; un tamaño mayor que 8×24 responde 422 |

Se corren todas con `pytest` desde la raíz del repositorio.
