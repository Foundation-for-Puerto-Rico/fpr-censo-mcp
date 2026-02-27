"""Tests para el Census API client."""

import pytest
import httpx
import respx

from src.census_client import CensusClient, CensusAPIError


@pytest.fixture
def client():
    return CensusClient(api_key="test_key")


@pytest.fixture
def mock_census_response():
    """Respuesta típica del Census API."""
    return [
        ["NAME", "B01003_001E", "B01003_001M", "state", "county"],
        ["Adjuntas Municipio, Puerto Rico", "17781", "0", "72", "001"],
        ["Aguada Municipio, Puerto Rico", "37560", "0", "72", "003"],
    ]


@respx.mock
@pytest.mark.asyncio
async def test_query_basic(client, mock_census_response):
    """Query básico parsea array-of-arrays a lista de dicts."""
    respx.get("https://api.census.gov/data/2022/acs/acs5").mock(
        return_value=httpx.Response(200, json=mock_census_response)
    )

    rows = await client.query(
        year=2022,
        dataset="acs/acs5",
        variables=["B01003_001E"],
        for_clause="county:*",
        in_clause="state:72",
        auto_moe=False,
    )

    assert len(rows) == 2
    assert rows[0]["NAME"] == "Adjuntas Municipio, Puerto Rico"
    assert rows[0]["B01003_001E"] == 17781
    assert rows[0]["county"] == "001"

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_query_auto_moe(client):
    """Auto-MOE añade variable _M correspondiente."""
    route = respx.get("https://api.census.gov/data/2022/acs/acs5").mock(
        return_value=httpx.Response(200, json=[
            ["NAME", "B01003_001E", "B01003_001M", "state"],
            ["Puerto Rico", "3221789", "0", "72"],
        ])
    )

    rows = await client.query(
        year=2022,
        dataset="acs/acs5",
        variables=["B01003_001E"],
        for_clause="state:72",
    )

    # Verify the request included MOE variable
    request = route.calls[0].request
    get_param = str(request.url.params.get("get", ""))
    assert "B01003_001M" in get_param

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_query_404_error(client):
    """Error HTTP genera CensusAPIError."""
    respx.get("https://api.census.gov/data/2022/acs/acs5").mock(
        return_value=httpx.Response(400, text="error: unknown variable")
    )

    with pytest.raises(CensusAPIError):
        await client.query(
            year=2022,
            dataset="acs/acs5",
            variables=["INVALID_VAR"],
            for_clause="county:*",
            in_clause="state:72",
        )

    await client.close()


@respx.mock
@pytest.mark.asyncio
async def test_query_no_content(client):
    """HTTP 204 genera error descriptivo."""
    respx.get("https://api.census.gov/data/2022/acs/acs5").mock(
        return_value=httpx.Response(204)
    )

    with pytest.raises(CensusAPIError) as exc_info:
        await client.query(
            year=2022,
            dataset="acs/acs5",
            variables=["B01003_001E"],
            for_clause="county:999",
            in_clause="state:72",
        )
    assert "no tiene datos" in str(exc_info.value).lower()

    await client.close()


def test_parse_response(client):
    """Parseo correcto de array-of-arrays."""
    data = [
        ["NAME", "B01003_001E", "state"],
        ["Puerto Rico", "3221789", "72"],
    ]
    rows = client._parse_response(data)
    assert len(rows) == 1
    assert rows[0]["B01003_001E"] == 3221789
    assert rows[0]["state"] == "72"  # geo fields preserved as string


def test_parse_response_empty(client):
    """Array vacío retorna lista vacía."""
    assert client._parse_response([]) == []
    assert client._parse_response([["header"]]) == []


def test_auto_add_moe(client):
    """Añade MOE para variables con sufijo E."""
    result = client._auto_add_moe(["B01003_001E", "NAME"])
    assert "B01003_001M" in result
    assert "NAME" in result
