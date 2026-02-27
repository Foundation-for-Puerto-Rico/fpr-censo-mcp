"""Tools de descubrimiento — explorar datasets, variables y geografías."""

from __future__ import annotations

import os

from src.census_client import CensusClient
from src.geography import GeographyResolver
from src.profiles import ProfileManager


def register_discovery_tools(mcp, client: CensusClient, geo: GeographyResolver, profiles: ProfileManager):
    """Registra los tools de descubrimiento en el servidor MCP."""

    @mcp.tool(
        name="censo_estado",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_estado() -> str:
        """
        Muestra el estado de configuración del servidor Census MCP.

        Verifica si el API key está configurado y devuelve instrucciones
        de configuración si no lo está. Llama este tool al inicio de
        cualquier sesión para verificar que todo esté listo.
        """
        has_key = bool(os.environ.get("CENSUS_API_KEY", ""))
        lines = ["# Estado del Census MCP Server\n"]

        if has_key:
            lines.append("- **API Key**: ✅ Configurada")
            lines.append("- **Estado**: Listo para consultas")
            lines.append("- **Rate limit**: Amplio (con API key)")
            lines.append("\nTodos los tools están disponibles. Puedes hacer consultas sin restricciones.")
        else:
            lines.append("- **API Key**: ⚠️ No configurada")
            lines.append("- **Estado**: Funcional con limitaciones")
            lines.append("- **Rate limit**: Restringido (sin API key)")
            lines.append("")
            lines.append("## Cómo obtener tu API Key (gratis)")
            lines.append("")
            lines.append("El Census Bureau ofrece API keys gratuitas. Sin key el servidor funciona, "
                         "pero con rate limiting que puede causar errores en consultas frecuentes.")
            lines.append("")
            lines.append("### Pasos:")
            lines.append("1. Ve a: **https://api.census.gov/data/key_signup.html**")
            lines.append("2. Llena el formulario con tu nombre y email organizacional de FPR")
            lines.append("3. Recibirás la key por email en unos minutos")
            lines.append("4. Configúrala como variable de entorno:")
            lines.append("   ```")
            lines.append("   export CENSUS_API_KEY=tu_key_aquí")
            lines.append("   ```")
            lines.append("5. Reinicia el servidor MCP")
            lines.append("")
            lines.append("### Configuración en Claude Desktop / .mcp.json")
            lines.append("Si usas Claude Desktop, puedes agregar la key en la configuración:")
            lines.append("```json")
            lines.append('{')
            lines.append('  "mcpServers": {')
            lines.append('    "fpr-censo": {')
            lines.append('      "url": "http://TU_SERVIDOR:8001/mcp",')
            lines.append('      "env": {')
            lines.append('        "CENSUS_API_KEY": "tu_key_aquí"')
            lines.append('      }')
            lines.append('    }')
            lines.append('  }')
            lines.append('}')
            lines.append("```")
            lines.append("")
            lines.append("⚠️ **Mientras tanto**, puedes usar el servidor sin key. "
                         "Las consultas funcionarán pero pueden ser más lentas o fallar si haces muchas seguidas.")

        return "\n".join(lines)

    @mcp.tool(
        name="censo_listar_datasets",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_listar_datasets(año: int | None = None) -> str:
        """
        Lista los datasets del Census Bureau disponibles para Puerto Rico.

        Devuelve nombre, path del API, años disponibles, y descripción
        de cada dataset. Filtra automáticamente a los datasets que tienen
        datos para PR (state:72).

        Args:
            año: Filtrar datasets que tengan datos para este año específico.
        """
        datasets = await client.get_available_datasets(year=año)

        if not datasets:
            return "No se encontraron datasets disponibles" + (f" para el año {año}" if año else "") + "."

        lines = ["# Datasets del Census Bureau disponibles para Puerto Rico\n"]
        for ds in datasets:
            years = ds["años"]
            year_range = f"{min(years)}-{max(years)}" if len(years) > 2 else ", ".join(str(y) for y in years)
            lines.append(f"## {ds['nombre']}")
            lines.append(f"- **Path API**: `{ds['path']}`")
            lines.append(f"- **Años**: {year_range}")
            lines.append(f"- **Granularidad en PR**: {ds['granularidad_pr']}")
            lines.append(f"- **Descripción**: {ds['descripcion']}")
            lines.append("")

        lines.append("---")
        lines.append("💡 **Recomendación**: Para la mayoría de análisis, usa `acs/acs5` (ACS 5-Year). "
                      "Cubre todas las áreas geográficas de PR hasta nivel de block group.")
        return "\n".join(lines)

    @mcp.tool(
        name="censo_buscar_variables",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_buscar_variables(
        keyword: str,
        dataset: str = "acs/acs5",
        año: int = 2022,
    ) -> str:
        """
        Busca variables del Census Bureau por keyword en español o inglés.

        Primero busca en el catálogo curado de variables relevantes para FPR.
        Si no encuentra resultados suficientes, busca en el API del Census Bureau.

        Args:
            keyword: Término de búsqueda (ej: "ingreso", "pobreza", "housing").
            dataset: Dataset donde buscar (default: acs/acs5).
            año: Año del dataset (default: 2022).
        """
        lines = [f"# Búsqueda de variables: \"{keyword}\"\n"]

        # Primero: catálogo curado
        curated = profiles.search_variables(keyword)
        if curated:
            lines.append("## Variables curadas (catálogo FPR)\n")
            lines.append("| Código | Nombre (ES) | Nombre (EN) | MOE | Formato |")
            lines.append("|--------|-------------|-------------|-----|---------|")
            for v in curated:
                lines.append(f"| `{v.code}` | {v.nombre_es} | {v.nombre_en} | `{v.moe_code}` | {v.formato} |")
            lines.append("")

        # Si pocas curadas, buscar en API
        if len(curated) < 3:
            api_results = await client.search_variables(dataset, año, keyword)
            if api_results:
                lines.append(f"## Variables del Census API ({dataset}, {año})\n")
                lines.append("| Código | Descripción | Concepto |")
                lines.append("|--------|-------------|----------|")
                for v in api_results[:20]:
                    lines.append(f"| `{v['code']}` | {v['label'][:60]} | {v.get('concept', '')[:40]} |")
                lines.append("")
                if len(api_results) > 20:
                    lines.append(f"*... y {len(api_results) - 20} más. Refina tu búsqueda para resultados más específicos.*")

        if len(curated) == 0 and not any("Census API" in l for l in lines):
            lines.append("No se encontraron variables para ese término. Intenta con sinónimos en inglés.")

        return "\n".join(lines)

    @mcp.tool(
        name="censo_listar_geografias",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_listar_geografias(
        dataset: str = "acs/acs5",
        año: int = 2022,
    ) -> str:
        """
        Lista los niveles geográficos disponibles para un dataset.

        Args:
            dataset: Path del dataset (default: acs/acs5).
            año: Año del dataset (default: 2022).
        """
        geos = await client.get_geographies(dataset, año)

        lines = [f"# Niveles geográficos: {dataset} ({año})\n"]
        lines.append("| Nivel (Census) | Nivel (PR) | Requiere |")
        lines.append("|----------------|------------|----------|")
        for g in geos:
            requires = ", ".join(g["requires"]) if g["requires"] else "—"
            lines.append(f"| {g['nombre']} | {g['nombre_local']} | {requires} |")

        lines.append("\n---")
        lines.append("**Jerarquía en PR**: Estado → Municipio → Barrio → Tract → Block Group → Block")
        return "\n".join(lines)

    @mcp.tool(
        name="censo_listar_municipios",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_listar_municipios() -> str:
        """
        Lista los 78 municipios de Puerto Rico con sus FIPS codes.

        Devuelve nombre, FIPS code y región de cada municipio.
        Útil para resolver nombres a códigos antes de hacer consultas.
        """
        municipios = geo.list_municipios()

        lines = ["# Los 78 municipios de Puerto Rico\n"]
        lines.append("| Municipio | FIPS | Región |")
        lines.append("|-----------|------|--------|")
        for m in municipios:
            lines.append(f"| {m.nombre} | {m.fips} | {m.region} |")

        lines.append(f"\nTotal: {len(municipios)} municipios")
        return "\n".join(lines)

    @mcp.tool(
        name="censo_listar_barrios",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_listar_barrios(municipio: str) -> str:
        """
        Lista los barrios (county subdivisions) dentro de un municipio.

        Acepta nombre o FIPS del municipio.

        Args:
            municipio: Nombre del municipio (ej: "Vega Baja") o FIPS (ej: "145").
        """
        barrios = geo.list_barrios(municipio)

        if not barrios:
            return f"No se encontraron barrios para '{municipio}'. Verifica el nombre del municipio."

        # Get municipio name for header
        resolved = geo.resolve(municipio, level="county")
        muni_name = resolved.nombre if resolved else municipio

        lines = [f"# Barrios de {muni_name}\n"]
        lines.append("| Barrio | FIPS |")
        lines.append("|--------|------|")
        for b in barrios:
            lines.append(f"| {b.nombre} | {b.fips} |")

        lines.append(f"\nTotal: {len(barrios)} barrios")
        return "\n".join(lines)
