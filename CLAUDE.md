# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este proyecto

MCP Server (Model Context Protocol) que conecta a Claude con datos del U.S. Census Bureau, optimizado para Puerto Rico. Es una herramienta organizacional de **Foundation for Puerto Rico (FPR)** — no es específica de ningún programa. Cualquier equipo de FPR (WCRP, desarrollo económico, turismo, emprendimiento, vivienda, investigación) debe poder usarlo.

## Stack técnico

- **Lenguaje**: Python 3.11+
- **Framework MCP**: FastMCP (mcp python sdk)
- **HTTP Client**: httpx (async)
- **Validación**: Pydantic v2
- **Transporte**: Streamable HTTP (servidor remoto, multiusuario)
- **Fuente de datos**: U.S. Census Bureau Data API (https://api.census.gov/data)
- **API Key**: Variable de entorno `CENSUS_API_KEY` (gratuito, obtener en https://api.census.gov/data/key_signup.html)

## Principios de diseño

1. **PR-first**: Todo el diseño asume Puerto Rico como contexto principal. Los FIPS codes, nombres de municipios, barrios y la jerarquía geográfica de PR están embebidos. El state FIPS de PR es `72`.
2. **Neutral al programa**: El MCP no asume qué programa de FPR lo usa. Provee datos y perfiles temáticos; la especialización ocurre en la capa de plugins de Cowork, no aquí.
3. **Bilingüe**: Tool names y parámetros en español. Documentación y respuestas en español. El Census API devuelve datos en inglés — el MCP los devuelve tal cual pero con contexto en español.
4. **Calidad de datos primero**: Cada respuesta con estimados del ACS debe incluir el Margin of Error (MOE) y una evaluación de confiabilidad (CV). Nunca devolver un estimado sin su MOE.
5. **Composable**: Los tools deben ser atómicos y componibles. Un agente debe poder combinar `censo_consultar` + `censo_evaluar_calidad` + `censo_comparar` para construir análisis complejos.

## Estructura del proyecto

```
fpr-censo-mcp/
├── CLAUDE.md                       # Este archivo
├── ARCHITECTURE.md                 # Arquitectura detallada
├── README.md                       # Documentación de uso
├── pyproject.toml                  # Dependencias y metadata
├── Dockerfile                      # Para deployment
├── .env.example                    # CENSUS_API_KEY=tu_key_aquí
├── src/
│   ├── __init__.py
│   ├── server.py                   # FastMCP server + entry point
│   ├── census_client.py            # Cliente async para Census API
│   ├── geography.py                # Jerarquía geográfica de PR
│   ├── profiles.py                 # Perfiles temáticos de variables
│   ├── variables.py                # Catálogo + búsqueda de variables ACS
│   ├── quality.py                  # Evaluación MOE / CV / confiabilidad
│   └── tools/
│       ├── __init__.py
│       ├── discovery.py            # Tools de exploración
│       ├── query.py                # Tools de consulta
│       └── analysis.py             # Tools de análisis
├── data/
│   ├── municipios_pr.json          # 78 municipios: nombre ↔ FIPS
│   ├── barrios_pr.json             # Barrios por municipio con FIPS
│   └── variables_curadas.json      # Variables pre-seleccionadas por perfil temático
└── tests/
    ├── test_client.py
    ├── test_tools.py
    └── eval.xml                    # Evaluaciones MCP (10 preguntas)
```

## Tools del MCP

### Discovery (explorar qué hay)

| Tool | Descripción | Read-only |
|------|-------------|-----------|
| `censo_listar_datasets` | Datasets disponibles para PR con años | ✅ |
| `censo_buscar_variables` | Buscar variables por keyword en español/inglés | ✅ |
| `censo_listar_geografias` | Niveles geográficos disponibles para un dataset | ✅ |
| `censo_listar_municipios` | Los 78 municipios con FIPS codes | ✅ |
| `censo_listar_barrios` | Barrios dentro de un municipio dado | ✅ |

### Query (consultar datos)

| Tool | Descripción | Read-only |
|------|-------------|-----------|
| `censo_consultar` | Query flexible: dataset, año, variables, geografía | ✅ |
| `censo_perfil` | Perfil temático pre-configurado para cualquier geografía | ✅ |
| `censo_serie_temporal` | Una variable a través de múltiples años | ✅ |

### Análisis (valor agregado)

| Tool | Descripción | Read-only |
|------|-------------|-----------|
| `censo_comparar` | Comparar dos o más geografías lado a lado | ✅ |
| `censo_evaluar_calidad` | Evaluar confiabilidad de un estimado ACS (MOE/CV) | ✅ |
| `censo_contexto` | Contextualizar un dato vs. mediana de PR y nacional | ✅ |

Todos los tools son read-only. Este MCP no escribe datos en ningún sistema.

## Datasets del Census API a soportar

| Dataset | Path API | Uso | Granularidad mínima en PR |
|---------|----------|-----|---------------------------|
| ACS 5-Year | `acs/acs5` | Principal. Cubre todas las áreas geográficas. | Block Group |
| ACS 1-Year | `acs/acs1` | Solo municipios 65k+ hab. Datos más recientes. | Municipio (limitado) |
| Decennial Census | `dec/pl` | Conteos oficiales, redistricting. | Block |
| Population Estimates | `pep/population` | Estimados intercensales anuales. | Municipio |

## Jerarquía geográfica de PR en el Census API

```
Puerto Rico (state:72)
  └── Municipio (county:001-153, 78 municipios)
       └── Barrio (county subdivision)
            └── Census Tract (tract)
                 └── Block Group (block group)
                      └── Block (block, solo decenal)
```

**Importante**: El Census API usa terminología federal (county, county subdivision). Este MCP traduce: county → municipio, county subdivision → barrio. Los usuarios de FPR piensan en municipios y barrios.

## Perfiles temáticos

Variables agrupadas por tema, usadas por `censo_perfil`:

- **demografico**: Población, edad, sexo, raza/etnicidad
- **economico**: Ingreso, pobreza, empleo/desempleo, industria
- **vivienda**: Unidades, ocupación/vacancia, valor, renta, año de construcción, tenure
- **educacion**: Nivel educativo, matrícula escolar
- **salud_social**: Seguro médico, discapacidad, idioma en el hogar
- **infraestructura**: Internet, vehículos, medio de transporte al trabajo
- **negocio**: Establecimientos, industria (Economic Census cuando disponible)

## Evaluación de calidad (MOE/CV)

Para todo estimado del ACS:

```
CV = (MOE / 1.645) / Estimado × 100

Clasificación:
  CV < 15%   → ✅ Confiable
  CV 15-30%  → ⚠️ Usar con precaución
  CV > 30%   → ❌ No confiable (considerar agregar geografías)
  Estimado 0 → ➖ No aplica
```

**Siempre** devolver MOE y clasificación junto al estimado. Nunca un número pelado.

## Convenciones de código

- Tool names: snake_case con prefijo `censo_`
- Pydantic models para todos los inputs
- Async/await para todas las llamadas HTTP
- Respuestas en formato markdown por defecto, JSON opcional
- Todos los tools deben tener annotations (readOnlyHint: true, destructiveHint: false)
- Docstrings en español
- Logging a stderr (nunca stdout)
- Manejo de errores con mensajes claros y sugerencias de próximos pasos

## Estado actual

Este proyecto está en fase de diseño. ARCHITECTURE.md contiene la especificación completa de módulos, variables curadas por perfil, y el roadmap de implementación. No hay código implementado todavía — toda la estructura bajo `src/`, `data/`, y `tests/` debe crearse.

## Dependencias principales

```
mcp[cli]
httpx
pydantic>=2.0
```

## Comandos de desarrollo

```bash
# Instalar dependencias
pip install -e ".[dev]"

# Desarrollo local (stdio)
python -m src.server

# Servidor remoto (streamable HTTP)
python -m src.server --transport streamable-http --port 8001

# Tests
pytest tests/

# Con Docker
docker compose up
```

## Variable de entorno requerida

```bash
export CENSUS_API_KEY=tu_key_aquí  # Obtener gratis en https://api.census.gov/data/key_signup.html
```

## Relación con otros sistemas FPR

- **WCRP-RAG** (https://wcrprag.shop/sse): MCP separado para planes comunitarios. Eventualmente un plugin de Cowork puede conectar ambos.
- **Plugin de Cowork**: Vive en repo separado (`fpr-cowork-plugins/`). El plugin envuelve este MCP con skills, commands y contexto organizacional.
- **Microsoft 365**: Conector existente en Claude. Los datos censales pueden fluir hacia Excel/PowerPoint vía Cowork.
