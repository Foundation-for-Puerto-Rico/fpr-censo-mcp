# fpr-censo-mcp

MCP Server que conecta a Claude con datos del U.S. Census Bureau, optimizado para Puerto Rico. Desarrollado para [Foundation for Puerto Rico](https://www.foundationforpuertorico.org/).

Provee 12 tools para consultar datos demográficos, económicos, de vivienda, educación, salud e infraestructura de los 78 municipios y sus barrios. Todos los estimados del ACS incluyen Margin of Error (MOE) y evaluación de confiabilidad.

## Conectar

El servidor está disponible en `https://censo.wcrprag.shop/mcp`.

### Claude Desktop / Claude Code

Agrega a tu `.mcp.json` o `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fpr-censo": {
      "type": "http",
      "url": "https://censo.wcrprag.shop/mcp"
    }
  }
}
```

### Claude Teams (Connector)

Un administrador de la organización puede agregar el Connector en Settings > Integrations con la URL `https://censo.wcrprag.shop/mcp`.

## Tools disponibles

### Exploración

| Tool | Qué hace |
|------|----------|
| `censo_estado` | Verifica configuración del servidor y API key |
| `censo_listar_datasets` | Datasets disponibles para PR con años |
| `censo_buscar_variables` | Busca variables por keyword en español o inglés |
| `censo_listar_geografias` | Niveles geográficos disponibles |
| `censo_listar_municipios` | Los 78 municipios con FIPS codes |
| `censo_listar_barrios` | Barrios dentro de un municipio |

### Consulta

| Tool | Qué hace |
|------|----------|
| `censo_consultar` | Query flexible: variables, geografía, dataset, año |
| `censo_perfil` | Perfil temático pre-configurado (demográfico, económico, etc.) |
| `censo_serie_temporal` | Una variable a través de múltiples años |

### Análisis

| Tool | Qué hace |
|------|----------|
| `censo_comparar` | Compara indicadores entre 2+ geografías |
| `censo_evaluar_calidad` | Evalúa confiabilidad estadística (MOE/CV) |
| `censo_contexto` | Contextualiza un dato vs. PR y EE.UU. |

## Perfiles temáticos

Usados por `censo_perfil` para obtener indicadores pre-seleccionados:

- **demografico** — Población, edad, sexo, raza/etnicidad
- **economico** — Ingreso, pobreza, empleo/desempleo
- **vivienda** — Unidades, ocupación, valor, renta
- **educacion** — Nivel educativo, matrícula escolar
- **salud_social** — Seguro médico, discapacidad, idioma
- **infraestructura** — Internet, vehículos, transporte

## Ejemplos de uso

Una vez conectado, pídele a Claude cosas como:

- "Consulta la población de Vega Baja"
- "Dame el perfil económico de Manatí"
- "Compara la mediana de ingreso entre San Juan, Bayamón y Carolina"
- "Muéstrame la tendencia de población de PR del 2010 al 2023"
- "Lista los barrios de Ponce con sus FIPS codes"

## Evaluación de calidad

Cada estimado del ACS incluye evaluación automática:

| CV | Clasificación | Significado |
|----|---------------|-------------|
| < 15% | ✅ Confiable | Dato robusto |
| 15-30% | ⚠️ Precaución | Usar con cuidado |
| > 30% | ❌ No confiable | Considerar agregar geografías |

## Desarrollo local

```bash
# Instalar
pip install -e ".[dev]"

# API key (gratis)
export CENSUS_API_KEY=tu_key  # https://api.census.gov/data/key_signup.html

# Correr local (stdio)
python -m src.server

# Correr como HTTP server
python -m src.server --transport streamable-http --port 8001

# Tests
pytest tests/
```

## Deploy

El servidor corre en una VM de GCP con Caddy como reverse proxy (auto-HTTPS).

```bash
export CENSUS_API_KEY=tu_key
./deploy/deploy.sh
```

## Fuente de datos

U.S. Census Bureau Data API. Dataset principal: ACS 5-Year Estimates (`acs/acs5`), que cubre todas las áreas geográficas de PR hasta nivel de block group. Año default: 2023.
