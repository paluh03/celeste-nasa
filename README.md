# NASA SPACE · Monitoreo óseo SCAN

Sistema local de seguimiento de densidad ósea para misiones espaciales de larga duración.
Implementa el método **SCAN** (Scanning Confocal Acoustic Navigation): captura **BUA**, **UV** y
**ATT**, estima **BV/TV** con la regresión publicada, calcula la tendencia de pérdida frente a la
línea base y clasifica el riesgo en tres niveles.

El proyecto está diseñado como plataforma de salud del astronauta con cuatro módulos independientes:
densidad ósea (SCAN), cortisol salival, radiación (TEPC) y salud mental (NASA-TLX + DMRS). Cada uno
tiene su propia fuente de datos y su propia tabla; el núcleo compartido es el perfil del astronauta
y el motor de alertas.

```
plan -> medir -> evaluar -> alertar -> registrar
```

## Stack

| Capa | Tecnología | Motivo |
| --- | --- | --- |
| Toolchain | **mise** (node 24, python 3.13, uv, bun) | una sola versión reproducible, sin admin |
| Backend | **FastAPI + SQLModel + SQLite** | validación, OpenAPI y archivo `.db` local |
| Ciencia | **Python puro** (numpy no requerido) | dominio testeable y determinista |
| Frontend | **React 19 + TypeScript + Vite** | componentes por función, tipado estricto |
| Datos remotos | **TanStack Query** | cache, invalidación y estados de carga |
| i18n | **react-i18next** + catálogos del backend | solo `es` y `en` |
| Runtime dev | **bun** | instalación rápida y `bun run dev` |

Sin nube, sin dominio, sin contenedores obligatorios: todo corre en la máquina.

## Inicio rápido

Requisitos: Windows 10/11 (probado), `mise` y `bun`.

```powershell
winget install --id jdx.mise -e
# nueva terminal para que mise entre al PATH
bun run setup          # mise install + uv sync + bun install
bun run dev            # API + web con recarga en vivo
```

- Web: <http://127.0.0.1:5173>
- API/Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>

Datos de ejemplo (opcional):

```powershell
mise run seed          # o: backend\.venv\Scripts\python.exe -m app.scripts.seed
```

## Arquitectura

Screaming architecture: las carpetas nombran el **qué** (mediciones, monitoreo, astronautas), no el
**cómo**. Cuatro capas con dependencias en un solo sentido:

```
api (HTTP) → modules (casos de uso) → domain (reglas) ← infrastructure (SQLite, archivos)
```

```
backend/
  app/
    core/            config, bus de eventos, i18n, dependencias compartidas
    domain/          modelos SQLModel, esquemas Pydantic, núcleo cientifico (bone.py)
    infrastructure/  engine SQLite, repositorios, lectura de archivos
    modules/
      astronauts/    alta y consulta de astronautas
      measurements/  registro, validación de entrada e importación CSV/XLSX/JSON
      monitoring/    evaluación de la serie, tendencia y triage
    api/v1/          routers FastAPI (contratos HTTP)
    i18n/            catálogos es.json / en.json (mensajes del backend)
    scripts/         seed de datos de ejemplo
  tests/             pytest: dominio puro + flujo HTTP completo
frontend/
  src/
    lib/             cliente API tipado, tipos compartidos, formato de números/fechas
    i18n/            catálogos es/en y configuración de react-i18next
    modules/
      shell/         header, selector de idioma, toast
      astronauts/    contexto de astronauta (en header)
      measurements/  asistente de 3 pasos e importación
      monitoring/    KPIs, gráfico SVG y tabla de historial
```

### Event-driven

`app/core/events.py` es un bus in-process con tópicos:

| Tópico | Se publica cuando | Suscriptor actual |
| --- | --- | --- |
| `measurement.created` | se registra una medición | invalida la cache de evaluaciones |
| `measurement.imported` | termina una importación | invalida la cache de evaluaciones |
| `astronaut.created` | se crea un astronauta | invalida la cache de evaluaciones |

