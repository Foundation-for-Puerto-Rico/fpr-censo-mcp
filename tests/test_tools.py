"""Tests de integración para los MCP tools con datos mock."""

import pytest
import httpx
import respx

from mcp.server.fastmcp import FastMCP

from src.census_client import CensusClient
from src.geography import GeographyResolver
from src.profiles import ProfileManager
from src.tools.discovery import register_discovery_tools
from src.tools.query import register_query_tools
from src.tools.analysis import register_analysis_tools


@pytest.fixture
def setup_mcp():
    """Configura un MCP server con tools registrados para testing."""
    mcp = FastMCP("test-censo")
    client = CensusClient(api_key="test")
    geo = GeographyResolver()
    profiles = ProfileManager()

    register_discovery_tools(mcp, client, geo, profiles)
    register_query_tools(mcp, client, geo, profiles)
    register_analysis_tools(mcp, client, geo, profiles)

    return mcp, client, geo, profiles


def test_tools_registered(setup_mcp):
    """Verifica que todos los 12 tools se registren."""
    mcp, *_ = setup_mcp

    # FastMCP stores tools internally; verify by listing them
    tool_names = [
        "censo_estado",
        "censo_listar_datasets",
        "censo_buscar_variables",
        "censo_listar_geografias",
        "censo_listar_municipios",
        "censo_listar_barrios",
        "censo_consultar",
        "censo_perfil",
        "censo_serie_temporal",
        "censo_comparar",
        "censo_evaluar_calidad",
        "censo_contexto",
    ]
    # The tools should be callable functions registered on the mcp
    # We verify they exist by checking the internal registry
    registered = list(mcp._tool_manager._tools.keys())
    for name in tool_names:
        assert name in registered, f"Tool '{name}' no está registrado"


def test_geography_resolver_integration():
    """Test que el geography resolver funciona con datos reales."""
    geo = GeographyResolver()

    # Listar municipios
    munis = geo.list_municipios()
    assert len(munis) == 78

    # Resolver Vega Baja
    result = geo.resolve("Vega Baja")
    assert result is not None
    assert result.nivel == "county"

    # Resolver Puerto Rico
    pr = geo.resolve("PR")
    assert pr is not None
    assert pr.for_clause == "state:72"


def test_profiles_integration():
    """Test que los perfiles cargan correctamente."""
    pm = ProfileManager()

    # Listar perfiles
    perfiles = pm.list_profiles()
    assert len(perfiles) >= 5

    # Obtener variables demográficas
    demo = pm.get_profile("demografico")
    assert len(demo) > 0
    assert any(v.code == "B01003_001E" for v in demo)

    # Buscar por keyword
    results = pm.search_variables("ingreso")
    assert len(results) > 0
    assert any("ingreso" in v.nombre_es.lower() for v in results)


@respx.mock
@pytest.mark.asyncio
async def test_censo_listar_datasets(setup_mcp):
    """Test del tool listar datasets."""
    mcp, client, _, _ = setup_mcp

    # Call the underlying function directly
    result = await client.get_available_datasets()
    assert len(result) > 0
    assert any("acs" in d["path"] for d in result)

    await client.close()
