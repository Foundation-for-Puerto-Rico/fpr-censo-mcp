"""Evaluación de calidad estadística para estimados del ACS."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class QualityAssessment:
    """Resultado de la evaluación de calidad de un estimado ACS."""

    estimado: float
    moe: float
    cv: float  # Coeficiente de variación (%)
    confiabilidad: str  # "confiable" | "precaucion" | "no_confiable" | "no_aplica"
    emoji: str  # ✅ | ⚠️ | ❌ | ➖
    mensaje: str
    sugerencia: str | None = None


def evaluar_calidad(estimado: float, moe: float) -> QualityAssessment:
    """
    Evalúa la confiabilidad estadística de un estimado del ACS.

    Fórmula: CV = (MOE / 1.645) / Estimado × 100

    Clasificación:
      CV < 15%   → confiable
      CV 15-30%  → precaucion
      CV > 30%   → no_confiable
      Estimado 0 → no_aplica
    """
    if estimado == 0 or moe is None:
        return QualityAssessment(
            estimado=estimado,
            moe=moe or 0,
            cv=0,
            confiabilidad="no_aplica",
            emoji="➖",
            mensaje="El estimado es cero o no tiene MOE. No se puede evaluar confiabilidad.",
        )

    # MOE especiales del Census
    if moe < 0:
        # -555555555 = "dato controlado" (estimado del Census, no muestreo)
        # -333333333 = mediana de distribución abierta
        # -222222222 = mediana del intervalo más bajo/alto
        return QualityAssessment(
            estimado=estimado,
            moe=moe,
            cv=0,
            confiabilidad="confiable",
            emoji="✅",
            mensaje="Este dato proviene de un conteo o estimado controlado, no de muestreo.",
        )

    se = moe / 1.645  # Standard error
    cv = (se / abs(estimado)) * 100

    if cv < 15:
        return QualityAssessment(
            estimado=estimado,
            moe=moe,
            cv=round(cv, 1),
            confiabilidad="confiable",
            emoji="✅",
            mensaje=f"CV de {cv:.1f}% — estimado confiable.",
        )
    elif cv <= 30:
        return QualityAssessment(
            estimado=estimado,
            moe=moe,
            cv=round(cv, 1),
            confiabilidad="precaucion",
            emoji="⚠️",
            mensaje=f"CV de {cv:.1f}% — usar con precaución.",
            sugerencia="Considerar usar ACS 5-Year en vez de 1-Year, o agregar geografías adyacentes.",
        )
    else:
        return QualityAssessment(
            estimado=estimado,
            moe=moe,
            cv=round(cv, 1),
            confiabilidad="no_confiable",
            emoji="❌",
            mensaje=f"CV de {cv:.1f}% — estimado NO confiable.",
            sugerencia="El margen de error es muy alto. Considerar: (1) usar ACS 5-Year, "
            "(2) agregar geografías para aumentar el tamaño de muestra, "
            "(3) usar un nivel geográfico más alto (municipio en vez de barrio).",
        )


def agregar_estimados(estimados: list[float], moes: list[float]) -> tuple[float, float]:
    """
    Agrega estimados ACS sumándolos con propagación de error.

    Para sumar estimados:
      Suma = sum(estimados)
      MOE_suma = sqrt(sum(moe_i^2))

    Returns:
        (suma, moe_propagado)
    """
    suma = sum(estimados)
    moe_propagado = math.sqrt(sum(m ** 2 for m in moes))
    return suma, round(moe_propagado, 1)


def calcular_proporcion(
    parte: float, moe_parte: float, total: float, moe_total: float
) -> tuple[float, float]:
    """
    Calcula una proporción derivada con propagación de error.

    Fórmula:
      P = parte / total
      MOE_P = (1/total) * sqrt(moe_parte^2 - (P^2 * moe_total^2))

    Si el valor bajo el sqrt es negativo:
      MOE_P = (1/total) * sqrt(moe_parte^2 + (P^2 * moe_total^2))

    Returns:
        (proporcion, moe_proporcion)
    """
    if total == 0:
        return 0.0, 0.0

    p = parte / total
    inner = moe_parte ** 2 - (p ** 2 * moe_total ** 2)

    if inner < 0:
        # Usar fórmula alternativa
        inner = moe_parte ** 2 + (p ** 2 * moe_total ** 2)

    moe_p = (1 / total) * math.sqrt(inner)
    return round(p, 6), round(moe_p, 6)


def formato_estimado(valor: float | int | None, formato: str, moe: float | None = None) -> str:
    """
    Formatea un estimado para presentación.

    Args:
        valor: El valor numérico
        formato: "conteo" | "moneda" | "porcentaje" | "mediana"
        moe: Margin of error opcional
    """
    if valor is None:
        return "N/D"

    if formato == "moneda":
        text = f"${valor:,.0f}"
    elif formato == "porcentaje":
        text = f"{valor:.1f}%"
    elif formato == "mediana":
        if isinstance(valor, float) and not valor.is_integer():
            text = f"{valor:,.1f}"
        else:
            text = f"{int(valor):,}"
    else:  # conteo
        text = f"{int(valor):,}"

    if moe is not None and moe >= 0:
        if formato == "moneda":
            text += f" (±${abs(moe):,.0f})"
        elif formato == "porcentaje":
            text += f" (±{abs(moe):.1f}%)"
        else:
            text += f" (±{int(abs(moe)):,})"

    return text