No hay broker porque la app corre en una máquina; el bus desacopla efectos secundarios y deja el
punto de extensión listo para métricas o auditoría.

### Base de datos

- Archivo: `backend/data/nasa_space.db` (ignorado por git).
- La crea **uvicorn** al arrancar (lifespan de FastAPI), no un proceso aparte.
- Se puede cambiar con `NASA_DATABASE_URL`; cualquier URL SQLAlchemy sirve (Postgres incluido).
- Reset: borrar el archivo y reiniciar.

## Reglas clínicas implementadas

| Concepto | Regla |
| --- | --- |
| BV/TV predicho | `3.89e-4 · UV − 9e-4 · BUA − 0.456` |
| Línea base | primera medición de cada astronauta **por sitio** |
| Pérdida acumulada | `(BUA_base − BUA_actual) / BUA_base · 100` |
| Tasa | pérdida acumulada / meses desde la línea base (≥ 0.1 mes) |
| Nivel 1 Normal | tasa < 0.8 %/mes |
| Nivel 2 Riesgo | 0.8 ≤ tasa ≤ 1.5 %/mes |
| Nivel 3 Alerta | tasa > 1.5 %/mes **o** pérdida acumulada > 3 % |

Validación de dominio (se rechaza, no se extrapola): `0 < BUA < 200 dB/MHz`,
`1200 ≤ UV ≤ 2000 m/s`, `0 < ATT < 200 dB/cm`. La fecha de sesión debe ser posterior a la línea
base. ATT se almacena y se muestra, pero no puntúa: el modelo publicado no lo incluye.

