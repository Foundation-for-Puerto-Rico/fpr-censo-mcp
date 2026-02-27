"""Tools de consulta — queries flexibles, perfiles temáticos, series temporales."""

from __future__ import annotations

from typing import Any

from src.census_client import CensusClient
from src.geography import GeographyResolver
from src.profiles import PERFIL_NOMBRES, ProfileManager
from src.quality import evaluar_calidad, formato_estimado


def register_query_tools(mcp, client: CensusClient, geo: GeographyResolver, profiles: ProfileManager):
    """Registra los tools de consulta en el servidor MCP."""

    @mcp.tool(
        name="censo_consultar",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_consultar(
        variables: list[str],
        geografia: str = "todos los municipios",
        dataset: str = "acs/acs5",
        año: int = 2022,
        nivel: str | None = None,
    ) -> str:
        """
        Consulta flexible al Census Bureau Data API.

        Acepta nombres de municipios/barrios en español — los resuelve
        automáticamente a FIPS codes. Siempre incluye MOE y evaluación
        de calidad para estimados del ACS.

        Args:
            variables: Lista de códigos de variables (ej: ["B01003_001E", "B19013_001E"]).
            geografia: Nombre de geografía (ej: "Vega Baja", "todos los municipios", "PR").
            dataset: Path del dataset (default: acs/acs5).
            año: Año de los datos (default: 2022).
            nivel: Nivel geográfico a forzar (ej: "county", "county subdivision").
        """
        # Resolver geografía
        geo_lower = geografia.lower().strip()

        if geo_lower in ("todos los municipios", "all", "*"):
            for_clause, in_clause = geo.resolve_for_all_municipios()
        elif "barrios de" in geo_lower or "barrios en" in geo_lower:
            muni_name = geo_lower.replace("barrios de ", "").replace("barrios en ", "").strip()
            result = geo.resolve_for_barrios_in(muni_name)
            if not result:
                return f"No se encontró el municipio '{muni_name}'. Usa `censo_listar_municipios` para ver la lista."
            for_clause, in_clause = result
        else:
            resolved = geo.resolve(geografia, level=nivel)
            if not resolved:
                return (
                    f"No se pudo resolver la geografía '{geografia}'. "
                    "Usa `censo_listar_municipios` o `censo_listar_barrios` para buscar nombres válidos."
                )
            for_clause = resolved.for_clause
            in_clause = resolved.in_clause

        try:
            rows = await client.query(
                year=año,
                dataset=dataset,
                variables=variables,
                for_clause=for_clause,
                in_clause=in_clause,
            )
        except Exception as e:
            return f"Error al consultar el Census API: {e}"

        if not rows:
            return "La consulta no devolvió resultados. Verifica los parámetros."

        return _format_query_results(rows, variables, profiles, dataset, año, geografia)

    @mcp.tool(
        name="censo_perfil",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_perfil(
        geografia: str,
        perfil: str | None = None,
        dataset: str = "acs/acs5",
        año: int = 2022,
    ) -> str:
        """
        Genera un perfil temático para una geografía dada.

        Usa variables pre-seleccionadas del perfil indicado. Si no se
        indica perfil, devuelve un resumen ejecutivo con indicadores
        clave de todos los perfiles.

        Args:
            geografia: Nombre de la geografía (ej: "Vega Baja", "Puerto Rico").
            perfil: Perfil temático (demografico, economico, vivienda, educacion, salud_social, infraestructura). Si None, resumen ejecutivo.
            dataset: Path del dataset (default: acs/acs5).
            año: Año de los datos (default: 2022).
        """
        # Resolver geografía
        resolved = geo.resolve(geografia)
        if not resolved:
            return f"No se pudo resolver '{geografia}'. Usa `censo_listar_municipios` para ver nombres válidos."

        # Determinar variables
        if perfil:
            if perfil not in PERFIL_NOMBRES:
                available = ", ".join(PERFIL_NOMBRES.keys())
                return f"Perfil '{perfil}' no válido. Perfiles disponibles: {available}"
            var_defs = profiles.get_profile(perfil)
            var_codes = [v.code for v in var_defs]
            title = f"Perfil {PERFIL_NOMBRES[perfil]}"
        else:
            var_codes = profiles.get_resumen_ejecutivo_variables()
            title = "Resumen Ejecutivo"

        if not var_codes:
            return "No hay variables definidas para este perfil."

        try:
            rows = await client.query(
                year=año,
                dataset=dataset,
                variables=var_codes,
                for_clause=resolved.for_clause,
                in_clause=resolved.in_clause,
            )
        except Exception as e:
            return f"Error al consultar el Census API: {e}"

        if not rows:
            return "No se obtuvieron datos para esta geografía y perfil."

        # Tomar el primer (y generalmente único) row
        row = rows[0]
        geo_name = row.get("NAME", resolved.nombre)

        lines = [f"# {title}: {geo_name}", f"*Fuente: {dataset}, {año}*\n"]

        if perfil:
            var_defs_to_show = profiles.get_profile(perfil)
        else:
            # Resumen ejecutivo: buscar cada variable
            var_defs_to_show = [profiles.find_variable(c) for c in var_codes]
            var_defs_to_show = [v for v in var_defs_to_show if v is not None]

        lines.append("| Indicador | Valor | MOE | Calidad |")
        lines.append("|-----------|-------|-----|---------|")

        for vdef in var_defs_to_show:
            est = row.get(vdef.code)
            moe = row.get(vdef.moe_code)
            if est is None:
                continue

            qa = evaluar_calidad(float(est), float(moe)) if moe is not None else None
            val_fmt = formato_estimado(est, vdef.formato, moe)

            if moe is not None and moe >= 0:
                moe_fmt = f"±{int(abs(moe)):,}" if vdef.formato != "moneda" else f"±${int(abs(moe)):,}"
            else:
                moe_fmt = "—"

            quality_str = f"{qa.emoji} {qa.confiabilidad}" if qa else "—"
            lines.append(f"| {vdef.nombre_es} | {formato_estimado(est, vdef.formato)} | {moe_fmt} | {quality_str} |")

        return "\n".join(lines)

    @mcp.tool(
        name="censo_serie_temporal",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_serie_temporal(
        variable: str,
        geografia: str,
        año_inicio: int = 2010,
        año_fin: int = 2022,
        dataset: str = "acs/acs5",
    ) -> str:
        """
        Obtiene una variable a través de múltiples años para ver tendencias.

        Args:
            variable: Código de variable (ej: "B01003_001E" para población).
            geografia: Nombre de geografía (ej: "Vega Baja", "Puerto Rico").
            año_inicio: Año inicial del rango (default: 2010).
            año_fin: Año final del rango (default: 2022).
            dataset: Path del dataset (default: acs/acs5).
        """
        resolved = geo.resolve(geografia)
        if not resolved:
            return f"No se pudo resolver '{geografia}'."

        # Variable info
        vdef = profiles.find_variable(variable)
        var_name = vdef.nombre_es if vdef else variable
        var_fmt = vdef.formato if vdef else "conteo"

        lines = [f"# Serie temporal: {var_name}", f"**Geografía**: {resolved.nombre}"]
        lines.append(f"**Fuente**: {dataset}, {año_inicio}-{año_fin}\n")
        lines.append("| Año | Valor | MOE | Calidad |")
        lines.append("|-----|-------|-----|---------|")

        moe_code = variable[:-1] + "M" if variable.endswith("E") else None
        prev_val = None

        for year in range(año_inicio, año_fin + 1):
            try:
                rows = await client.query(
                    year=year,
                    dataset=dataset,
                    variables=[variable],
                    for_clause=resolved.for_clause,
                    in_clause=resolved.in_clause,
                    auto_moe=True,
                )
                if rows:
                    row = rows[0]
                    est = row.get(variable)
                    moe = row.get(moe_code) if moe_code else None

                    if est is not None:
                        qa = evaluar_calidad(float(est), float(moe)) if moe is not None else None
                        val_str = formato_estimado(est, var_fmt)

                        # Calcular cambio
                        change = ""
                        if prev_val is not None and est != 0:
                            pct = ((est - prev_val) / abs(prev_val)) * 100
                            change = f" ({pct:+.1f}%)"
                        prev_val = est

                        moe_str = f"±{int(abs(moe)):,}" if moe is not None and moe >= 0 else "—"
                        q_str = qa.emoji if qa else ""
                        lines.append(f"| {year} | {val_str}{change} | {moe_str} | {q_str} |")
                    else:
                        lines.append(f"| {year} | N/D | — | — |")
            except Exception:
                lines.append(f"| {year} | Error | — | — |")

        return "\n".join(lines)


def _format_query_results(
    rows: list[dict[str, Any]],
    variables: list[str],
    profiles: ProfileManager,
    dataset: str,
    año: int,
    geografia: str,
) -> str:
    """Formatea resultados de query en markdown."""
    lines = [f"# Consulta: {dataset} ({año})", f"**Geografía**: {geografia}\n"]

    # Build headers
    var_defs = {v: profiles.find_variable(v) for v in variables}
    headers = ["Nombre"]
    for v in variables:
        vd = var_defs.get(v)
        name = vd.nombre_es if vd else v
        headers.append(name)
        # Add quality column
        moe_code = v[:-1] + "M" if v.endswith("E") else None
        if moe_code and any(moe_code in row for row in rows[:1]):
            headers.append("Calidad")

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")

    for row in rows:
        cols = [str(row.get("NAME", ""))]
        for v in variables:
            vd = var_defs.get(v)
            est = row.get(v)
            fmt = vd.formato if vd else "conteo"
            moe_code = v[:-1] + "M" if v.endswith("E") else None
            moe = row.get(moe_code) if moe_code else None

            cols.append(formato_estimado(est, fmt, moe))

            if moe_code and moe_code in row:
                qa = evaluar_calidad(float(est), float(moe)) if est is not None and moe is not None else None
                cols.append(qa.emoji if qa else "—")

        lines.append("| " + " | ".join(cols) + " |")

    lines.append(f"\n*{len(rows)} resultados*")
    return "\n".join(lines)
