# IMP-001 — M01 Validate & Desurvey

## 1. Identificación

- **Implementation ID:** IMP-001
- **Module:** M01 — Validate & Desurvey
- **Date:** 2026-09-25
- **Group:** UNKNOWN
- **Participants:** UNKNOWN
- **Status:** IN_PROGRESS

---

## 2. Problema minero

Reconstruir la trayectoria espacial de sondajes y ubicar sobre ella observaciones
de survey e intervalos geológicos y analíticos, manteniendo validación y
trazabilidad de los datos fuente.

## 3. Objetivo

Desarrollar progresivamente la carga, validación, desurvey, posicionamiento,
visualización y exportación de datos del release sin modificar los archivos
originales de `data/raw/`.

## 4. Inputs

| Variable | Significado | Unidad | Origen | Obligatorio | Validación |
|---|---|---|---|---|---|
| `release_manifest.json` | Inventario y metadatos del release | No aplica | `data/raw/` | Sí | JSON objeto y lista de archivos |
| Archivos CSV declarados | Datos observados del release | Según `data_dictionary.csv`; celdas vacías son `""` y campos finales ausentes `None` | `data/raw/` | Según manifest | CSV con encabezado único; valores preservados |
| Archivos de texto declarados | Documentación del release | No aplica | `data/raw/` | Según manifest | Lectura UTF-8 |
| `LoadedRelease` | Datos cargados, con procedencia de fila | Según diccionario | `loader.py` | Sí para validator | Reglas estructurales, numéricas y relacionales |
| `collar.csv` + `survey.csv` | Collar XYZ y estaciones MD/azimuth/dip | Coordenadas y MD: m; azimuth/dip: grados | `data/raw/` | Sí para trayectoria | Dominios, duplicados y cobertura; orientación inicial del collar |
| `lithology.csv` | Intervalos `from_m`/`to_m` y códigos litológicos | m | `data/raw/` | Sí para capa litológica | El intervalo debe quedar dentro de trayectoria survey disponible |

## 5. Outputs

| Variable / resultado | Significado | Unidad | Destino |
|---|---|---|---|
| `LoadedRelease` | Manifest, tablas CSV y archivos de texto leídos en memoria | No aplica | Retorno de `load_release` |
| `RawTable` / `SourceRow` | Columnas, valores fuente, archivo y línea física de registro | Sin conversión de unidad | Memoria |
| `ValidationReport` | Resúmenes por regla y hallazgos asociados a filas fuente | No aplica | Retorno de `validate_release` |
| Trayectorias desurveyed | Coordenadas XYZ en estaciones observadas de survey | m | Memoria |
| Intervalos litológicos posicionados | Coordenadas XYZ de inicio y fin por intervalo | m | Memoria |
| Visualizador 3D | HTML interactivo con collars, survey y códigos litológicos | Coordenadas locales del release | `outputs/figures/m01_exploration_3d.html` |

## 6. Supuestos

Los valores CSV se preservan como texto durante la carga y no se reparan. El
desurvey adopta Minimum Curvature entre estaciones consecutivas, orientación
del collar para el inicio, y no extrapola fuera del intervalo survey observado.

## 7. Lógica minera

El loader no altera observaciones. El desurvey deriva coordenadas XYZ desde
collar y survey; positioning evalúa las coordenadas de `from_m` y `to_m` sobre
esa trayectoria; el visualizador representa resultados derivados junto con
collars. Los CSV fuente permanecen sin cambios.

## 8. Diseño computacional

### Módulos / archivos

- `src/m01/loader.py`
- `src/m01/validator.py`
- `src/m01/desurvey.py`
- `src/m01/positioning.py`
- `src/m01/visualizer.py`
- `src/m01/main.py`
- `tests/test_loader.py`
- `tests/test_validator.py`
- `tests/test_desurvey.py`
- `tests/test_visualizer.py`

### Funciones / clases principales

- `load_release(raw_dir)`: carga todos los archivos enumerados en
  `release_manifest.json`.
- `validate_release(release, config)`: evalúa estructura, valores, rangos
  derivados de convenciones aprobadas, identificadores, relaciones, intervalos,
  assay y density.
- `calculate_trajectory(collar, survey_rows)`: calcula XYZ en estaciones de
  survey mediante Minimum Curvature desde la orientación de collar.
- `position_at_md(trajectory, measured_depth)`: posiciona una profundidad
  dentro de la trayectoria sin extrapolar.