Referencias: [10.1117/12.810048](https://doi.org/10.1117/12.810048),
[10.1016/j.actaastro.2012.08.032](https://doi.org/10.1016/j.actaastro.2012.08.032),
[10.1121/1.4784949](https://doi.org/10.1121/1.4784949).

## Referencia poblacional (Shin et al., 2005)

El astronauta necesita **sexo** y **fecha de nacimiento**. La edad se calcula a la fecha de cada
medición y se busca su grupo en la tabla de 12 grupos (2 sexos × 6 rangos) generada desde
`_local/Ultrasonido.xlsx`:

| Sexo | Edad | n | BUA media ± DE (dB/MHz) | SOS media ± DE (m/s) |
|---|---|---:|---|---|
| Hombre | 20-29 | 50 | 121,4 ± 15,6 | 1556,1 ± 47,7 |
| Hombre | 30-39 | 77 | 121,2 ± 15,7 | 1554,6 ± 40,2 |
| Hombre | 40-49 | 137 | 119,2 ± 13,9 | 1548,7 ± 40,7 |
| Hombre | 50-59 | 327 | 114,2 ± 13,1 | 1545,0 ± 35,0 |
| Hombre | 60-69 | 506 | 111,6 ± 13,8 | 1541,0 ± 32,4 |
| Hombre | 70-74 | 128 | 108,7 ± 16,0 | 1527,3 ± 30,8 |
| Mujer | 20-29 | 55 | 113,2 ± 13,6 | 1556,1 ± 28,2 |
| Mujer | 30-39 | 109 | 113,9 ± 13,9 | 1548,5 ± 29,4 |
| Mujer | 40-49 | 228 | 111,1 ± 13,8 | 1547,3 ± 32,1 |
| Mujer | 50-59 | 519 | 105,2 ± 12,9 | 1537,3 ± 28,0 |
| Mujer | 60-69 | 756 | 95,4 ± 11,7 | 1520,8 ± 23,0 |
| Mujer | 70-74 | 161 | 90,2 ± 11,7 | 1507,6 ± 20,5 |

Con esa tabla se calculan, para BUA y para SOS:

```
Z = (valor − media del grupo) / DE del grupo      (ajuste por edad y sexo)
T = (valor − media del grupo 20-29 del sexo) / DE de ese grupo
```

Clasificación por convención OMS sobre **T**: `> -1,0` normal, `-2,5 < T ≤ -1,0` osteopenia,
`T ≤ -2,5` osteoporosis. Se reporta el peor de BUA/SOS y el nivel de triage sigue calculándose por
tasa de pérdida (son ejes distintos: estado vs. velocidad).

Fuera de 20-74 años se usa el grupo extremo más cercano y se emite un aviso. El origen y la
población (coreana, n = 3.053) se muestran junto al resultado: es una referencia poblacional, no un
diagnóstico clínico.

## Módulo de cortisol (independiente)

La segunda sección de la página evalúa **cortisol salival** por CLIA/ECLIA con un semáforo que
depende de la **hora exacta** de la muestra:

```
z = (ln(valor) − ln(mediana(hora))) / σ_ln        verde |z| ≤ 1,28 · amarillo ≤ 1,96 · rojo > 1,96
```

- Referencia matutina combinada (n = 56): mediana 0,474 µg/dL, σ_ln 0,511; ancla nocturna
  0,155 µg/dL e interpolación log-lineal entre 07:30 y 21:30.
- Se guarda en **µg/dL** y se acepta **nmol/L** (÷ 27,59).
- Reglas extra: piso del ensayo después de las 11:00, control p95 del fabricante, contraste por
  sexo (dudoso si discrepa), aviso de edad fuera de 20–55, razón tarde/noche (15:30/21:00), basal
  propio con ≥3 muestras y bandera de cruce con el módulo óseo.
- Datos: tabla `cortisol_sample`; referencia en `backend/app/data/cortisol_reference.json`.
- Detalle completo en [docs/cortisol-spec.md](docs/cortisol-spec.md).

La vista se cambia con las pestañas **Densidad ósea** / **Cortisol** del encabezado; el astronauta
y el idioma son compartidos.

## Módulo de radiación (TEPC)

Sección independiente construida sobre `_local/data_radiacion.csv` (export ASCII del TEPC: un día,
1.441 muestras de 60 s, solo tasa equivalente). La referencia se genera con
`mise run radiation-reference` y produce P50/P95/P99 por estrato con retroceso jerárquico. Con esta
base queda un **estrato general** (las franjas horarias no alcanzan el mínimo de 120) y la **capa
diaria en “insuficiente”**.

Clasificación en tres capas, color final = la peor:

- **A instantánea**: `≤P95` verde, `P95–P99` amarillo, `>P99` rojo solo si 3 lecturas seguidas.
- **B diaria**: dosis del día vs referencia diaria (no disponible con un solo día).
- **C acumulada**: `F30 = H30/250 mSv`, `F_carrera = (previa + misión + proyección)/600 mSv`.

Entrada: fecha-hora UTC, µSv/min, µGy/min opcional (para `Q̄`), región manual GCR/SAA, módulo, día
de misión, duración y dosis previa. Detalle en [docs/radiation-spec.md](docs/radiation-spec.md).

## Módulo de salud mental (NASA-TLX + DMRS + ALI)

Sección independiente con la parte psicométrica de `mental.md` (sin su dosimetría TLD/CR-39):

- **NASA-TLX** por tarea en modo `WEIGHTED_FULL` (tallies que suman 15) o `RAW_FAST` (pesos 1/6).
- **DMRS** diario (8 ítems) con subíndices PA/NA y puntaje global.
- **WL diaria** ponderada por duración, **EWMA α=0,35**, **Z** de 7 días con piso σ=5,
  **ALI = 0,55·EWMA_WL + 0,45·(100−EWMA_ánimo)** y penalización de +8 por deuda de sueño.
- **4 zonas** (verde/amarilla/naranja/roja) con el protocolo del documento; la dosis aguda es un
  campo manual opcional.

El ejemplo del documento se reproduce (TLX 70,6667; DMRS 64,5). Detalle en
[docs/mental-spec.md](docs/mental-spec.md).

## API

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/api/health` | estado del proceso y URL de la base |
| GET | `/api/v1/health` | alias dentro del prefijo versionado |
| GET | `/api/v1/meta` | modelo, umbrales, unidades, sitios e idiomas |
| GET | `/api/v1/astronauts` | lista de astronautas |
| POST | `/api/v1/astronauts` | alta (`{"code","name","sex","birth_date"}`) |
| PATCH | `/api/v1/astronauts/{code}` | perfil: sexo, fecha de nacimiento, nombre |
| GET | `/api/v1/astronauts/{code}` | detalle |
| GET | `/api/v1/astronauts/{code}/measurements?site=` | mediciones |
| POST | `/api/v1/astronauts/{code}/measurements` | alta de medición |
| POST | `/api/v1/astronauts/{code}/preview` | evalúa sin guardar (paso 3 del asistente) |
| POST | `/api/v1/astronauts/{code}/measurements/import` | importa archivo |
| GET | `/api/v1/astronauts/{code}/monitoring?site=&window=&lang=` | serie evaluada + nivel actual |
| POST | `/api/v1/astronauts/{code}/cortisol` | registra y evalúa una muestra de cortisol |
| GET | `/api/v1/astronauts/{code}/cortisol?days=` | serie de cortisol, razón y basal |
| POST | `/api/v1/astronauts/{code}/cortisol/import` | importa muestras (CSV/XLSX/JSON) |
| GET | `/api/v1/astronauts/{code}/radiation` | lecturas + capas A/B/C + acumulados |
| POST | `/api/v1/astronauts/{code}/radiation` | registra una lectura (UTC) |
| GET | `/api/v1/astronauts/{code}/mental?days=` | serie diaria + zona actual |
| PUT | `/api/v1/astronauts/{code}/mental/{date}` | guarda/reemplaza el día (TLX + DMRS) |

Todas las respuestas de error usan `{"detail": "...", "code": "..."}` en el idioma solicitado.

### i18n

- Idiomas: **es** y **en**.
- El frontend traduce su interfaz (`frontend/src/i18n`).
- El backend traduce errores y el texto clínico de cada nivel (`backend/app/i18n`), resolviendo
  `?lang=` → `Accept-Language` → `es`.
- La preferencia del navegador queda en `localStorage` (`nasa-space-lang`).

## Importación de datos

Formatos: **CSV**, **XLSX** y **JSON**. El formato se detecta por extensión.

```csv
date,bua,uv,att,site
2026-07-01,118.0,1552,52,calcaneus
2026-07-31,77.5,1556,51.6,calcaneus
```

- Columnas obligatorias: `date` (o `fecha`) y `bua`, `uv`. Opcionales: `att`, `site`.
- Fechas aceptadas: `YYYY-MM-DD`, `DD/MM/YYYY`, `YYYY/MM/DD`, `DD-MM-YYYY`, `MM/DD/YYYY`.
- Sitios: `calcaneus` / `calcáneo` / `talón` y `femoral_neck` / `cuello femoral`.
- El archivo se ordena por fecha antes de escribir y se valida fila a fila: la respuesta reporta
  `created`, `skipped` y los errores con número de línea. Un archivo con filas malas no pierde las
  buenas.

Ejemplos listos en `examples/`.

## Escalabilidad a nuevos factores

El módulo óseo no está cableado a la API:

1. Nuevo factor → carpeta `app/modules/<factor>/` con su `service.py` y `router.py`.
2. Sus fórmulas puras → `app/domain/<factor>.py` con tests propios.
3. La tabla `measurement` guarda `site` y parámetros óseos; los factores nuevos usan su propia
   tabla (`cortisol_sample`) o la columna `source`/atributos extendidos, sin tocar lo existente.
4. El `triage` por niveles se reutiliza: recibe números y umbrales, no tipos de medición.

## Estado

- 127 tests de backend (dominio, referencias, cortisol, radiación, salud mental y API) y 4 de frontend en verde.
- Ruff limpio, TypeScript estricto y build de producción verificado.
- Base local creada por uvicorn y hot reload comprobado en `bun run dev`.

Ver [DEV.md](DEV.md) para el flujo de trabajo diario.
