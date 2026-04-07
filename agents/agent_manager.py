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


async def stream_compliance_check(
    raw_geojson: dict[str, Any],
    metadata: FarmMetadata,
    thread_id: str | None = None,
):
    """
    Execute the full EcoOracle compliance pipeline as an async stream of events.
    Yields JSON-serializable dictionaries for each completed node.
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

    logger.info("[agent_manager] Starting streaming compliance run (thread_id=%s)", thread_id)
    
    async for event in _graph.astream(initial_state, config=config):
        # LangGraph dynamic event structure: {"node_name": {state_updates...}}
        node_name = list(event.keys())[0]
        state_updates = event[node_name]
        
        yield {"type": "node_start", "node": node_name}
        
        if node_name == "audit_finalizer":
            final_response = state_updates.get("final_response")
            if final_response and hasattr(final_response, "model_dump"):
                yield {"type": "final", "data": final_response.model_dump(mode="json")}
            else:
                yield {"type": "final", "data": final_response}


def run_compliance_check(
    raw_geojson: dict[str, Any],
    metadata: FarmMetadata,
    thread_id: str | None = None,
) -> AgentState:
    """
    Execute the full EcoOracle compliance pipeline (Legacy Blocking Version).
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