- `position_intervals(...)`: calcula XYZ de extremos de intervalos.
- `create_exploration_figure(...)`: arma capas Plotly con XYZ precomputados.
- `write_exploration_html(...)`: escribe HTML interactivo autocontenido.
- `build_release_visualization(release, output_path)`: conecta datos cargados,
  desurvey, posicionamiento de litología y visualización.
- `LoadedRelease`, `RawTable`, `SourceRow`: estructuras de datos de salida.
- `ValidationConfig`, `ValidationReport`, `RuleSummary`,
  `ValidationFinding`: configuración explícita y resultados de validación.
- `TopographySurface`: malla topográfica triangulada de entrada.
- `ReleaseLoadError`: error explícito de lectura o estructura básica.

### Dependencias relevantes

- Solo biblioteca estándar de Python (`csv`, `json`, `pathlib`, `dataclasses`,
  `typing`, `decimal`, `collections`, `math`) y Plotly para visualización.

## 9. Etapas de implementación

### Etapa 1 — 2026-09-25

- **Objetivo:** Definir el alcance inicial y revisar el estado real del proyecto.
- **Trabajo realizado:** Confirmado que `src/` y `tests/` no tenían módulos; no
  existe previamente un registro IMP-001. Revisados manifest, diccionario y
  archivos de datos.
- **Resultado:** Contrato inicial del loader preserva texto y procedencia de
  filas; `alteration.csv` con encabezado y cero registros es válido.
- **Pendiente:** Implementar validator y demás componentes de M01.

### Etapa 2 — 2026-09-25

- **Objetivo:** Implementar y probar la carga de los archivos declarados.
- **Trabajo realizado:** Añadido `loader.py` y pruebas unitarias de valores
  preservados, archivo CSV vacío con encabezado, campo final ausente, archivo
  declarado faltante, encabezados duplicados y campos extra.
- **Resultado:** `python -m unittest discover -s tests -p 'test_loader.py' -v`
  ejecutó 5 pruebas; 5 pasaron y 0 fallaron. La carga del release `DS02`
  encontró 54 collars, 385 surveys, 153 intervalos litológicos, 0 intervalos
  de alteración, 8.002 assays, 630 muestras de densidad y 54 filas del
  diccionario. `README.md` se cargó como texto.
- **Pendiente:** Implementar validator y demás componentes de M01.

### Etapa 3 — 2026-09-26

- **Objetivo:** Implementar controles de validación reproducibles para el
  release cargado.
- **Trabajo realizado:** Añadido `validator.py` y pruebas unitarias para
  duplicados de survey, relaciones de sondajes, intervalos, leyes negativas,
  ceros descriptivos y tolerancias configurables.
- **Resultado:** `python -m unittest discover -s tests -v` ejecutó 12 pruebas;
  12 pasaron y 0 fallaron. En `DS02`, `validate_release` generó 38 resúmenes:
  30 `PASS`, 5 `NOT_IMPLEMENTED` y 3 `INFO`; registró 16.580 findings `INFO`.
  Las reglas dependientes de límites o tolerancias permanecen
  `NOT_IMPLEMENTED` cuando no se proporcionan.
- **Pendiente:** Obtener aprobación de tolerancias y validar los métodos
  geométricos de desurvey y posicionamiento.

### Etapa 4 — 2026-09-26

- **Objetivo:** Visualizar capas 3D ya calculadas y disponibles en el pipeline.
- **Trabajo realizado:** Añadidos `visualizer.py` y pruebas para capas
  topográficas trianguladas, collars, trayectorias por MD e intervalos con
  color categórico o numérico. Declarada la dependencia Plotly.
- **Resultado:** La suite completa ejecutó 16 pruebas; 16 pasaron y 0
  fallaron. Generado `outputs/figures/m01_exploration_3d.html` como HTML
  autocontenido con Plotly incrustado, usando los 54 collars cargados del
  release. No se añadieron topografía, trayectorias ni intervalos porque el
  pipeline todavía no proporciona esas capas XYZ calculadas.
- **Pendiente:** Integrar trayectorias e intervalos cuando desurvey y
  positioning produzcan sus coordenadas XYZ.

### Etapa 5 — 2026-09-27

- **Objetivo:** Ajustar la presentación del visualizador a la referencia
  proporcionada y regenerar el HTML con datos del release.
