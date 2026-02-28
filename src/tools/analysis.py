"""Tools de análisis — comparación, evaluación de calidad, contextualización."""

from __future__ import annotations

from src.census_client import CensusClient
from src.geography import GeographyResolver
from src.profiles import ProfileManager
from src.quality import (
    QualityAssessment,
    agregar_estimados,
    calcular_proporcion,
    evaluar_calidad,
    formato_estimado,
)


def register_analysis_tools(mcp, client: CensusClient, geo: GeographyResolver, profiles: ProfileManager):
    """Registra los tools de análisis en el servidor MCP."""

    @mcp.tool(
        name="censo_comparar",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_comparar(
        geografias: list[str],
        variables: list[str] | None = None,
        perfil: str | None = None,
        dataset: str = "acs/acs5",
        anio: int = 2022,
    ) -> str:
        """
        Compara indicadores entre dos o más geografías lado a lado.

        Señala diferencias estadísticamente significativas (cuando los
        intervalos de confianza no se solapan).

        Args:
            geografias: Lista de nombres de geografías (ej: ["Vega Baja", "Manatí", "Barceloneta"]).
            variables: Códigos de variables a comparar. Si None, usa perfil o resumen.
            perfil: Perfil temático a usar si no se dan variables específicas.
            dataset: Path del dataset (default: acs/acs5).
            anio: Año de los datos (default: 2022).
        """
        if len(geografias) < 2:
            return "Necesitas al menos 2 geografías para comparar."

        # Determinar variables
        if variables:
            var_codes = variables
        elif perfil:
            var_codes = profiles.get_variables_for_profile(perfil)
        else:
            var_codes = profiles.get_resumen_ejecutivo_variables()

        if not var_codes:
            return "No hay variables para comparar."

        # Consultar cada geografía
        results = {}
        for geo_name in geografias:
            resolved = geo.resolve(geo_name)
            if not resolved:
                results[geo_name] = {"error": f"No se pudo resolver '{geo_name}'"}
                continue
            try:
                rows = await client.query(
                    year=anio,
                    dataset=dataset,
                    variables=var_codes,
                    for_clause=resolved.for_clause,
                    in_clause=resolved.in_clause,
                )
                if rows:
                    results[geo_name] = rows[0]
                else:
                    results[geo_name] = {"error": "Sin datos"}
            except Exception as e:
                results[geo_name] = {"error": str(e)}

        # Formatear tabla comparativa
        lines = [f"# Comparación: {', '.join(geografias)}", f"*Fuente: {dataset}, {anio}*\n"]

        # Headers
        header = ["Indicador"] + list(results.keys())
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join("---" for _ in header) + "|")

        for var in var_codes:
            vdef = profiles.find_variable(var)
            var_name = vdef.nombre_es if vdef else var
            fmt = vdef.formato if vdef else "conteo"
            moe_code = var[:-1] + "M" if var.endswith("E") else None

            cols = [var_name]
            values_for_significance = []

            for geo_name in results:
                row = results[geo_name]
                if "error" in row:
                    cols.append(f"*{row['error']}*")
                    values_for_significance.append(None)
                    continue

                est = row.get(var)
                moe = row.get(moe_code) if moe_code else None

                if est is not None:
                    qa = evaluar_calidad(float(est), float(moe)) if moe is not None else None
                    val = formato_estimado(est, fmt, moe)
                    cols.append(f"{val} {qa.emoji if qa else ''}")
                    values_for_significance.append((float(est), float(moe) if moe else 0))
                else:
                    cols.append("N/D")
                    values_for_significance.append(None)

            lines.append("| " + " | ".join(cols) + " |")

            # Check significance between first two geographies
            if len(values_for_significance) >= 2:
                v1, v2 = values_for_significance[0], values_for_significance[1]
                if v1 and v2 and v1[1] > 0 and v2[1] > 0:
                    if _is_significant(v1[0], v1[1], v2[0], v2[1]):
                        diff = v1[0] - v2[0]
                        direction = "mayor" if diff > 0 else "menor"
                        lines.append(
                            f"| ↑ *{geografias[0]} es significativamente {direction} "
                            f"que {geografias[1]}* | | |"
                        )

        return "\n".join(lines)

    @mcp.tool(
        name="censo_evaluar_calidad",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_evaluar_calidad_tool(
        estimado: float,
        moe: float,
        nombre_variable: str | None = None,
    ) -> str:
        """
        Evalúa la confiabilidad estadística de un estimado del ACS.

        Calcula CV, clasifica confiabilidad, y sugiere acciones cuando
        un dato no es confiable.

        Args:
            estimado: El valor del estimado.
            moe: El Margin of Error (MOE) del estimado.
            nombre_variable: Nombre descriptivo opcional de la variable.
        """
        qa = evaluar_calidad(estimado, moe)
        var_label = nombre_variable or "este estimado"

        lines = [f"# Evaluación de calidad: {var_label}\n"]
        lines.append(f"- **Estimado**: {estimado:,.0f}")
        lines.append(f"- **MOE**: ±{moe:,.0f}")
        lines.append(f"- **CV**: {qa.cv:.1f}%")
        lines.append(f"- **Confiabilidad**: {qa.emoji} {qa.confiabilidad}")
        lines.append(f"- **Interpretación**: {qa.mensaje}")

        if qa.sugerencia:
            lines.append(f"\n**Sugerencia**: {qa.sugerencia}")

        lines.append("\n---")
        lines.append("**Referencia de clasificación:**")
        lines.append("- ✅ CV < 15% → Confiable")
        lines.append("- ⚠️ CV 15-30% → Usar con precaución")
        lines.append("- ❌ CV > 30% → No confiable")

        return "\n".join(lines)

    @mcp.tool(
        name="censo_contexto",
        annotations={"readOnlyHint": True, "destructiveHint": False},
    )
    async def censo_contexto(
        variable: str,
        geografia: str,
        dataset: str = "acs/acs5",
        anio: int = 2022,
    ) -> str:
        """
        Contextualiza un indicador comparándolo con PR y EE.UU.

        Dado un valor para una geografía específica, lo compara con
        la mediana de Puerto Rico y el valor nacional.

        Args:
            variable: Código de variable (ej: "B19013_001E").
            geografia: Nombre de la geografía local (ej: "Vega Baja").
            dataset: Path del dataset (default: acs/acs5).
            anio: Año de los datos (default: 2022).
        """
        vdef = profiles.find_variable(variable)
        var_name = vdef.nombre_es if vdef else variable
        fmt = vdef.formato if vdef else "conteo"
        moe_code = variable[:-1] + "M" if variable.endswith("E") else None

        # Resolver geografía local
        resolved = geo.resolve(geografia)
        if not resolved:
            return f"No se pudo resolver '{geografia}'."

        # Obtener datos: local, PR, y US
        comparisons = {
            geografia: (resolved.for_clause, resolved.in_clause),
            "Puerto Rico": ("state:72", ""),
            "Estados Unidos": ("us:1", ""),
        }

        values = {}
        for label, (for_c, in_c) in comparisons.items():
            try:
                rows = await client.query(
                    year=anio,
                    dataset=dataset,
                    variables=[variable],
                    for_clause=for_c,
                    in_clause=in_c if in_c else None,
                )
                if rows:
                    est = rows[0].get(variable)
                    moe = rows[0].get(moe_code) if moe_code else None
                    values[label] = (est, moe)
                else:
                    values[label] = (None, None)
            except Exception:
                values[label] = (None, None)

        # Obtener rango de municipios de PR
        try:
            all_munis = await client.query(
                year=anio,
                dataset=dataset,
                variables=[variable],
                for_clause="county:*",
                in_clause="state:72",
            )
            muni_values = sorted(
                [float(r[variable]) for r in all_munis if r.get(variable) is not None and float(r[variable]) > 0]
            )
        except Exception:
            muni_values = []

        # Formatear
        lines = [f"# Contexto: {var_name}", f"**Geografía**: {geografia} | **Fuente**: {dataset}, {anio}\n"]

        lines.append("| Nivel | Valor | MOE |")
        lines.append("|-------|-------|-----|")

        for label, (est, moe) in values.items():
            if est is not None:
                val_str = formato_estimado(est, fmt, moe)
                moe_str = f"±{int(abs(moe)):,}" if moe is not None and moe >= 0 else "—"
                lines.append(f"| **{label}** | {val_str} | {moe_str} |")
            else:
                lines.append(f"| **{label}** | N/D | — |")

        # Interpretación
        local_val = values.get(geografia, (None, None))[0]
        pr_val = values.get("Puerto Rico", (None, None))[0]
        us_val = values.get("Estados Unidos", (None, None))[0]

        if local_val is not None and pr_val is not None:
            lines.append("\n**Interpretación:**")
            if pr_val != 0:
                ratio = (float(local_val) / float(pr_val) - 1) * 100
                if abs(ratio) < 5:
                    lines.append(f"- Respecto a PR: similar al promedio ({ratio:+.1f}%)")
                elif ratio > 0:
                    lines.append(f"- Respecto a PR: **{ratio:.1f}% más alto** que el promedio de PR")
                else:
                    lines.append(f"- Respecto a PR: **{abs(ratio):.1f}% más bajo** que el promedio de PR")

            if us_val is not None and us_val != 0:
                ratio_us = (float(local_val) / float(us_val) - 1) * 100
                if ratio_us > 0:
                    lines.append(f"- Respecto a EE.UU.: {ratio_us:.1f}% más alto que el promedio nacional")
                else:
                    lines.append(f"- Respecto a EE.UU.: {abs(ratio_us):.1f}% más bajo que el promedio nacional")

        # Percentil entre municipios
        if muni_values and local_val is not None:
            local_float = float(local_val)
            below = sum(1 for v in muni_values if v <= local_float)
            percentile = (below / len(muni_values)) * 100
            lines.append(f"- Percentil entre municipios de PR: **{percentile:.0f}** (de {len(muni_values)} municipios)")

        return "\n".join(lines)


def _is_significant(est1: float, moe1: float, est2: float, moe2: float) -> bool:
    """Verifica si la diferencia entre dos estimados es estadísticamente significativa."""
    # Los intervalos no se solapan si |est1 - est2| > MOE1 + MOE2
    # Método conservador simplificado
    import math

    diff = abs(est1 - est2)
    se_diff = math.sqrt((moe1 / 1.645) ** 2 + (moe2 / 1.645) ** 2)
    z = diff / se_diff if se_diff > 0 else 0
    return z > 1.645  # 90% confidence
