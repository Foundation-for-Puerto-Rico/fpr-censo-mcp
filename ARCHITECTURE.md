# ARCHITECTURE.md — fpr-censo-mcp

## Visión general

```
┌─────────────────────────────────────────────────────────┐
│                    Claude (Cowork / Code / Chat)         │
│                                                         │
│  Plugin FPR ──→ Skills + Commands + Contexto org.       │
│       │                                                 │
│       ▼                                                 │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ fpr-censo-mcp│    │  wcrp-rag    │   [otros MCPs]    │
│  │  (este repo) │    │              │                   │
│  └──────┬───────┘    └──────────────┘                   │
└─────────┼───────────────────────────────────────────────┘
          │ httpx (async)
          ▼
┌─────────────────────┐
│  U.S. Census Bureau │
│     Data API        │
│ api.census.gov/data │
└─────────────────────┘
```

El MCP es un intermediario inteligente entre Claude y el Census API. Agrega valor en tres áreas: (1) traducción de la jerga federal a terminología local de PR, (2) curación de variables relevantes para el trabajo de FPR, y (3) evaluación automática de calidad estadística.

---

## Census API — Cómo funciona

### Estructura de un request

```
GET https://api.census.gov/data/{year}/{dataset}?get={variables}&for={geography}&in={parent_geography}&key={api_key}
```

### Ejemplos concretos para PR

**Población total de todos los municipios:**
```
GET https://api.census.gov/data/2022/acs/acs5?get=NAME,B01003_001E&for=county:*&in=state:72&key=KEY
```

**Ingreso mediano en los barrios de Vega Baja (FIPS county:145):**
```
GET https://api.census.gov/data/2022/acs/acs5?get=NAME,B19013_001E,B19013_001M&for=county%20subdivision:*&in=state:72%20county:145&key=KEY
```

**Nota**: `_001E` = estimado, `_001M` = margin of error. Siempre pedir ambos.

**Tracts en un municipio:**
```
GET https://api.census.gov/data/2022/acs/acs5?get=NAME,B01003_001E&for=tract:*&in=state:72%20county:145&key=KEY
```

### Respuesta del API

El Census API devuelve un array de arrays. La primera fila son headers:

```json
[
  ["NAME", "B01003_001E", "state", "county"],
  ["Adjuntas Municipio, Puerto Rico", "17781", "72", "001"],
  ["Aguada Municipio, Puerto Rico", "37560", "72", "003"],
  ...
]
```

El MCP debe parsear esto en estructuras con nombre, no devolver arrays crudos.

### Limitaciones del API

- Máximo ~50 variables por request
- Rate limiting (no documentado oficialmente, pero ~500 requests/día es seguro)
- Algunos datasets/años no tienen datos para PR
- Variables cambian entre años — verificar disponibilidad
- Block groups y blocks requieren especificar tract padre
- El ACS 1-Year solo cubre áreas con 65,000+ habitantes

---

## Módulos del sistema

### `src/census_client.py` — Cliente HTTP

Responsabilidades:
- Construcción de URLs del Census API
- Manejo de requests async con httpx
- Parseo de respuestas (array de arrays → lista de dicts)
- Cache en memoria de respuestas (LRU, TTL de 24h)
- Retry con backoff exponencial
- Manejo de errores HTTP con mensajes claros

```python
class CensusClient:
    BASE_URL = "https://api.census.gov/data"

    async def query(
        self,
        year: int,
        dataset: str,
        variables: list[str],
        for_clause: str,
        in_clause: str | None = None,
    ) -> list[dict]:
        """
        Ejecuta un query al Census API y devuelve lista de dicts.
        Siempre incluye la variable MOE correspondiente si existe.
        """
        ...

    async def get_available_datasets(self, year: int | None = None) -> list[dict]:
        """Lista datasets disponibles para PR."""
        ...

    async def search_variables(self, dataset: str, year: int, keyword: str) -> list[dict]:
        """Busca variables por keyword en un dataset."""
        ...

    async def get_geographies(self, dataset: str, year: int) -> list[dict]:
        """Niveles geográficos disponibles para un dataset."""
        ...
```

