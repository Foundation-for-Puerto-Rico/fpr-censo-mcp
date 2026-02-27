"""Perfiles temáticos de variables curadas del Census Bureau para FPR."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"

PERFIL_NOMBRES = {
    "demografico": "Demográfico",
    "economico": "Económico",
    "vivienda": "Vivienda",
    "educacion": "Educación",
    "salud_social": "Salud y Social",
    "infraestructura": "Infraestructura",
}

PERFILES_DISPONIBLES = list(PERFIL_NOMBRES.keys())


@dataclass
class VariableDefinition:
    """Definición de una variable curada del Census Bureau."""

    code: str  # "B19013_001E"
    moe_code: str  # "B19013_001M"
    nombre_es: str  # "Ingreso mediano del hogar"
    nombre_en: str  # "Median household income"
    universo: str  # "Hogares"
    formato: str  # "moneda" | "porcentaje" | "conteo" | "mediana"
    notas: str | None = None


class ProfileManager:
    """Maneja perfiles temáticos de variables curadas."""

    def __init__(self) -> None:
        self._profiles: dict[str, list[VariableDefinition]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        path = DATA_DIR / "variables_curadas.json"
        if not path.exists():
            logger.warning("No se encontró %s", path)
            self._loaded = True
            return

        raw = json.loads(path.read_text(encoding="utf-8"))
        for perfil, variables in raw.items():
            self._profiles[perfil] = [
                VariableDefinition(
                    code=v["code"],
                    moe_code=v["moe_code"],
                    nombre_es=v["nombre_es"],
                    nombre_en=v["nombre_en"],
                    universo=v["universo"],
                    formato=v["formato"],
                    notas=v.get("notas"),
                )
                for v in variables
            ]
        self._loaded = True

    def get_profile(self, perfil: str) -> list[VariableDefinition]:
        """Variables de un perfil temático."""
        self._ensure_loaded()
        return self._profiles.get(perfil, [])

    def get_all_profiles(self) -> dict[str, list[VariableDefinition]]:
        """Todos los perfiles."""
        self._ensure_loaded()
        return dict(self._profiles)

    def get_variables_for_profile(self, perfil: str) -> list[str]:
        """Códigos de variables (estimado) para un perfil."""
        return [v.code for v in self.get_profile(perfil)]

    def get_resumen_ejecutivo_variables(self) -> list[str]:
        """Variables clave para un resumen ejecutivo (1-2 de cada perfil)."""
        key_vars = [
            "B01003_001E",  # Población total
            "B01002_001E",  # Edad mediana
            "B19013_001E",  # Ingreso mediano
            "B17001_002E",  # Bajo pobreza
            "B25001_001E",  # Unidades de vivienda
            "B25002_003E",  # Vacantes
            "B15003_022E",  # Bachelor's
            "B28002_004E",  # Internet
        ]
        return key_vars

    def find_variable(self, code: str) -> VariableDefinition | None:
        """Busca una variable por código en todos los perfiles."""
        self._ensure_loaded()
        for variables in self._profiles.values():
            for v in variables:
                if v.code == code or v.moe_code == code:
                    return v
        return None

    def search_variables(self, keyword: str) -> list[VariableDefinition]:
        """Busca variables por keyword en español o inglés."""
        self._ensure_loaded()
        keyword_lower = keyword.lower()
        results = []
        for variables in self._profiles.values():
            for v in variables:
                if (
                    keyword_lower in v.nombre_es.lower()
                    or keyword_lower in v.nombre_en.lower()
                    or keyword_lower in v.code.lower()
                    or (v.notas and keyword_lower in v.notas.lower())
                ):
                    results.append(v)
        return results

    def list_profiles(self) -> list[dict[str, Any]]:
        """Lista perfiles disponibles con conteo de variables."""
        self._ensure_loaded()
        return [
            {
                "id": pid,
                "nombre": PERFIL_NOMBRES.get(pid, pid),
                "variables": len(self._profiles.get(pid, [])),
            }
            for pid in PERFILES_DISPONIBLES
            if pid in self._profiles
        ]
