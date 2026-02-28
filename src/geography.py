"""Resolución de geografías de Puerto Rico — municipios, barrios, FIPS codes."""

from __future__ import annotations

import json
import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

# Traducción de terminología federal ↔ local
TERMINOLOGY = {
    "county": "municipio",
    "county subdivision": "barrio",
    "tract": "tract censal",
    "block group": "grupo de bloques",
    "block": "bloque",
    "state": "estado/territorio",
}

# Niveles geográficos válidos
GEOGRAPHIC_LEVELS = ["state", "county", "county subdivision", "tract", "block group"]


@dataclass
class GeographyResult:
    """Resultado de resolver una geografía."""

    nombre: str
    fips: str
    nivel: str  # "county", "county subdivision", etc.
    for_clause: str  # "county:145"
    in_clause: str  # "state:72" o "state:72 county:145"
    nombre_completo: str | None = None  # "Vega Baja Municipio, Puerto Rico"


@dataclass
class Municipio:
    nombre: str
    fips: str
    region: str


@dataclass
class Barrio:
    nombre: str
    fips: str
    municipio_fips: str


def _normalize(text: str) -> str:
    """Normaliza texto: minúsculas, sin acentos, sin espacios extra."""
    text = text.lower().strip()
    # Remover acentos
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


class GeographyResolver:
    """Resuelve nombres de geografías de PR a FIPS codes y cláusulas Census API."""

    def __init__(self) -> None:
        self._municipios: list[dict[str, str]] = []
        self._barrios: dict[str, list[dict[str, str]]] = {}
        self._muni_lookup: dict[str, dict[str, str]] = {}  # normalized name → entry
        self._barrio_lookup: dict[str, list[tuple[dict[str, str], str]]] = {}  # normalized → [(entry, muni_fips)]
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        # Cargar municipios
        muni_path = DATA_DIR / "municipios_pr.json"
        if muni_path.exists():
            self._municipios = json.loads(muni_path.read_text(encoding="utf-8"))
            for m in self._municipios:
                key = _normalize(m["nombre"])
                self._muni_lookup[key] = m
                # También indexar sin "municipio" por si acaso
                if key.endswith(" municipio"):
                    self._muni_lookup[key.replace(" municipio", "")] = m
        else:
            logger.warning("No se encontró %s", muni_path)

        # Cargar barrios
        barrio_path = DATA_DIR / "barrios_pr.json"
        if barrio_path.exists():
            self._barrios = json.loads(barrio_path.read_text(encoding="utf-8"))
            for muni_fips, barrios in self._barrios.items():
                for b in barrios:
                    key = _normalize(b["nombre"])
                    if key not in self._barrio_lookup:
                        self._barrio_lookup[key] = []
                    self._barrio_lookup[key].append((b, muni_fips))
        else:
            logger.warning("No se encontró %s", barrio_path)

        self._loaded = True

    def resolve(self, name: str, level: str | None = None) -> GeographyResult | None:
        """
        Resuelve un nombre de geografía a FIPS y cláusulas for/in.

        Soporta formatos:
          - "Vega Baja" → municipio
          - "Almirante Norte" → barrio (si no existe municipio con ese nombre)
          - "Almirante Norte, Vega Baja" → barrio dentro del municipio

        Args:
            name: Nombre como "Vega Baja", "Almirante Sur, Vega Baja", o FIPS directo
            level: Forzar nivel ("county", "county subdivision"). Si None, auto-detecta.

        Returns:
            GeographyResult o None si no se encuentra
        """
        self._ensure_loaded()
        normalized = _normalize(name)

        # Caso especial: "Puerto Rico" o "PR" → state level
        if normalized in ("puerto rico", "pr"):
            return GeographyResult(
                nombre="Puerto Rico",
                fips="72",
                nivel="state",
                for_clause="state:72",
                in_clause="",
            )

        # Detectar formato "barrio, municipio" (coma como separador)
        has_comma = "," in normalized
        if has_comma:
            # Intentar barrio primero cuando hay coma — indica "barrio, municipio"
            if level is None or level in ("county subdivision", "barrio"):
                barrio_result = self._find_barrio(normalized)
                if barrio_result:
                    barrio, muni_fips = barrio_result
                    muni = self.get_municipio_by_fips(muni_fips)
                    nombre_display = f"{barrio['nombre']}, {muni.nombre}" if muni else barrio["nombre"]
                    return GeographyResult(
                        nombre=nombre_display,
                        fips=barrio["fips"],
                        nivel="county subdivision",
                        for_clause=f"county subdivision:{barrio['fips']}",
                        in_clause=f"state:72 county:{muni_fips}",
                    )

        # Intentar como municipio (o si level fuerza county)
        if level is None or level in ("county", "municipio"):
            muni = self._find_municipio(normalized)
            if muni:
                return GeographyResult(
                    nombre=muni["nombre"],
                    fips=muni["fips"],
                    nivel="county",
                    for_clause=f"county:{muni['fips']}",
                    in_clause="state:72",
                )

        # Intentar como barrio (sin coma — nombre suelto)
        if level is None or level in ("county subdivision", "barrio"):
            barrio_result = self._find_barrio(normalized)
            if barrio_result:
                barrio, muni_fips = barrio_result
                return GeographyResult(
                    nombre=barrio["nombre"],
                    fips=barrio["fips"],
                    nivel="county subdivision",
                    for_clause=f"county subdivision:{barrio['fips']}",
                    in_clause=f"state:72 county:{muni_fips}",
                )

        return None

    def _find_municipio(self, normalized: str) -> dict[str, str] | None:
        """Busca municipio por nombre normalizado, con fuzzy matching."""
        # Exact match
        if normalized in self._muni_lookup:
            return self._muni_lookup[normalized]

        # Partial / fuzzy match
        for key, muni in self._muni_lookup.items():
            if normalized in key or key in normalized:
                return muni

        return None

    def _find_barrio(self, normalized: str) -> tuple[dict[str, str], str] | None:
        """
        Busca barrio por nombre normalizado.

        Soporta formatos:
          - "almirante norte" → primer barrio con ese nombre
          - "almirante norte, vega baja" → barrio dentro del municipio especificado
        """
        # Parsear formato "barrio, municipio"
        barrio_name = normalized
        muni_filter_fips: str | None = None

        if "," in normalized:
            parts = [p.strip() for p in normalized.split(",", 1)]
            barrio_name = parts[0]
            muni_name = parts[1]
            muni = self._find_municipio(_normalize(muni_name))
            if muni:
                muni_filter_fips = muni["fips"]

        # Exact match (filtrado por municipio si se especificó)
        if barrio_name in self._barrio_lookup:
            matches = self._barrio_lookup[barrio_name]
            if muni_filter_fips:
                for barrio, mfips in matches:
                    if mfips == muni_filter_fips:
                        return barrio, mfips
            return matches[0]

        # Partial match
        for key, matches in self._barrio_lookup.items():
            if barrio_name in key or key in barrio_name:
                if muni_filter_fips:
                    for barrio, mfips in matches:
                        if mfips == muni_filter_fips:
                            return barrio, mfips
                return matches[0]

        return None

    def resolve_for_all_municipios(self) -> tuple[str, str]:
        """Devuelve for/in clauses para obtener todos los municipios de PR."""
        return "county:*", "state:72"

    def resolve_for_barrios_in(self, municipio: str) -> tuple[str, str] | None:
        """Devuelve for/in clauses para obtener barrios de un municipio."""
        self._ensure_loaded()
        muni = self._find_municipio(_normalize(municipio))
        if not muni:
            return None
        return "county subdivision:*", f"state:72 county:{muni['fips']}"

    def list_municipios(self) -> list[Municipio]:
        """Los 78 municipios de PR con FIPS."""
        self._ensure_loaded()
        return [
            Municipio(nombre=m["nombre"], fips=m["fips"], region=m.get("region", ""))
            for m in self._municipios
        ]

    def list_barrios(self, municipio: str) -> list[Barrio]:
        """Barrios dentro de un municipio dado."""
        self._ensure_loaded()
        muni = self._find_municipio(_normalize(municipio))
        if not muni:
            return []
        barrios = self._barrios.get(muni["fips"], [])
        return [
            Barrio(nombre=b["nombre"], fips=b["fips"], municipio_fips=muni["fips"])
            for b in barrios
        ]

    def get_municipio_by_fips(self, fips: str) -> Municipio | None:
        """Busca municipio por FIPS code."""
        self._ensure_loaded()
        for m in self._municipios:
            if m["fips"] == fips:
                return Municipio(nombre=m["nombre"], fips=m["fips"], region=m.get("region", ""))
        return None