### `src/geography.py` — Geografías de PR

Responsabilidades:
- Mapeo bidireccional nombre ↔ FIPS para municipios y barrios
- Búsqueda fuzzy de nombres (ej: "vega baja" → "Vega Baja Municipio" → county:145)
- Traducción de terminología federal ↔ local
- Construcción de cláusulas `for` e `in` para el Census API

```python
# Mapeos clave
TERMINOLOGY = {
    "county": "municipio",
    "county subdivision": "barrio",
    "tract": "tract censal",
    "block group": "grupo de bloques",
    "state": "estado/territorio",
}

class GeographyResolver:
    def resolve(self, name: str, level: str | None = None) -> GeographyResult:
        """
        Dado un nombre como 'Vega Baja' o 'Almirante Sur',
        devuelve el FIPS code y las cláusulas for/in correctas.
        """
        ...

    def list_municipios(self) -> list[Municipio]:
        """Los 78 municipios con FIPS."""
        ...

    def list_barrios(self, municipio: str) -> list[Barrio]:
        """Barrios de un municipio dado."""
        ...
```

### `src/profiles.py` — Perfiles temáticos

Responsabilidades:
- Definición de grupos de variables por tema
- Cada variable tiene: código ACS, nombre en español, nombre en inglés, código MOE correspondiente, categoría
- Resolución de variables por perfil temático

```python
@dataclass
class VariableDefinition:
    code: str           # "B19013_001E"
    moe_code: str       # "B19013_001M"
    nombre_es: str      # "Ingreso mediano del hogar"
    nombre_en: str      # "Median household income"
    universo: str       # "Hogares"
    formato: str        # "moneda" | "porcentaje" | "conteo" | "mediana"
    perfil: str         # "economico"

PERFILES: dict[str, list[VariableDefinition]] = {
    "demografico": [...],
    "economico": [...],
    "vivienda": [...],
    "educacion": [...],
    "salud_social": [...],
    "infraestructura": [...],
    "negocio": [...],
}
```

#### Variables curadas por perfil

**Demográfico:**
| Variable | Código | MOE |
|----------|--------|-----|
| Población total | B01003_001E | B01003_001M |
| Edad mediana | B01002_001E | B01002_001M |
| Masculino | B01001_002E | B01001_002M |
| Femenino | B01001_026E | B01001_026M |
| Menores de 18 | B09001_001E | B09001_001M |
| 65 años o más | B01001_020E-025E (aggregate) | — |
| Hispanic/Latino | B03003_003E | B03003_003M |

**Económico:**
| Variable | Código | MOE |
|----------|--------|-----|
| Ingreso mediano del hogar | B19013_001E | B19013_001M |
| Ingreso per cápita | B19301_001E | B19301_001M |
| Personas bajo pobreza | B17001_002E | B17001_002M |
| Tasa de desempleo | B23025_005E / B23025_002E | — |
| Hogares con SNAP/cupones | B22003_002E | B22003_002M |

**Vivienda:**
| Variable | Código | MOE |
|----------|--------|-----|
| Unidades de vivienda total | B25001_001E | B25001_001M |
| Viviendas ocupadas | B25002_002E | B25002_002M |
| Viviendas vacantes | B25002_003E | B25002_003M |
| Valor mediano (owner-occupied) | B25077_001E | B25077_001M |
| Renta mediana | B25064_001E | B25064_001M |
| Construidas antes de 1970 | B25034_008E-010E (aggregate) | — |
| Sin hipoteca | B25081_002E | B25081_002M |

