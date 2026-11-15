# Especificación de dominio · Monitoreo óseo SCAN

Documento de trabajo derivado de `_local/NASA SPACE.docx` (no versionado). Fija las reglas que el
código implementa; si una regla cambia, cambia aquí y en `backend/app/domain/bone.py`.

## Contexto

En misiones de larga duración la microgravedad produce pérdida de masa ósea del **1–2 % mensual**,
con foco en hueso trabecular (cuello femoral y calcáneo). A bordo no hay DXA, así que se propone un
esquema híbrido:

- **Tierra**: DXA como estándar de oro antes y después del vuelo.
- **Vuelo**: SCAN como seguimiento longitudinal no invasivo de alta resolución temporal.

## Parámetros

| Sigla | Nombre | Unidad | Rol |
| --- | --- | --- | --- |
| BUA | Atenuación de ultrasonido de banda ancha | dB/MHz | indicador principal; refleja porosidad trabecular (r = 0.82) |
| UV | Velocidad del ultrasonido | m/s | se correlaciona con elasticidad y densidad aparente |
| ATT | Coeficiente de atenuación | dB/cm | pérdida total de energía; se registra, no puntúa |
| BV/TV | Fracción volumétrica ósea predicha | adimensional | estimada por regresión |

## Modelo

```
BV/TV = 3.89e-4 · UV − 9e-4 · BUA − 0.456
```

Correlación reportada con BV/TV medida: r = 0.92. Es una regresión ajustada: **no se extrapola**
fuera del dominio de captura.

Rangos aceptados:

| Variable | Rango |
| --- | --- |
| BUA | `0 < BUA < 200` dB/MHz |
| UV | `1200 ≤ UV ≤ 2000` m/s |
| ATT | `0 < ATT < 200` dB/cm |

Un UV de `1.5` (km/s) produce un BV/TV negativo: por eso la API responde 422 en vez de calcular.

## Serie y línea base

- La **primera medición** de cada astronauta por sitio es la línea base (día 0).
- `pérdida acumulada (%) = (BUA_base − BUA_actual) / BUA_base · 100`.
- `tasa (%/mes) = pérdida acumulada / meses desde la línea base`, solo si han pasado ≥ 0.1 mes.
- La fecha de cada sesión debe ser estrictamente posterior a la línea base.

## Triage

| Nivel | Criterio | Acción |
| --- | --- | --- |
| 1 · Normal | tasa < 0.8 %/mes | mantener protocolo |
| 2 · Riesgo | 0.8 ≤ tasa ≤ 1.5 %/mes | aumentar carga de ejercicio |
| 3 · Alerta | tasa > 1.5 %/mes **o** acumulada > 3 % | revisión clínica |

La pérdida acumulada de 3 % se acerca al límite superior observado en calcáneo (2.9 % ± 1.0 % en
4–6 meses, n = 29).

## Referencia poblacional

Cada medición se contrasta con el grupo etario y sexual del astronauta (Shin et al., 2005):
`Z = (valor − media)/DE` y `T = (valor − media joven)/DE joven`. Clasificación OMS por T:
normal > −1,0; osteopenia −2,5 a −1,0; osteoporosis ≤ −2,5. El resultado incluye media ± DE,
Z, T y estado, y se muestra junto al nivel de triage (estado vs. velocidad de pérdida).

La tabla de 12 grupos vive en `backend/app/data/reference_ultrasound.json` y se regenera desde
`_local/Ultrasonido.xlsx` con `mise run reference` (o
`uv run python -m app.scripts.build_reference`). La fuente es una población coreana de 3.053
adultos: es una referencia, no un diagnóstico.

## Decisiones de implementación

1. El nivel se calcula sobre **BUA**, tal como define la fuente. BV/TV se reporta como métrica
   secundaria (con su propia pérdida acumulada) pero no altera el nivel.
2. ATT se conserva para trazabilidad y análisis posterior; hoy no participa del triage.
3. Con una sola medición no hay tasa ni nivel: la UI muestra "línea base" y no pinta alerta.
4. Cada evaluación se deriva de la serie completa, de modo que recalcular es determinista y
   reproducible (`model_version = scan-2013-v1`).

## Referencias

- <https://doi.org/10.1117/12.810048>
- <https://doi.org/10.1016/j.actaastro.2012.08.032>
- <https://doi.org/10.1121/1.4784949>
