"""Cliente async para el U.S. Census Bureau Data API."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache: 512 entradas, TTL 24 horas
_cache: TTLCache[str, list[dict[str, Any]]] = TTLCache(maxsize=512, ttl=86400)


def _cache_key(year: int, dataset: str, variables: tuple[str, ...], for_clause: str, in_clause: str | None) -> str:
    return f"{year}:{dataset}:{','.join(variables)}:{for_clause}:{in_clause or ''}"


class CensusAPIError(Exception):
    """Error al comunicarse con el Census API."""

    def __init__(self, message: str, status_code: int | None = None, suggestion: str | None = None):
        self.status_code = status_code
        self.suggestion = suggestion
        super().__init__(message)


class CensusClient:
    """Cliente async para el U.S. Census Bureau Data API."""

    BASE_URL = "https://api.census.gov/data"
    MAX_RETRIES = 3
    BACKOFF_BASE = 1.0  # segundos

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("CENSUS_API_KEY", "")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_url(self, year: int, dataset: str) -> str:
        return f"{self.BASE_URL}/{year}/{dataset}"

    def _auto_add_moe(self, variables: list[str]) -> list[str]:
        """Añade automáticamente la variable MOE para cada estimado (_E → _M)."""
        result = list(variables)
        for var in variables:
            if var.endswith("E") and "_" in var:
                moe_var = var[:-1] + "M"
                if moe_var not in result:
                    result.append(moe_var)
        return result

    async def _request_with_retry(self, url: str, params: dict[str, str]) -> httpx.Response:
        """Ejecuta request con retry y backoff exponencial."""
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.get(url, params=params)

                if response.status_code == 200:
                    # Census API redirige a HTML cuando el API key es inválido
                    content_type = response.headers.get("content-type", "")
                    if "text/html" in content_type:
                        raise CensusAPIError(
                            "API key inválida o expirada. El Census API funciona sin key (con rate limiting).",
                            status_code=200,
                            suggestion="Elimina CENSUS_API_KEY o obtén una nueva en https://api.census.gov/data/key_signup.html",
                        )
                    return response
                elif response.status_code == 204:
                    raise CensusAPIError(
                        "El Census API no tiene datos para esta combinación de parámetros.",
                        status_code=204,
                        suggestion="Verifica que el dataset, año y geografía sean válidos para PR.",
                    )
                elif response.status_code == 400:
                    text = response.text[:500]
                    raise CensusAPIError(
                        f"Parámetros inválidos en la consulta al Census API: {text}",
                        status_code=400,
                        suggestion="Verifica los códigos de variables y la geografía.",
                    )
                elif response.status_code in (429, 500, 502, 503):
                    last_error = CensusAPIError(
                        f"Census API respondió con HTTP {response.status_code}",
                        status_code=response.status_code,
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        wait = self.BACKOFF_BASE * (2 ** attempt)
                        logger.warning("Census API HTTP %d, reintentando en %.1fs...", response.status_code, wait)
                        import asyncio
                        await asyncio.sleep(wait)
                        continue
                else:
                    raise CensusAPIError(
                        f"Census API respondió con HTTP {response.status_code}: {response.text[:300]}",
                        status_code=response.status_code,
                    )
            except httpx.TimeoutException:
                last_error = CensusAPIError(
                    "Timeout al conectar con el Census API.",
                    suggestion="El servidor puede estar lento. Intenta de nuevo en unos minutos.",
                )
                if attempt < self.MAX_RETRIES - 1:
                    import asyncio
                    await asyncio.sleep(self.BACKOFF_BASE * (2 ** attempt))
                    continue
            except httpx.HTTPError as e:
                last_error = CensusAPIError(f"Error HTTP: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    import asyncio
                    await asyncio.sleep(self.BACKOFF_BASE * (2 ** attempt))
                    continue

        raise last_error  # type: ignore[misc]

    # Campos geográficos que deben permanecer como string (preservar ceros iniciales)
    _GEO_FIELDS = {"state", "county", "county subdivision", "tract", "block group", "block", "place", "us"}

    def _parse_response(self, data: list[list[str]]) -> list[dict[str, Any]]:
        """Convierte array-of-arrays del Census API a lista de dicts."""
        if not data or len(data) < 2:
            return []
        headers = data[0]
        rows = []
        for row in data[1:]:
            record: dict[str, Any] = {}
            for i, header in enumerate(headers):
                val = row[i] if i < len(row) else None
                if val is None:
                    record[header] = val
                elif header.lower() in self._GEO_FIELDS or header == "NAME":
                    # Preservar como string para campos geográficos y nombres
                    record[header] = val
                else:
                    try:
                        if "." in str(val):
                            record[header] = float(val)
                        else:
                            record[header] = int(val)
                    except (ValueError, TypeError):
                        record[header] = val
            rows.append(record)
        return rows

    async def query(
        self,
        year: int,
        dataset: str,
        variables: list[str],
        for_clause: str,
        in_clause: str | None = None,
        auto_moe: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Ejecuta un query al Census API y devuelve lista de dicts.

        Args:
            year: Año de los datos (ej: 2022)
            dataset: Path del dataset (ej: "acs/acs5")
            variables: Lista de códigos de variables (ej: ["B01003_001E"])
            for_clause: Geografía objetivo (ej: "county:*")
            in_clause: Geografía padre (ej: "state:72")
            auto_moe: Si True, añade automáticamente variables MOE
        """
        if auto_moe:
            variables = self._auto_add_moe(variables)

        # Siempre incluir NAME
        if "NAME" not in variables:
            variables = ["NAME"] + variables

        # Check cache
        cache_k = _cache_key(year, dataset, tuple(sorted(variables)), for_clause, in_clause)
        if cache_k in _cache:
            logger.debug("Cache hit: %s", cache_k[:80])
            return _cache[cache_k]

        url = self._build_url(year, dataset)
        params: dict[str, str] = {
            "get": ",".join(variables),
            "for": for_clause,
        }
        if in_clause:
            params["in"] = in_clause
        if self.api_key:
            params["key"] = self.api_key

        response = await self._request_with_retry(url, params)

        try:
            raw = response.json()
        except Exception:
            raise CensusAPIError(
                "La respuesta del Census API no es JSON válido.",
                suggestion="Esto puede indicar un problema temporal. Intenta de nuevo.",
            )

        rows = self._parse_response(raw)

        # Cache the result
        _cache[cache_k] = rows
        return rows

    async def get_available_datasets(self, year: int | None = None) -> list[dict[str, Any]]:
        """Lista datasets disponibles. Si se da año, filtra para ese año."""
        # Datasets conocidos que funcionan con PR
        known = [
            {
                "nombre": "American Community Survey 5-Year",
                "path": "acs/acs5",
                "años": list(range(2009, 2024)),
                "descripcion": "Datos detallados para todas las áreas geográficas de PR. Fuente principal.",
                "granularidad_pr": "Block Group",
            },
            {
                "nombre": "American Community Survey 1-Year",
                "path": "acs/acs1",
                "años": list(range(2005, 2024)),
                "descripcion": "Datos más recientes pero solo para municipios con 65,000+ habitantes.",
                "granularidad_pr": "Municipio (limitado)",
            },
            {
                "nombre": "Decennial Census (Redistricting)",
                "path": "dec/pl",
                "años": [2020, 2010],
                "descripcion": "Conteos oficiales de población para redistricting.",
                "granularidad_pr": "Block",
            },
            {
                "nombre": "Population Estimates",
                "path": "pep/population",
                "años": list(range(2015, 2024)),
                "descripcion": "Estimados intercensales anuales de población.",
                "granularidad_pr": "Municipio",
            },
        ]
        if year:
            known = [d for d in known if year in d["años"]]
        return known

    async def search_variables(self, dataset: str, year: int, keyword: str) -> list[dict[str, Any]]:
        """Busca variables por keyword en el API del Census Bureau."""
        url = f"{self.BASE_URL}/{year}/{dataset}/variables.json"
        client = await self._get_client()

        try:
            response = await client.get(url, timeout=30.0)
            if response.status_code != 200:
                return []
            data = response.json()
        except Exception:
            return []

        keyword_lower = keyword.lower()
        results = []
        variables = data.get("variables", {})
        for code, info in variables.items():
            if code.startswith("_"):
                continue
            label = info.get("label", "")
            concept = info.get("concept", "")
            if keyword_lower in label.lower() or keyword_lower in concept.lower():
                results.append({
                    "code": code,
                    "label": label,
                    "concept": concept,
                    "group": info.get("group", ""),
                })
                if len(results) >= 50:
                    break

        return results

    async def get_geographies(self, dataset: str, year: int) -> list[dict[str, Any]]:
        """Niveles geográficos disponibles para un dataset."""
        url = f"{self.BASE_URL}/{year}/{dataset}/geography.json"
        client = await self._get_client()

        try:
            response = await client.get(url, timeout=30.0)
            if response.status_code != 200:
                return []
            data = response.json()
        except Exception:
            return []

        geos = []
        for geo in data.get("fips", []):
            name = geo.get("name", "")
            geos.append({
                "nombre": name,
                "nombre_local": _translate_geo_name(name),
                "requires": geo.get("requires", []),
                "wildcard": geo.get("wildcard", []),
            })
        return geos


def _translate_geo_name(name: str) -> str:
    """Traduce nombres de geografía federal a terminología local de PR."""
    translations = {
        "state": "Estado/Territorio",
        "county": "Municipio",
        "county subdivision": "Barrio",
        "tract": "Tract censal",
        "block group": "Grupo de bloques",
        "block": "Bloque",
        "place": "Lugar",
        "zip code tabulation area": "Código postal (ZCTA)",
    }
    return translations.get(name.lower(), name)
