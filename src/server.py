"""FPR Census MCP Server — Entry point.

Servidor MCP que conecta a Claude con datos del U.S. Census Bureau,
optimizado para Puerto Rico.

Uso:
    python -m src.server                                          # stdio (dev)
    python -m src.server --transport streamable-http --port 8001  # HTTP (prod)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from src.census_client import CensusClient
from src.geography import GeographyResolver
from src.profiles import ProfileManager
from src.tools.analysis import register_analysis_tools
from src.tools.discovery import register_discovery_tools
from src.tools.query import register_query_tools

# Logging a stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("fpr-censo")

# ---------------------------------------------------------------------------
# Inicializar componentes
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "fpr-censo",
    instructions=(
        "Servidor MCP del Census Bureau para Puerto Rico. "
        "Provee datos demográficos, económicos, de vivienda, educación, "
        "salud, e infraestructura para los 78 municipios y sus barrios. "
        "Todos los estimados del ACS incluyen Margin of Error (MOE) y "
        "evaluación de confiabilidad (CV). Los tools aceptan nombres de "
        "municipios y barrios en español.\n\n"
        "IMPORTANTE: Al inicio de cada sesión, llama censo_estado para "
        "verificar la configuración. Si el API key no está configurado, "
        "muestra las instrucciones al usuario y guíalo para obtener una "
        "key gratuita en https://api.census.gov/data/key_signup.html. "
        "El servidor funciona sin key pero con rate limiting."
    ),
)

client = CensusClient()
geo = GeographyResolver()
profiles = ProfileManager()

# ---------------------------------------------------------------------------
# Registrar tools
# ---------------------------------------------------------------------------

register_discovery_tools(mcp, client, geo, profiles)
register_query_tools(mcp, client, geo, profiles)
register_analysis_tools(mcp, client, geo, profiles)

# ---------------------------------------------------------------------------
# Health endpoint (para monitoring)
# ---------------------------------------------------------------------------

from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> Response:
    """Health check."""
    return JSONResponse({
        "status": "ok",
        "service": "fpr-censo-mcp",
        "version": "0.1.0",
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="FPR Census MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Tipo de transporte (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CENSO_PORT", "8001")),
        help="Puerto para HTTP transport (default: 8001)",
    )
    args = parser.parse_args()

    if args.transport in ("streamable-http", "sse"):
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = args.port
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        )
        logger.info("Iniciando fpr-censo-mcp en %s://0.0.0.0:%d", args.transport, args.port)

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
