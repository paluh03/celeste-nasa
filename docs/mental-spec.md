# Especificación · Módulo de salud mental

Derivado de `_local/mental.md`, limitado a la parte psicométrica (NASA-TLX + DMRS + ALI). El
subsistema de dosimetría TLD/CR-39 de ese documento **no** se implementa: la radiación tiene su
propio módulo con datos TEPC. Sección independiente, sin lecturas ni escrituras en otras tablas.

## Entradas

**NASA-TLX por tarea** (K tareas por día):

- 6 dimensiones 0–100 en pasos de 5: `MD`, `PD`, `TD`, `OP` (invertida), `EF`, `FR`.
- `WEIGHTED_FULL`: contadores `T_i` enteros 0–5 con suma exacta **15** → `W_i = T_i/15`.
- `RAW_FAST`: `W_i = 1/6`.
- `Overall = Σ R_i·W_i`.
- `WL_day = Σ(Overall_k·D_k) / Σ D_k` (ponderada por duración en minutos).

**DMRS diario** (8 ítems 0–10):

```
PA  = (M1+M2+M3+M4)/40 · 100
NA  = (M5+M6+M7+M8)/40 · 100
DMRS = 10 · [0,15·M1 + 0,15·M2 + 0,10·M3 + 0,10·M4
           + 0,15·(10−M5) + 0,10·(10−M6) + 0,15·(10−M7) + 0,10·(10−M8)]
```

## Curva longitudinal

```
EWMA_WL(t)   = 0,35·WL_day + 0,65·EWMA_WL(t−1)
EWMA_Mood(t) = 0,35·DMRS   + 0,65·EWMA_Mood(t−1)
Z_DMRS(t)    = (DMRS − μ_7d) / max(σ_7d, 5)
ALI(t)       = 0,55·EWMA_WL + 0,45·(100 − EWMA_Mood)
               +8 si M1 ≤ 3 dos días consecutivos (tope 100)
```

Con menos de 3 días previos se usan `μ_WL = 50`, `μ_DMRS = 75`, `σ = 5`.

## Zonas (orden jerárquico)

| Zona | Condición | Protocolo |
|---|---|---|
| 🔴 Roja (4) | `ALI ≥ 65` ∨ `DMRS < 45` ∨ (`WL < 45` ∧ `DMRS < 50`) ∨ dosis aguda ≥ 500 mGy | Alerta al cirujano de vuelo; restringir EVA/robótica |
| 🟠 Naranja (3) | `45 ≤ ALI < 65` ∨ `45 ≤ DMRS < 65` ∨ `Z_DMRS ≤ −1,5` | Bloquear tareas de alta demanda temporal |
| 🟡 Amarilla (2) | `EWMA_WL ≥ 65` ∧ `DMRS ≥ 60` | Descanso de 45 min post-tarea |
| 🟢 Verde (1) | resto | Operación nominal |

La dosis aguda es un campo **opcional y manual** del registro diario; si está vacío, la regla de
radiación se ignora y el módulo sigue siendo independiente.

## Verificación numérica

Con el ejemplo del documento (ratings 75/65/65/75/70/65 y tallies 3/3/0/4/3/2) el TLX da
**70,6667**. Con el ánimo 6/5/6/8/4/3/2/4: PA 62,5 · NA 32,5 · **DMRS 64,5**. El JSON de ejemplo del
documento indica 65,5, pero la fórmula y su propio código de referencia dan 64,5; se implementa la
fórmula.

## Persistencia y API

- `mental_day`: fecha única por astronauta, día de misión, M1…M8, dosis aguda, notas.
- `mental_task`: por día, duración, modo, ratings/tallies (JSON validado) y `overall`.
- Los derivados (DMRS, WL, EWMA, Z, ALI, zona) se recalculan al leer.

```
GET /api/v1/astronauts/{code}/mental?days=
PUT /api/v1/astronauts/{code}/mental/{date}     (idempotente: reemplaza las tareas del día)
```

## Límites

- Herramienta de tamizaje; no sustituye la evaluación del médico de vuelo.
- Los pesos DMRS y los umbrales 45/65 provienen del documento y son configurables en
  `domain/mental.py`.
- La Z usa una ventana de 7 días previos; series cortas usan los valores por defecto.