**Educación:**
| Variable | Código | MOE |
|----------|--------|-----|
| Bachillerato o más (25+) | B15003_017E-025E (aggregate) | — |
| Grado asociado o más | B15003_021E-025E (aggregate) | — |
| Matrícula escolar (3+) | B14001_002E | B14001_002M |

**Salud y Social:**
| Variable | Código | MOE |
|----------|--------|-----|
| Sin seguro médico | B27010 series | — |
| Con discapacidad | B18101_004E+ (aggregate) | — |
| Hogares con un idioma distinto al inglés | B16001 series | — |
| Veteranos | B21001_002E | B21001_002M |

**Infraestructura:**
| Variable | Código | MOE |
|----------|--------|-----|
| Hogares con internet | B28002_004E | B28002_004M |
| Sin vehículo disponible | B08201_002E | B08201_002M |
| Transporte público al trabajo | B08301_010E | B08301_010M |
| Viaja solo en carro | B08301_003E | B08301_003M |

> **Nota**: Las variables con "(aggregate)" requieren sumar múltiples celdas. El MCP debe manejar estas agregaciones internamente y devolver el total.

### `src/quality.py` — Evaluación de calidad

Responsabilidades:
- Cálculo de Coeficiente de Variación (CV)
- Clasificación de confiabilidad
- Sugerencias cuando un dato no es confiable
- Derivación de estimados agregados con propagación de error

```python
@dataclass
class QualityAssessment:
    estimado: float
    moe: float
    cv: float               # Coeficiente de variación (%)
    confiabilidad: str       # "confiable" | "precaucion" | "no_confiable"
    mensaje: str             # Explicación en español
    sugerencia: str | None   # Qué hacer si no es confiable

def evaluar_calidad(estimado: float, moe: float) -> QualityAssessment:
    """
    CV = (MOE / 1.645) / Estimado × 100

    Clasificación:
      CV < 15%   → confiable
      CV 15-30%  → precaucion
      CV > 30%   → no_confiable
    """
    ...

def agregar_estimados(estimados: list[float], moes: list[float]) -> tuple[float, float]:
    """
    Para sumar estimados ACS (ej: agregar grupos de edad):
      Suma = sum(estimados)
      MOE_suma = sqrt(sum(moe_i^2))
    """
    ...

def calcular_proporcion(parte: float, moe_parte: float, total: float, moe_total: float) -> tuple[float, float]:
    """
    Para calcular proporciones (ej: % pobreza):
      P = parte / total
      MOE_P = (1/total) * sqrt(moe_parte^2 - (P^2 * moe_total^2))

    Si el valor dentro del sqrt es negativo, usar:
      MOE_P = (1/total) * sqrt(moe_parte^2 + (P^2 * moe_total^2))
    """
    ...
```

### `src/tools/discovery.py`

```python
@mcp.tool(name="censo_listar_datasets", annotations={"readOnlyHint": True, ...})
async def censo_listar_datasets(params: ListarDatasetsInput) -> str:
    """
    Lista los datasets del Census Bureau disponibles para Puerto Rico.

    Devuelve: nombre, path del API, años disponibles, y descripción
    de cada dataset. Filtra automáticamente a los datasets que tienen
    datos para PR (state:72).
    """
    ...

@mcp.tool(name="censo_buscar_variables", annotations={"readOnlyHint": True, ...})
async def censo_buscar_variables(params: BuscarVariablesInput) -> str:
    """
    Busca variables del Census Bureau por keyword en español o inglés.

    Primero busca en el catálogo curado de variables relevantes para FPR.
    Si no encuentra resultados, busca en el API del Census Bureau directamente.
    Devuelve: código de variable, nombre, concepto, y el código MOE asociado.
    """
    ...

@mcp.tool(name="censo_listar_municipios", annotations={"readOnlyHint": True, ...})
async def censo_listar_municipios() -> str:
    """
    Lista los 78 municipios de Puerto Rico con sus FIPS codes.

    Devuelve nombre, FIPS code, y región (si aplica).
    Útil para resolver nombres a códigos antes de hacer consultas.
    """
    ...

@mcp.tool(name="censo_listar_barrios", annotations={"readOnlyHint": True, ...})
async def censo_listar_barrios(params: ListarBarriosInput) -> str:
    """
    Lista los barrios (county subdivisions) dentro de un municipio.

    Acepta nombre o FIPS del municipio. Devuelve nombre y FIPS de cada barrio.
    """
    ...
```

