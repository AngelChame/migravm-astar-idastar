# Tablas de resultados

Generado por `reporte/generar_tablas.py` a partir de `medicion/resultados/` (`resumen.csv` y `mediciones_*.csv`). No editar a mano: volver a correr el script. – = no medido o sin casos resueltos.

## a) Tabla comparativa por tamaño

### 4x7 (tope 150000 nodos)

| Algoritmo | Heurística | Resueltos / casos | Nodos (mediana / máx.) | Tiempo mediano (s) | Estados guardados máx. | Memoria pico máx. (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| ucs | h0 | 30 / 30 | 70 / 249 | 0.001142 | 716 | 154.1 |
| voraz | h2 | 30 / 30 | 3 / 5 | 0.0001014 | 31 | 6.859 |
| astar | h1 | 30 / 30 | 12 / 45 | 0.000217 | 153 | 22.22 |
| astar | h2 | 30 / 30 | 9 / 38 | 0.0002552 | 135 | 21.07 |
| ida | h2 | 30 / 30 | 4 / 65 | 0.000115 | 51 | 8.688 |
| ida_sin_tabla | h2 | 30 / 30 | 4 / 142 | 0.0001208 | 4 | 7.539 |

### 5x10 (tope 150000 nodos)

| Algoritmo | Heurística | Resueltos / casos | Nodos (mediana / máx.) | Tiempo mediano (s) | Estados guardados máx. | Memoria pico máx. (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| ucs | h0 | 30 / 30 | 574 / 2892 | 0.01693 | 11165 | 4557 |
| voraz | h2 | 30 / 30 | 3 / 31 | 0.0001907 | 79 | 11.73 |
| astar | h1 | 30 / 30 | 30 / 297 | 0.00103 | 1554 | 316.7 |
| astar | h2 | 30 / 30 | 17 / 218 | 0.0008444 | 871 | 156.1 |
| ida | h2 | 30 / 30 | 4 / 253 | 0.0001998 | 362 | 40.25 |
| ida_sin_tabla | h2 | 30 / 30 | 4 / 1569 | 0.0001966 | 5 | 15.15 |

### 6x16 (tope 150000 nodos)

| Algoritmo | Heurística | Resueltos / casos | Nodos (mediana / máx.) | Tiempo mediano (s) | Estados guardados máx. | Memoria pico máx. (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| ucs | h0 | 26 / 30 | 13439 / 126568 | 0.9062 | 1705874 | – |
| voraz | h2 | 30 / 30 | 3 / 5 | 0.0004373 | 105 | 20.91 |
| astar | h1 | 30 / 30 | 105 / 1713 | 0.007859 | 21826 | 9020 |
| astar | h2 | 30 / 30 | 48.5 / 586 | 0.006579 | 7044 | 2720 |
| ida | h2 | 30 / 30 | 7.5 / 198 | 0.0009241 | 1825 | 123.1 |
| ida_sin_tabla | h2 | 30 / 30 | 7.5 / 312 | 0.0009431 | 5 | 25.23 |

### 8x24 (tope 150000 nodos)

| Algoritmo | Heurística | Resueltos / casos | Nodos (mediana / máx.) | Tiempo mediano (s) | Estados guardados máx. | Memoria pico máx. (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| voraz | h2 | 30 / 30 | 4 / 16 | 0.001199 | 477 | 192 |
| astar | h1 | 30 / 30 | 663.5 / 143282 | 0.1055 | 4779032 | – |
| astar | h2 | 30 / 30 | 226.5 / 47644 | 0.05859 | 1860797 | 1010000 |
| ida | h2 | 30 / 30 | 15.5 / 3365 | 0.004895 | 142088 | 37370 |
| ida_sin_tabla | h2 | 30 / 30 | 15.5 / 16346 | 0.00478 | 6 | – |

### 10x32 (tope 150000 nodos)

| Algoritmo | Heurística | Resueltos / casos | Nodos (mediana / máx.) | Tiempo mediano (s) | Estados guardados máx. | Memoria pico máx. (KB) |
| --- | --- | --- | --- | --- | --- | --- |
| voraz | h2 | 30 / 30 | 4 / 11 | 0.002555 | 649 | 290.9 |
| astar | h1 | 28 / 30 | 1005 / 100607 | 0.3125 | 4873508 | – |
| astar | h2 | 29 / 30 | 563 / 89617 | 0.3281 | 5463410 | – |
| ida | h2 | 30 / 30 | 72 / 14719 | 0.05273 | 440424 | 147900 |
| ida_sin_tabla | h2 | 30 / 30 | 76.5 / 73488 | 0.05664 | 6 | – |

## b) Casos que llegaron al tope

| Tamaño | Algoritmo | Heurística | Topes / casos | Tope (nodos) | Escenarios |
| --- | --- | --- | --- | --- | --- |
| 6x16 | ucs | h0 | 4 / 30 | 150000 | 6x16_s25_x2, 6x16_s37_x2, 6x16_s45_x1, 6x16_s59_x1 |
| 10x32 | astar | h1 | 2 / 30 | 150000 | 10x32_s39_x0, 10x32_s39_x2 |
| 10x32 | astar | h2 | 1 / 30 | 150000 | 10x32_s39_x0 |

## c) Memoria: A* con h2 contra IDA* con h2 (con tabla)

| Tamaño | Medida | A* h2 | IDA* h2 | Razón A* / IDA* |
| --- | --- | --- | --- | --- |
| 8x24 | Estados guardados máx. | 1860797 | 142088 | 13.10 |
| 8x24 | Memoria pico máx. (KB) | 1010000 | 37370 | 27.02 |
| 10x32 | Estados guardados máx. | 5463410 | 440424 | 12.40 |

## d) Razón entre medianas de nodos expandidos

| Tamaño | A* h1 | A* h2 | IDA* h2 | A* h1 / A* h2 | A* h2 / IDA* h2 | A* h1 / IDA* h2 | Resueltos (A* h1 / A* h2 / IDA* h2) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4x7 | 12 | 9 | 4 | 1.33 | 2.25 | 3.00 | 30 / 30 / 30 |
| 5x10 | 30 | 17 | 4 | 1.76 | 4.25 | 7.50 | 30 / 30 / 30 |
| 6x16 | 105 | 48.5 | 7.5 | 2.16 | 6.47 | 14.00 | 30 / 30 / 30 |
| 8x24 | 663.5 | 226.5 | 15.5 | 2.93 | 14.61 | 42.81 | 30 / 30 / 30 |
| 10x32 | 1005 | 563 | 72 | 1.79 | 7.82 | 13.96 | 28 / 29 / 30 |

Medianas sobre los casos resueltos de cada configuración.