- **Trabajo realizado:** Se añadieron etiquetas visibles de `hole_id`, detalles
  de collar en los tooltips y un estilo de escena claro con nota explícita de
  coordenadas locales sin CRS/EPSG. Se corrigió la generación de intervalos
  numéricos para que cada registro genere su propio segmento.
- **Resultado:** La suite del visualizador ejecutó 5 pruebas; 5 pasaron y 0
  fallaron. El HTML se genera con los 54 collars del release.
- **Limitación:** No existen salidas XYZ de desurvey/positioning ni una
  superficie topográfica triangulada disponible; por ello no se muestran
  trayectorias medidas ni intervalos 3D.

### Etapa 6 — 2026-09-27

- **Objetivo:** Añadir una proyección ilustrativa de los sondajes a partir de
  los datos de orientación y profundidad disponibles en collar.
- **Trabajo realizado:** Se incorporó una línea recta desde cada collar usando
  `azimuth_deg`, `dip_deg` y `final_depth_m`. La vista identifica la línea como
  proyección ilustrativa de orientación constante, diferenciándola de survey
  medido y de una trayectoria calculada por desurvey. Los archivos fuente se
  consumen sin modificación.
- **Resultado:** Suite del visualizador: 7 pruebas pasaron; 0 fallaron. HTML
  regenerado con las proyecciones de los collars que contienen las variables
  requeridas.
- **Limitación:** La proyección no incorpora curvatura observada en las
  estaciones de `survey.csv`; no representa una trayectoria surveyed ni un
  resultado de Minimum Curvature.

### Etapa 7 — 2026-09-27

- **Objetivo:** Generar el visualizador con las capas Survey y Litología
  posicionadas usando las tablas observadas del release.
- **Trabajo realizado:** Añadidos `desurvey.py`, `positioning.py` y el
  integrador `main.py`. Se calculan las coordenadas de survey con Minimum
  Curvature, se posicionan los extremos de los intervalos litológicos sobre la
  trayectoria y se representan como capas diferenciadas de collars, Survey y
  códigos de litología. Se rechazan duplicados contradictorios y no se
  extrapola fuera de estaciones observadas.
- **Resultado:** Se ejecutaron 25 pruebas; 25 pasaron y 0 fallaron. El release
  contiene 54 collars, 385 registros survey y 153 intervalos litológicos; se
  regeneró el HTML autocontenido con dichas capas. La superficie topográfica
  no se muestra porque no existe en los archivos del release.

## 10. Decisiones

### Decisiones de convenciones registradas antes de esta etapa

- **Orientación inicial:** La posición y orientación de inicio provienen del
  collar; survey en MD=0 se compara como control.
- **Desurvey:** Método seleccionado para la etapa correspondiente: Minimum
  Curvature.
- **CRS/EPSG (DECISION-06):** ausencia de código CRS/EPSG no bloquea M01; se
  trabaja en coordenadas locales y no se afirma ubicación global ni
  transformación a otro CRS.
- **Survey duplicado idéntico:** `WARNING`; para cálculos posteriores se usará
  una sola estación equivalente en memoria, sin modificar el dato fuente.
- **Survey duplicado contradictorio:** `ERROR`.
- **Survey incompleto:** no inventar estaciones.
- **Más allá del último survey:** no extrapolar sin aprobación explícita.
- **Intervalo fuera de trayectoria disponible:** `ERROR` y no generar XYZ.

### Decisiones de implementación

- Los valores de celdas se conservan como cadenas; celdas vacías quedan `""` y
  campos finales ausentes quedan `None`.
- Una fila con más campos que el encabezado es error explícito de carga.
- El loader procesa los archivos que enumera el manifest; no modifica datos
  fuente.
- Los umbrales de comparación angular collar-survey y diferencia de longitud
  se suministran explícitamente en `ValidationConfig`; no se infieren.
- `ValidationConfig` clasifica discrepancias collar-survey como `WARNING` si
  exceden el umbral de warning y como `ERROR` si exceden el umbral de error.
- Los cambios angulares entre estaciones y los límites de plausibilidad de
  density no se rechazan sin umbrales aprobados.
- Los valores cero en assay se reportan como `INFO`, sin asignarles semántica.
- Los ceros de densidad y densidades negativas se consideran `ERROR`; no se
  configura un rango superior de plausibilidad sin referencia documentada.

## 11. Archivos creados o modificados

