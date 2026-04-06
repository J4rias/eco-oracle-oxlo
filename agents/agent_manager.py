"""LangGraph agent graph builder and runner."""
from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.nodes.audit_finalizer import audit_finalizer
from agents.nodes.input_validator import input_validator
from agents.nodes.legal_reasoner import legal_reasoner
from agents.nodes.satellite_fetcher import satellite_fetcher
from agents.nodes.vision_analyzer import vision_analyzer
from schemas.agent_state import AgentState
from schemas.inputs import FarmMetadata

logger = logging.getLogger(__name__)


def _build_graph() -> StateGraph:
    """Build and compile the EcoOracle LangGraph state graph."""
    graph = StateGraph(AgentState)

    # ── Register nodes ─────────────────────────────────────────────────────────
    graph.add_node("input_validator", input_validator)
    graph.add_node("satellite_fetcher", satellite_fetcher)
    graph.add_node("vision_analyzer", vision_analyzer)
    graph.add_node("legal_reasoner", legal_reasoner)
    graph.add_node("audit_finalizer", audit_finalizer)

    # ── Define edges (linear pipeline) ────────────────────────────────────────
    graph.add_edge(START, "input_validator")
    graph.add_edge("input_validator", "satellite_fetcher")
    graph.add_edge("satellite_fetcher", "vision_analyzer")
    graph.add_edge("vision_analyzer", "legal_reasoner")
    graph.add_edge("legal_reasoner", "audit_finalizer")
    graph.add_edge("audit_finalizer", END)

    return graph


# ── Singleton compiled graph with in-memory checkpointer ──────────────────────
_checkpointer = MemorySaver()
_graph = _build_graph().compile(checkpointer=_checkpointer)


def run_compliance_check(
    raw_geojson: dict[str, Any],
    metadata: FarmMetadata,
    thread_id: str | None = None,
) -> AgentState:
    """
    Execute the full EcoOracle compliance pipeline.

    Args:
        raw_geojson: Parsed GeoJSON dict (Feature or FeatureCollection).
        metadata: Validated FarmMetadata (crop type, harvest date, invoice).
        thread_id: Optional LangGraph thread ID for checkpoint resumption.

    Returns:
        Final AgentState containing `final_response` (ComplianceResponse).

    Raises:
        Any domain exception from the individual nodes.
    """
    import uuid

    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: AgentState = {
        "raw_geojson": raw_geojson,
        "metadata": metadata,
        "requires_human_review": False,
        "audit_stored": False,
        "rag_context": [],
    }

    logger.info("[agent_manager] Starting compliance run (thread_id=%s)", thread_id)
    final_state = _graph.invoke(initial_state, config=config)
    logger.info("[agent_manager] Run complete — verdict=%s", final_state.get("verdict"))

    return final_state