### `src/tools/query.py`

```python
@mcp.tool(name="censo_consultar", annotations={"readOnlyHint": True, ...})
async def censo_consultar(params: ConsultarInput) -> str:
    """
    Consulta flexible al Census Bureau Data API.

    Permite especificar dataset, año, variables, y nivel geográfico.
    Acepta nombres de municipios/barrios en español — los resuelve
    automáticamente a FIPS codes.

    Siempre incluye el MOE correspondiente y la evaluación de calidad
    para estimados del ACS.

    Ejemplo: Consultar ingreso mediano de todos los municipios, ACS 2022.
    """
    ...

@mcp.tool(name="censo_perfil", annotations={"readOnlyHint": True, ...})
async def censo_perfil(params: PerfilInput) -> str:
    """
    Genera un perfil temático para una geografía dada.

    Usa variables pre-seleccionadas del perfil temático indicado
    (demografico, economico, vivienda, educacion, salud_social,
    infraestructura, negocio). Si no se indica perfil, devuelve
    un resumen ejecutivo con indicadores clave de todos los perfiles.

    Incluye evaluación de calidad para cada indicador.
    """
    ...

@mcp.tool(name="censo_serie_temporal", annotations={"readOnlyHint": True, ...})
async def censo_serie_temporal(params: SerieTemporalInput) -> str:
    """
    Obtiene una variable a través de múltiples años para ver tendencias.

    Útil para analizar cambios demográficos, pérdida poblacional,
    cambios en ingreso, etc. Intenta obtener datos del rango de años
    solicitado. Si una variable no existe en un año dado, lo omite.
    """
    ...
```

### `src/tools/analysis.py`

```python
@mcp.tool(name="censo_comparar", annotations={"readOnlyHint": True, ...})
async def censo_comparar(params: CompararInput) -> str:
    """
    Compara indicadores entre dos o más geografías.

    Acepta municipios, barrios, tracts, o combinaciones.
    Devuelve tabla comparativa con evaluación de calidad.
    Señala diferencias estadísticamente significativas
    (cuando los intervalos de confianza no se solapan).
    """
    ...

@mcp.tool(name="censo_evaluar_calidad", annotations={"readOnlyHint": True, ...})
async def censo_evaluar_calidad(params: EvaluarCalidadInput) -> str:
    """
    Evalúa la confiabilidad estadística de estimados del ACS.

    Calcula CV, clasifica confiabilidad, y sugiere acciones cuando
    un dato no es confiable (ej: usar ACS 5-Year en vez de 1-Year,
    agregar geografías adyacentes, etc.)
    """
    ...

@mcp.tool(name="censo_contexto", annotations={"readOnlyHint": True, ...})
async def censo_contexto(params: ContextoInput) -> str:
    """
    Contextualiza un indicador comparándolo con PR y EE.UU.

    Dado un valor para una geografía específica, lo compara con:
    - La mediana/promedio de Puerto Rico
    - La mediana/promedio nacional de EE.UU.
    - El rango entre municipios de PR (percentiles)

    Útil para interpretar si un dato es alto, bajo, o típico.
    """
    ...
```

---

## Datos estáticos (`data/`)

### `municipios_pr.json`

```json
[
  {"nombre": "Adjuntas", "fips": "001", "region": "Central"},
  {"nombre": "Aguada", "fips": "003", "region": "Oeste"},
  {"nombre": "Aguadilla", "fips": "005", "region": "Noroeste"},
  ...
  {"nombre": "Vega Baja", "fips": "145", "region": "Norte"},
  ...
  {"nombre": "Yauco", "fips": "153", "region": "Suroeste"}
]
```

