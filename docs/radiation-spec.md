# Especificación · Módulo de radiación (TEPC)

Derivado de `_local/radiación.md` y construido sobre `_local/data_radiacion.csv`. Sección
independiente: no lee ni escribe datos de los módulos óseo, cortisol o salud mental.

## Datos disponibles

`data_radiacion.csv` es un export ASCII-CDF de **un día** (2018-04-10 23:19 → 2018-04-11 23:19 UTC),
cadencia de 60 s, 1.441 filas, con **solo** `AVG_DOSE_EQV_RATE_uSv/min`. No incluye `DOSE`,
`DOSE_EQ60`, `FLAG`, `LOCATION`, posición ni `TIME_INTERVAL`.

| Estadístico | Valor |
|---|---|
| n | 1.441 |
| P50 | 0,238 µSv/min |
| P95 | 1,175 µSv/min |
| P99 | 12,881 µSv/min |
| Total del día | 0,909 mSv |

Con n = 60 por franja horaria (< 120 del documento), la regla jerárquica deja **un estrato general**
de 1.441 muestras; las 24 franjas se guardan como informativas (`below_min_n: true`).

## Referencia

`app/data/radiation_reference.json`, generado con
`mise run radiation-reference` (`python -m app.scripts.build_radiation_reference`). El generador es
genérico: si el archivo trae `DOSE`, `DOSE_EQ60`, `FLAG`, `LOCATION`, posición o `TIME_INTERVAL`,
produce estratos por región, hora, módulo y época.

Estadísticos en escala logarítmica: P50/P95/P99, `median_ln`, `mad_ln`. La referencia diaria queda
**insuficiente** con un solo día (se necesitan ≥ 30 días completos con cobertura ≥ 80 %).

## Clasificación en tres capas

| Capa | Regla |
|---|---|
| **A · instantánea** | `≤ P95` verde · `P95–P99` amarillo · `> P99` rojo solo si 3 lecturas consecutivas (>60 min de ventana) superan P99; si no, amarillo |
| **B · diaria** | Dosis del día (integración por trapecios, huecos ≤ 60 min) vs P95/P99 diarios; si no hay referencia diaria → insuficiente |
| **C · acumulada** | `F30 = H_30d / 250 mSv` y `F_carrera = (previa + H_misión + proyección) / 600 mSv`; verde < 0,50, amarillo < 0,80, rojo ≥ 0,80 |

- **Color final**: el peor de las capas disponibles; gris si ninguna clasifica.
- `F30` solo se calcula con ≥ 24 h de historial; `F_carrera` requiere dosis previa declarada.
- La proyección usa `H_total / día_de_misión × días_restantes` cuando se informan día y duración.
- `Q̄ = H/D` se muestra cuando se ingresa también la tasa absorbida; se advierte fuera de 1,2–3,5.
- Relleno `-1.0e31` y valores fuera de rango se descartan; entrada válida: 0,001–100 000 µSv/min.

## Persistencia y API

Tabla `radiation_reading`: `measured_at` (UTC), `eq_rate_usv_min`, `dose_rate_ugy_min`, `region`,
`module`, `mission_day`, `planned_days`, `prior_career_msv`, `notes`, `source`.

```
GET  /api/v1/astronauts/{code}/radiation
POST /api/v1/astronauts/{code}/radiation
```

El color se recalcula al leer; no se almacena. `GET /api/v1/meta` expone la referencia, límites y
cortes.

## Límites declarados

- Monitor de área, no dosimetría personal.
- Base de un día: la capa diaria no puede clasificarse y el estrato es general.
- La dosis equivalente del TEPC es una aproximación conservadora a la dosis efectiva.
- Los cortes P95/P99 y las fracciones 0,50/0,80 son valores de diseño, configurables.
- Herramienta de apoyo; las decisiones operativas son de los equipos de vuelo.
