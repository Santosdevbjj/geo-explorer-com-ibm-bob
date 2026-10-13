"""Servidor MCP oficial do Sentinel usando o SDK Python.

Inicie na raiz do repositório após instalar `pip install -e ".[mcp]"`.
Transporte stdio; logs devem permanecer em stderr (gerenciados pelo SDK).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

TOOLS_PATH = Path(__file__).with_name("tools.py")
_spec = importlib.util.spec_from_file_location("sentinel_mcp_local_tools", TOOLS_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("Não foi possível carregar as ferramentas MCP locais.")
_tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tools)

server = FastMCP(
    "sentinel",
    instructions=(
        "Ferramentas de análise defensiva somente leitura. Não trate scores como "
        "probabilidades calibradas nem drift como prova isolada de perda de acurácia."
    ),
)


@server.tool()
def get_model_info() -> dict[str, Any]:
    """Retorna versão, disponibilidade e modo de inferência do modelo."""
    return _tools.get_model_info()


@server.tool()
def analyze_event(event: dict[str, Any]) -> dict[str, Any]:
    """Valida e analisa um evento sintético/autorizado; não persiste nem retorna o payload."""
    return _tools.analyze_event(event)


@server.tool()
def get_metrics_summary() -> dict[str, Any]:
    """Retorna métricas resumidas do relatório de avaliação disponível."""
    return _tools.get_metrics_summary()


@server.tool()
def get_drift_summary() -> dict[str, Any]:
    """Retorna resumo de drift disponível e limitações de interpretação."""
    return _tools.get_drift_summary()


if __name__ == "__main__":
    server.run(transport="stdio")
