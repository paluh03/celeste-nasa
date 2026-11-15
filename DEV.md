# DEV · guía de desarrollo

Todo corre en local. No hay dominio, ni contenedores, ni servicios externos: la API y la base viven
en tu máquina.

## 1. Entorno

Las versiones están fijadas en `mise.toml`:

| Herramienta | Versión | Uso |
| --- | --- | --- |
| node | 24 | build del frontend |
| python | 3.13 | backend |
| uv | latest | venv y dependencias Python |
| bun | latest | instalar/correr el frontend y orquestar dev |

```powershell
mise install                 # instala el toolchain pinneado
mise exec -- uv sync --project backend
cd frontend; bun install; cd ..
```

o en un paso: `bun run setup`.

> En Windows, `mise` debe estar en el PATH de la terminal (`mise activate pwsh` o abrir una consola
> nueva después de `winget install jdx.mise`).

## 2. Comandos

| Comando | Qué hace |
| --- | --- |
| `bun run dev` | API con `--reload` + Vite en paralelo (recomendado) |
| `bun run setup` | instala toolchain, venv y node_modules |
| `bun run check` | ruff + pytest + tsc + vitest |
| `bun run build` | `tsc --noEmit` + `vite build` |
| `mise run api` | solo backend en 8000 |
| `mise run web` | solo frontend en 5173 |
| `mise run test` | ruff + pytest + tsc + vitest |
| `mise run lint` | ruff + tsc |
| `mise run seed` | datos de ejemplo (AST-01 / AST-02) |
| `mise run reference` | regenera la referencia desde `_local/Ultrasonido.xlsx` |
| `mise run radiation-reference` | regenera la referencia desde `_local/data_radiacion.csv` |

### Qué hace exactamente `bun run dev`

`scripts/dev.mjs` lanza dos procesos con prefijo de color:

1. **api**: `backend/.venv/Scripts/python.exe -m uvicorn app.main:app --reload`
   - WatchFiles vigila `backend/`. Al guardar cualquier `.py`, uvicorn **reinicia la API** y vuelve a
     levantar la base `.db` (los datos persisten).
2. **web**: `bun run dev` dentro de `frontend/` (Vite con HMR y proxy `/api` → `127.0.0.1:8000`).

Ctrl+C detiene ambos. Si el venv o `node_modules` no existen, el script corta y te dice el comando
que falta en lugar de fallar a medias.

## 3. Base de datos

- Ruta: `backend/data/nasa_space.db` (git-ignored).
- Se crea en el **lifespan de FastAPI**: `init_db()` ejecuta `create_all` cuando uvicorn arranca.
- Inspección rápida:

```powershell
backend\.venv\Scripts\python.exe -c "import sqlite3;c=sqlite3.connect('backend/data/nasa_space.db');print(c.execute('select count(*) from measurement').fetchone())"
```

- Reset total: borra el archivo y reinicia; los astronautas `AST-01`/`AST-02` se recrean solos.
- Cambiar de motor: `NASA_DATABASE_URL=postgresql+psycopg://...` y reiniciar (el dominio no cambia).

## 4. Tests y calidad

```powershell
cd backend; .venv\Scripts\python.exe -m pytest -q
cd backend; .venv\Scripts\python.exe -m ruff check .
cd frontend; bun run test
cd frontend; bun run lint
```

- `tests/test_bone.py`: fórmula, rangos, niveles, orden de la serie.
- `tests/test_api.py`: flujo HTTP completo, importación CSV/XLSX, errores i18n.
- Los tests usan una base temporal (`tests/conftest.py`), nunca la de desarrollo.
- Frontend: `src/lib/format.test.ts` (formato por idioma y aritmética de fechas).

## 5. Convenciones

- **Capas**: `api` no contiene reglas; `domain` no importa FastAPI/SQLModel salvo modelos; los casos
  de uso viven en `modules/*/service.py`.
- **Un módulo por función**: si agregas cortisol, crea `modules/cortisol/`, no un `utils.py`.
- **Fórmulas**: solo en `domain/`. El frontend nunca recalcula BV/TV; usa `/preview` y
  `/monitoring`.
- **Errores**: `DomainError(key, **params)` + catálogo `app/i18n/*.json`; jamás textos hardcodeados
  en los servicios.
- **Eventos**: publica en `events.bus` después de escribir; el suscriptor decide (cache, logs).
- **Tipos**: el contrato real es OpenAPI (`/openapi.json`); mantén `frontend/src/lib/types.ts`
  alineado.

### Agregar un endpoint

1. Esquema Pydantic en `app/domain/schemas.py`.
2. Caso de uso en `app/modules/<modulo>/service.py`.
3. Router en `app/modules/<modulo>/router.py` y regístralo en `app/api/v1/router.py`.
4. Test HTTP en `tests/test_api.py`.

### Agregar un factor de salud

1. `app/domain/<factor>.py` con funciones puras y umbrales.
2. `app/modules/<factor>/` con servicio y router.
3. Tabla propia en `app/domain/models.py` (o reutiliza `measurement` si comparte unidad y sitio).
4. Reutiliza `triage()` si el factor usa los mismos niveles.

## 6. Importación