```text
src/m01/__init__.py
src/m01/desurvey.py
src/m01/main.py
src/m01/positioning.py
src/m01/loader.py
src/m01/validator.py
src/m01/visualizer.py
tests/test_desurvey.py
tests/test_loader.py
tests/test_validator.py
tests/test_visualizer.py
docs/implementation/IMP-001_m01_validate_desurvey.md
requirements.txt
outputs/figures/m01_exploration_3d.html
```

## 12. Pruebas realizadas

### Comandos ejecutados

```text
python -m unittest discover -s tests -p 'test_loader.py' -v
python -c "from pathlib import Path; from src.m01.loader import load_release; r=load_release(Path('data/raw')); ..."
python -m unittest discover -s tests -v
python -c "from pathlib import Path; from src.m01.loader import load_release; from src.m01.validator import validate_release; r=validate_release(load_release(Path('data/raw'))); ..."
python -m unittest discover -s tests -p 'test_visualizer.py' -v
python -c "from pathlib import Path; from src.m01.loader import load_release; from src.m01.visualizer import write_exploration_html; r=load_release(Path('data/raw')); write_exploration_html(collars=[row.values for row in r.tables['collar.csv'].rows])"
python -m src.m01.main --raw-dir data/raw
```

### Resultado real

- **Status:** PASS
- **Tests passed:** 24
- **Tests failed:** 0

## 13. Validación minera

- [ ] Unidades consistentes.
- [ ] Signos económicos correctos cuando corresponda.
- [ ] Magnitudes razonables.
- [ ] Restricciones operacionales respetadas.
- [ ] Casos extremos revisados.
- [ ] Caso manual independiente revisado cuando es posible.

### Evidencia / comentario

El loader no interpreta valores ni realiza cálculos mineros. Las convenciones
espaciales se aplicarán en el módulo de desurvey. El validator comprueba dominios
angulares establecidos por las convenciones disponibles, pero la comparación
collar-survey necesita tolerancias configuradas. Las diferencias de longitud de
intervalo también requieren tolerancia explícita.

En la ejecución sobre el release DS02, los 16.580 findings `INFO` corresponden a
576 gaps internos entre intervalos y 8.002 ceros en `mo_pct` y 8.002 ceros en
`au_gt`. Esto registra observaciones del archivo sin asignarles interpretación.

El módulo Plotly consume capas XYZ ya preparadas. El integrador ejecuta el
desurvey y posicionamiento antes de llamar al visualizador. La proyección recta
de collar queda como alternativa ilustrativa solo cuando no se entrega una
trayectoria surveyed.

## 14. Limitaciones y pendientes

### LIMITATION-01

El loader no valida dominios numéricos ni relaciones entre tablas; esa
responsabilidad corresponde a `validator.py`. Los límites de plausibilidad de
density, los cambios angulares anómalos, la tolerancia collar-survey y la
tolerancia de longitud quedan sin criterio aprobado. Los controles configurables
requieren que el llamador provea tolerancias aprobadas para abandonar
`NOT_IMPLEMENTED`.

### FUTURE-01

Incorporar exportación de datos procesados y una superficie topográfica cuando
se disponga de fuentes y criterios definidos.

### LIMITATION-02

No hay datos de topografía en el release, por lo que el visualizador no puede
representar esa superficie.

### LIMITATION-03

El Minimum Curvature representa la trayectoria entre estaciones mediante un
arco de curvatura constante. No se crean estaciones adicionales en los datos
fuente y no se extiende la trayectoria más allá de la última estación medida.

## 15. Uso del agente de IA

- [x] Explicación conceptual.
- [x] Arquitectura.
- [ ] Algoritmo.
- [x] Implementación.
- [x] Pruebas.
- [ ] Depuración.
- [ ] Revisión de unidades.
- [x] Documentación.

Comentario: apoyo en la definición y construcción inicial del loader y sus
pruebas unitarias.

## 16. Checklist de cierre

- [x] Problema minero documentado.
- [x] Inputs documentados para la etapa del loader.
- [ ] Unidades verificadas.
- [x] Supuestos identificados.
- [ ] Lógica minera documentada.
- [ ] Implementación terminada.
- [x] Pruebas ejecutadas para loader y validator.
- [x] Validación computacional de loader y validator realizada.
- [ ] Validación minera realizada.
- [x] Archivos modificados registrados.
- [x] Limitaciones registradas.
- [x] Registro actualizado.

**M01 permanece IN_PROGRESS.**
