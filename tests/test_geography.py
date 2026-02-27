"""Tests para el módulo de geografía."""

from src.geography import GeographyResolver


def test_list_municipios():
    """Debe listar los 78 municipios de PR."""
    resolver = GeographyResolver()
    municipios = resolver.list_municipios()
    assert len(municipios) == 78


def test_resolve_municipio_nombre():
    """Resuelve un municipio por nombre."""
    resolver = GeographyResolver()
    result = resolver.resolve("Vega Baja")
    assert result is not None
    assert result.nivel == "county"
    assert result.fips == "145"  # Vega Baja FIPS (Census Bureau)
    assert result.for_clause.startswith("county:")
    assert result.in_clause == "state:72"


def test_resolve_municipio_case_insensitive():
    """Resolución case-insensitive."""
    resolver = GeographyResolver()
    result = resolver.resolve("san juan")
    assert result is not None
    assert result.nombre == "San Juan"


def test_resolve_municipio_sin_acentos():
    """Resolución sin acentos."""
    resolver = GeographyResolver()
    result = resolver.resolve("Bayamon")
    assert result is not None
    assert result.nombre == "Bayamón"


def test_resolve_pr():
    """Puerto Rico como state."""
    resolver = GeographyResolver()
    result = resolver.resolve("Puerto Rico")
    assert result is not None
    assert result.nivel == "state"
    assert result.for_clause == "state:72"


def test_resolve_unknown():
    """Nombre desconocido retorna None."""
    resolver = GeographyResolver()
    result = resolver.resolve("Ciudad Inexistente XYZ")
    assert result is None


def test_list_barrios():
    """Lista barrios de un municipio."""
    resolver = GeographyResolver()
    barrios = resolver.list_barrios("Ponce")
    assert len(barrios) > 0
    ponce_fips = barrios[0].municipio_fips
    assert all(b.municipio_fips == ponce_fips for b in barrios)


def test_resolve_for_all_municipios():
    """Genera cláusulas para todos los municipios."""
    resolver = GeographyResolver()
    for_c, in_c = resolver.resolve_for_all_municipios()
    assert for_c == "county:*"
    assert in_c == "state:72"


def test_get_municipio_by_fips():
    """Busca municipio por FIPS."""
    resolver = GeographyResolver()
    muni = resolver.get_municipio_by_fips("127")
    assert muni is not None
    assert muni.nombre == "San Juan"