Los 78 municipios con su FIPS de 3 dígitos (county code) y región.

### `barrios_pr.json`

```json
{
  "145": [
    {"nombre": "Almirante Norte", "fips": "02428"},
    {"nombre": "Almirante Sur", "fips": "02430"},
    {"nombre": "Cabo Caribe", "fips": "12730"},
    {"nombre": "Ceiba", "fips": "15814"},
    {"nombre": "Cibuco", "fips": "17542"},
    {"nombre": "Puerto Nuevo", "fips": "72225"},
    {"nombre": "Pugnado Adentro", "fips": "73200"},
    {"nombre": "Pugnado Afuera", "fips": "73310"},
    {"nombre": "Río Abajo", "fips": "76530"},
    {"nombre": "Río Arriba", "fips": "76640"},
    {"nombre": "Vega Baja Pueblo", "fips": "84445"},
    {"nombre": "Yeguada", "fips": "91350"}
  ]
}
```

Indexado por FIPS del municipio padre. Los FIPS de los barrios son county subdivision codes.

> **Nota**: Estos archivos deben generarse a partir de los datos reales del Census Bureau Gazetteer o del Tiger/Line files. Los FIPS de ejemplo arriba son ilustrativos — verificar contra datos oficiales al implementar.

### `variables_curadas.json`

```json
{
  "demografico": [
    {
      "code": "B01003_001E",
      "moe_code": "B01003_001M",
      "nombre_es": "Población total",
      "nombre_en": "Total population",
      "universo": "Total population",
      "formato": "conteo",
      "notas": null
    },
    ...
  ],
  "economico": [...],
  "vivienda": [...],
  ...
}
```

---

## Cache

Los datos del ACS se publican anualmente (típicamente septiembre-diciembre). No tiene sentido hacer el mismo query al Census API múltiples veces en el mismo día.

Estrategia: Cache LRU en memoria con TTL de 24 horas.

```python
from functools import lru_cache
# o usar cachetools para TTL

# Key: (year, dataset, variables_tuple, for_clause, in_clause)
# Value: parsed response
```

Para un deployment más robusto, considerar SQLite como cache persistente.

---

## Deployment

### Opción 1: Streamable HTTP directo

```bash
python -m src.server --transport streamable-http --port 8001
```

Ideal para desarrollo y testing. Correr detrás de nginx/caddy para HTTPS.

### Opción 2: Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install .
COPY src/ src/
COPY data/ data/
EXPOSE 8001
CMD ["python", "-m", "src.server", "--transport", "streamable-http", "--port", "8001"]
```

### Configuración en Claude Desktop / Cowork

Como conector remoto (streamable HTTP):
```json
{
  "mcpServers": {
    "fpr-censo": {
      "url": "https://censo.tudominio.com/mcp"
    }
  }
}
```

---

## Roadmap

### Fase 1: MVP
- Census client con query básico
- Geografías de PR (municipios)
- Tools: `censo_consultar`, `censo_listar_municipios`, `censo_buscar_variables`
- Perfil demográfico y económico
- Evaluación de calidad MOE/CV
- Deploy como streamable HTTP

### Fase 2: Cobertura completa
- Todos los perfiles temáticos
- Barrios y tracts
- Series temporales
- Comparaciones y contexto
- Cache
- Tests y evaluaciones

### Fase 3: Plugin de Cowork
- Repo separado `fpr-cowork-plugins/`
- Plugin `fpr-censo` con skills y commands
- Marketplace privado de FPR
- Documentación para el equipo

### Fase 4: Integración cross-MCP
- Conectar con WCRP-RAG en un plugin combinado
- Datos censales + contenido de planes = diagnóstico comunitario completo
- Otros MCPs según necesidades de FPR
