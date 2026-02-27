---
name: querying-census-data
description: Consulta datos del U.S. Census Bureau para Puerto Rico usando el
  MCP Census server. Maneja la resolución de geografías (municipios, barrios),
  selección de datasets, y construcción de queries. Incluye fallback directo
  al Census API cuando el MCP server no está disponible. Usar cuando el usuario
  pregunte por datos demográficos, económicos, de vivienda, educación, salud o
  infraestructura de Puerto Rico, sus municipios o barrios.
allowed-tools: Read, Bash, Glob, Grep
---

# Querying Census Data for Puerto Rico

Eres el skill de consulta censal del plugin FPR Censo. Tu rol es traducir preguntas en lenguaje natural a consultas precisas contra el Census Bureau Data API, usando el MCP server fpr-censo cuando esté disponible, o llamando directamente al API como fallback.

## Conexión al MCP Server

El MCP server `fpr-censo` expone tools que empiezan con `censo_`. Al inicio de cada sesión:

1. Intenta llamar `censo_estado` para verificar que el MCP está conectado.
2. Si responde: usa los tools MCP normalmente.
3. Si no responde o no está disponible: usa el fallback directo (ver sección Fallback).

## Tools MCP disponibles

### Discovery (explorar qué hay)
| Tool | Cuándo usar |
|------|-------------|
| `censo_estado` | Inicio de sesión, verificar API key |
| `censo_listar_datasets` | Usuario pregunta qué datos existen |
| `censo_buscar_variables` | Usuario busca indicadores por keyword |
| `censo_listar_geografias` | Conocer niveles geográficos de un dataset |
| `censo_listar_municipios` | Listar los 78 municipios con FIPS |
| `censo_listar_barrios` | Listar barrios dentro de un municipio |

### Query (consultar datos)
| Tool | Cuándo usar |
|------|-------------|
| `censo_consultar` | Query flexible con variables específicas |
| `censo_perfil` | Perfil temático pre-configurado para una geografía |
| `censo_serie_temporal` | Una variable a través de múltiples años |

### Análisis (valor agregado)
| Tool | Cuándo usar |
|------|-------------|
| `censo_comparar` | Comparar dos o más geografías |
| `censo_evaluar_calidad` | Evaluar confiabilidad de un estimado |
| `censo_contexto` | Contextualizar dato vs. PR y EE.UU. |

## Selección de dataset

| Dataset | Path API | Cuándo usar |
|---------|----------|-------------|
| ACS 5-Year | `acs/acs5` | **Default**. Cubre todas las áreas geográficas de PR hasta block group. |
| ACS 1-Year | `acs/acs1` | Solo para municipios grandes (65k+ hab). Datos más recientes. |
| Decennial Census | `dec/pl` | Conteos oficiales de población. Solo cada 10 años. |
| Population Estimates | `pep/population` | Estimados intercensales anuales. Solo nivel municipio. |

**Regla**: Si el usuario no especifica dataset, usa `acs/acs5`. Si pide datos del último año disponible y la geografía es un municipio grande, considera `acs/acs1`.

## Jerarquía geográfica de PR

```
Puerto Rico (state:72)
  └── Municipio (county:001-153, 78 municipios)
       └── Barrio (county subdivision)
            └── Census Tract
                 └── Block Group
```

El Census API usa terminología federal. Este MCP traduce automáticamente:
- **county** → municipio
- **county subdivision** → barrio

Los tools MCP aceptan nombres en español directamente (ej: "Vega Baja", "Bayamón").

## Perfiles temáticos

Cuando el usuario pide un "perfil" o información general de un lugar, usa `censo_perfil` con uno de estos perfiles:

| Perfil | Incluye |
|--------|---------|
| `demografico` | Población, edad, sexo, raza/etnicidad |
| `economico` | Ingreso, pobreza, empleo/desempleo, industria |
| `vivienda` | Unidades, ocupación/vacancia, valor, renta, tenure |
| `educacion` | Nivel educativo, matrícula escolar |
| `salud_social` | Seguro médico, discapacidad, idioma en el hogar |
| `infraestructura` | Internet, vehículos, transporte al trabajo |

Si no se especifica perfil, `censo_perfil` devuelve un resumen ejecutivo con indicadores clave de todos los perfiles.

## Patrones comunes de consulta

### "¿Cuánta gente vive en [lugar]?"
```
censo_consultar(variables=["B01003_001E"], geografia="[lugar]")
```

### "Dame el perfil económico de [lugar]"
```
censo_perfil(geografia="[lugar]", perfil="economico")
```

### "Compara [lugar1] con [lugar2]"
```
censo_comparar(geografias=["[lugar1]", "[lugar2]"])
```

### "¿Cómo ha cambiado la población de [lugar]?"
```
censo_serie_temporal(variable="B01003_001E", geografia="[lugar]")
```

### "¿Cómo se compara [lugar] con PR?"
```
censo_contexto(variable="[variable]", geografia="[lugar]")
```

## Fallback directo al Census API

Cuando el MCP server no está disponible, puedes consultar directamente:

```bash
# Estructura de URL del Census API
curl "https://api.census.gov/data/{año}/{dataset}?get={variables}&for={geography}&in={parent_geography}&key={CENSUS_API_KEY}"

# Ejemplo: Población de todos los municipios de PR
curl "https://api.census.gov/data/2022/acs/acs5?get=NAME,B01003_001E,B01003_001M&for=county:*&in=state:72"
```

**Para el fallback necesitas**:
1. La variable de entorno `CENSUS_API_KEY` (opcional pero recomendada)
2. Resolver nombres de municipios a FIPS codes. Los 78 municipios están en `data/municipios_pr.json` en el plugin root.
3. Resolver barrios a FIPS codes. Están en `data/barrios_pr.json`.

**Plugin root**: El directorio base de este skill, dos niveles arriba de este SKILL.md.

```bash
PLUGIN_ROOT="<plugin-root>"
# Leer FIPS de un municipio
cat "$PLUGIN_ROOT/data/municipios_pr.json" | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Buscar por nombre
for m in data:
    if 'vega baja' in m['nombre'].lower():
        print(m['fips'])
"
```

### Parsear respuesta del Census API

La respuesta es un JSON array-of-arrays donde la primera fila son headers:
```json
[
  ["NAME", "B01003_001E", "B01003_001M", "state", "county"],
  ["Vega Baja Municipio, Puerto Rico", "54414", "null", "72", "145"]
]
```

Siempre incluye la variable MOE (sufijo `M` en vez de `E`) para evaluación de calidad.

## Referencias

- `geographic-hierarchy.md` — Detalle completo de la jerarquía geográfica
- `dataset-guide.md` — Guía detallada de cada dataset
