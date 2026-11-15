# Especificación · Módulo de cortisol salival

Documento derivado de `_local/cortisol.md` (no versionado). Fija las reglas que implementa
`backend/app/domain/cortisol.py`. Es un módulo **independiente** del óseo: comparte astronauta
(sexo/edad) y se cruza con él solo como aviso.

## Método y fuente

- Inmunoensayo **CLIA/ECLIA** (Roche Elecsys 2010, Salivette) sobre cortisol libre en saliva.
- Referencia matutina combinada (n = 56) de Strewe 2012/2018 y Moser 2026; forma circadiana de
  Egawa 2018 (ELISA, no se mezclan concentraciones); control externo de Vogeser 2017.
- Unidad interna: **µg/dL**. Conversión: `nmol/L ÷ 27,59`.

| Referencia | N | Media | SD | σ_ln | Mediana |
|---|---:|---:|---:|---:|---:|
| Todos | 56 | 0,540 | 0,295 | 0,511 | 0,474 |
| Hombres | 39 | 0,522 | 0,317 | 0,560 | 0,446 |
| Mujeres | 17 | 0,580 | 0,240 | 0,398 | 0,536 |

Ancla nocturna: **0,155 µg/dL**.

## Modelo

```
ln_mediana(h) = ln(med_mañana) + (ln(ancla_noche) − ln(med_mañana)) · (h − 7,5)/(21,5 − 7,5)
z = (ln(valor) − ln(mediana(h))) / σ_ln
percentil = Φ(z)
```

Fuera de 07:30–21:30 la mediana es constante (mañana antes de 07:30; noche después de 21:30 y
antes de 06:00). Esto reproduce la tabla de franjas del documento:

| Franja | Horas | Mediana | Verde | Amarillo | Rojo |
|---|---|---|---|---|---|
| Mañana | 06:00–09:59 | 0,47 | 0,25–0,91 | 0,17–0,25 / 0,91–1,29 | < 0,17 / > 1,29 |
| Mediodía | 10:00–13:59 | 0,33 | ≤ 0,64 | 0,64–0,90 | > 0,90 |
| Tarde | 14:00–18:59 | 0,23 | ≤ 0,45 | 0,45–0,63 | > 0,63 |
| Noche | 19:00–23:59 | 0,16 | ≤ 0,30 | 0,30–0,42 | > 0,42 |
| Madrugada | 00:00–05:59 | 0,16 | ≤ 0,30 | 0,30–0,42 | > 0,42 |

Colores: verde `|z| ≤ 1,28`, amarillo `|z| ≤ 1,96`, rojo `|z| > 1,96`.

## Reglas adicionales

- **Piso del ensayo**: después de las 11:00, un valor < 0,18 µg/dL se marca verde con aviso
  (`assay_floor`), porque el percentil 10 cae bajo lo medible con fiabilidad.
- **Control del fabricante**: p95 de Roche Cortisol II = 0,736 / 0,252 / 0,274 µg/dL
  (mañana / tarde / noche). No cambia el color (`above_manufacturer_p95`).
- **Contraste por sexo**: se recalcula el color con la referencia del sexo; si difiere, el
  resultado es dudoso (`sex_discordant`). El color principal usa la referencia agrupada.
- **Edad**: fuera de 20–55 años se emite advertencia (`age_out_of_range`); no cambia el cálculo.
- **Razón tarde/noche**: con muestras de 14:00–18:59 y 19:00–23:59 del mismo día (las más cercanas
  a 15:30 y 21:00): 1,3–2,0 normal · 2–4 vigilar · >4 elevada · <1,3 sin bajada clara.
- **Basal propio**: con ≥3 muestras de la misma franja se muestra su mediana y el delta % de la
  muestra actual.
- **Cruce con el óseo**: ≥2 muestras no verdes en 14 días (con al menos una nocturna, o ≥3 en
  total) activan `bone_cross_risk` como aviso; no modifica el triage óseo.

## Persistencia y API

Tabla `cortisol_sample`: `measured_at`, `value_ug_dl` (canónico), `input_value`, `input_unit`,
`wake_time`, `mission_phase`, `notes`, `source`, `created_at`.

| Método | Ruta |
|---|---|
| POST | `/api/v1/astronauts/{code}/cortisol` |
| GET | `/api/v1/astronauts/{code}/cortisol?days=` |
| POST | `/api/v1/astronauts/{code}/cortisol/import` (CSV/XLSX/JSON) |

Validación: `0 < valor ≤ 10 µg/dL`, fecha no futura. Las muestras se evalúan al leer; no se guarda
el color, para que el resultado sea reproducible.

## Límites declarados

- La referencia son resúmenes de grupo, no percentiles individuales.
- Solo la mañana tiene media y dispersión publicadas; el resto es interpolación log-lineal.
- Los basales son terrestres; no hay referencia en microgravedad.
- Es tamizaje: un rojo pide repetir y consultar, no diagnóstico.