Formatos `.csv`, `.xlsx`, `.json`; columnas `date|fecha`, `bua`, `uv` y opcionales `att`, `site`.
Las filas se ordenan por fecha y se validan una a una; la respuesta incluye errores por línea.
Prueba rápida:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/astronauts/AST-01/measurements/import?lang=es" -F "file=@examples/measurements-sample.csv"
```

## 7. Producción local (un solo puerto)

```powershell
bun run build                                  # genera frontend/dist
cd backend; .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

FastAPI detecta `frontend/dist` y sirve el SPA en `/`, con la API en `/api/v1`. Útil para demos sin
Vite.

## 8. Problemas típicos

| Síntoma | Causa / solución |
| --- | --- |
| `mise` no se reconoce | abrir una terminal nueva o `mise activate pwsh` |
| `No existe backend/.venv` | `bun run setup` |
| `Faltan dependencias del frontend` | `cd frontend; bun install` |
| Puerto 8000/5173 ocupado | cerrar el proceso anterior (`Get-NetTCPConnection -LocalPort 8000`) |
| `.db` bloqueada | detener uvicorn antes de borrarla |
| Import responde 422 con `error.import_format` | extensión no soportada: usa `.csv`, `.xlsx` o `.json` |
| UV rechazado | el rango es 1200–2000 m/s; un valor como `1.5` significa km/s |
| Cambios de Python no se reflejan | revisa que corras con `bun run dev` (no `uvicorn` sin `--reload`) |

## 9. Variables de entorno

`backend/.env` (opcional, ver `.env.example`):

| Variable | Default |
| --- | --- |
| `NASA_DATABASE_URL` | `sqlite:///backend/data/nasa_space.db` |
| `NASA_DEFAULT_LANG` | `es` |
| `NASA_CACHE_TTL_SECONDS` | `30` |
| `NASA_LEVEL_RISK_RATE` | `0.8` |
| `NASA_LEVEL_ALERT_RATE` | `1.5` |
| `NASA_LEVEL_ALERT_CUMULATIVE` | `3.0` |

## 10. Referencia poblacional

- El artefacto versionado es `backend/app/data/reference_ultrasound.json` (12 grupos).
- Se regenera desde `_local/Ultrasonido.xlsx` (no versionado) con `mise run reference`.
- Campos del astronauta que la alimentan: `sex` (`male`/`female`) y `birth_date`. La edad se
  calcula a la fecha de cada medición, no a la fecha actual.
- Si faltan esos campos, la evaluación devuelve `reference: null` y el estado `unknown`; nada se
  inventa.
- La base se migra sola al arrancar: `init_db()` agrega `sex` y `birth_date` con `ALTER TABLE` si
  la `.db` es anterior. No borra datos.

## 11. Shells (PowerShell y Git Bash)

El proyecto se usa igual desde ambos. `bun run dev` no depende de que `bun` esté en el PATH para
lanzar Vite (usa `process.execPath`), pero sí para invocar `bun` desde la terminal.

```powershell
# PowerShell: perfil con mise (requiere ExecutionPolicy RemoteSigned)
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

```bash
# Git Bash: ~/.bashrc con `eval "$(mise activate bash)"`
```

Si un shell no reconoce `bun`, abre una terminal nueva o usa `export PATH="$PATH:/c/Users/Windows/.bun/bin"`.

## 12. Módulo de cortisol

- Es independiente del óseo: tabla `cortisol_sample`, dominio `app/domain/cortisol.py`, módulo
  `app/modules/cortisol/`.
- La referencia está en `backend/app/data/cortisol_reference.json` (no hay Excel: los valores
  derivados vienen de `_local/cortisol.md`). Editar ahí exige re-ejecutar los tests.
- La vista se cambia con las pestañas del encabezado; la preferencia queda en
  `localStorage["nasa-space-view"]`.
- Import: `measured_at` (fecha **y hora**), `value`, `unit` (`ug_dl` por defecto), `wake_time`,
  `mission_phase`, `notes`.
- El color y el z se recalculan en cada lectura (no se guardan), así que cambiar la referencia
  corrige el histórico sin migrar datos.
- El cruce con el óseo es solo un aviso (`bone_cross_risk`); no altera el triage de BUA.
- Regenerar el seed de demo: `mise run seed` (agrega cortisol si falta) o `... seed --force` para
  duplicar series de demo.

## 13. Módulo de radiación

- Referencia: `backend/app/data/radiation_reference.json`, generada desde
  `_local/data_radiacion.csv` con `mise run radiation-reference`.
- El CSV entregado cubre **un día** y solo trae tasa equivalente: por eso hay un estrato general y
  la capa diaria queda insuficiente. Con un export de varios días, el generador produce estratos
  por región, hora, módulo y época automáticamente.
- Tabla `radiation_reading`; el color se recalcula al leer.
- Región manual (GCR/SAA); sin SGP4 no se infiere.
- Entrada en **UTC** (el formulario lo indica).

## 14. Módulo de salud mental

- Dominio: `backend/app/domain/mental.py` (TLX, DMRS, EWMA, ALI, zonas).
- Tablas `mental_day` (única por astronauta y fecha) y `mental_task`.
- `PUT /mental/{date}` es idempotente: reemplaza las tareas de ese día y recalcula la serie.
- La dosis aguda de la zona roja es un campo manual opcional; no consulta el módulo de radiación.
- Los umbrales viven en `mental.THRESHOLDS`; cambiarlos recalcula todo el histórico al leer.
- `seed` carga 5 días de ejemplo para AST-01 y 2 para AST-02.
