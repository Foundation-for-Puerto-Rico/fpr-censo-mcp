"""Tests para el módulo de evaluación de calidad estadística."""

from src.quality import (
    agregar_estimados,
    calcular_proporcion,
    evaluar_calidad,
    formato_estimado,
)


def test_evaluar_calidad_confiable():
    """CV < 15% → confiable."""
    # Estimado 50000, MOE 3000 → CV ≈ 3.6%
    qa = evaluar_calidad(50000, 3000)
    assert qa.confiabilidad == "confiable"
    assert qa.emoji == "✅"
    assert qa.cv < 15


def test_evaluar_calidad_precaucion():
    """CV 15-30% → precaucion."""
    # Estimado 1000, MOE 300 → CV ≈ 18.2%
    qa = evaluar_calidad(1000, 300)
    assert qa.confiabilidad == "precaucion"
    assert qa.emoji == "⚠️"
    assert 15 <= qa.cv <= 30


def test_evaluar_calidad_no_confiable():
    """CV > 30% → no_confiable."""
    # Estimado 100, MOE 100 → CV ≈ 60.8%
    qa = evaluar_calidad(100, 100)
    assert qa.confiabilidad == "no_confiable"
    assert qa.emoji == "❌"
    assert qa.cv > 30


def test_evaluar_calidad_cero():
    """Estimado cero → no_aplica."""
    qa = evaluar_calidad(0, 50)
    assert qa.confiabilidad == "no_aplica"


def test_evaluar_calidad_moe_negativo():
    """MOE negativo (dato controlado) → confiable."""
    qa = evaluar_calidad(35000, -555555555)
    assert qa.confiabilidad == "confiable"


def test_agregar_estimados():
    """Suma con propagación de error."""
    suma, moe = agregar_estimados([1000, 2000, 3000], [100, 150, 200])
    assert suma == 6000
    # MOE = sqrt(100^2 + 150^2 + 200^2) = sqrt(10000+22500+40000) ≈ 269.3
    assert 269 <= moe <= 270


def test_calcular_proporcion():
    """Proporción derivada con propagación de error."""
    prop, moe = calcular_proporcion(500, 80, 2000, 150)
    assert abs(prop - 0.25) < 0.001
    assert moe > 0


def test_calcular_proporcion_cero():
    """Total cero → retorna 0."""
    prop, moe = calcular_proporcion(500, 80, 0, 150)
    assert prop == 0.0
    assert moe == 0.0


def test_formato_estimado_conteo():
    assert formato_estimado(35000, "conteo") == "35,000"
    assert formato_estimado(35000, "conteo", 1500) == "35,000 (±1,500)"


def test_formato_estimado_moneda():
    assert formato_estimado(45000, "moneda") == "$45,000"
    assert formato_estimado(45000, "moneda", 3000) == "$45,000 (±$3,000)"


def test_formato_estimado_none():
    assert formato_estimado(None, "conteo") == "N/D"
