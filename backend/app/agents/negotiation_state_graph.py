"""The negotiation as a real LangGraph StateGraph.

`graph_builder.NegotiationGraph` describes itself as "LangGraph-style" and is a
hand-rolled `while` loop. The node boundaries were always right — buyer turn,
routing, parallel sellers, decision check — so this file keeps that logic exactly
and replaces the loop with an actual compiled graph.

What that buys, beyond the name being true:

  * **The topology is declared, not implied.** The round loop is a conditional
    edge from `decision_check`, so the termination rules are one function you can
    read rather than four `break` statements scattered through a loop body.
  * **Every node returns a state delta.** Nodes stop mutating shared state in
    place, which is what made the original hard to reason about when a seller
    response failed mid-round.
  * **Checkpointing comes free.** A compiled graph with a checkpointer can resume
    a negotiation, which the `while` loop could never do.

The node bodies are delegated to the existing `NegotiationGraph` methods rather
than reimplemented, so behaviour is unchanged and there is one place to fix bugs.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)


def _last(_current: Any, incoming: Any) -> Any:
    """Reducer: last write wins. Nodes own the keys they return."""
    return incoming


def _extend(current: list, incoming: list) -> list:
    """Reducer: append, so parallel seller nodes can each contribute events."""
    return (current or []) + (incoming or [])


class NegotiationState(TypedDict, total=False):
    """What flows between nodes.

    `room` is the existing NegotiationRoomState, carried through untouched so the
    delegated node methods keep working. Everything else is graph bookkeeping.
    """

    room: Any
    round_number: Annotated[int, _last]
    buyer_result: Annotated[Optional[dict], _last]
    responding_sellers: Annotated[list, _last]
    seller_results: Annotated[list, _last]
    decision: Annotated[Optional[dict], _last]
    events: Annotated[list, _extend]
    stop_reason: Annotated[Optional[str], _last]


def build_negotiation_graph(orchestrator, checkpointer=None):
    """Compile the negotiation graph.

    Args:
        orchestrator: a `NegotiationGraph`, whose node methods are reused.
        checkpointer: optional LangGraph checkpointer for resumable runs.

    Returns:
        A compiled graph. Call `.ainvoke({"room": room_state})`.
    """

    async def buyer_turn(state: NegotiationState) -> dict:
        room = state["room"]
        room.current_round += 1
        result = await orchestrator._buyer_turn_node(room)
        return {
            "buyer_result": result,
            "round_number": room.current_round,
            "events": [{"type": "round_start", "round": room.current_round}],
            "stop_reason": None if result else "buyer produced no message",
        }

    def message_routing(state: NegotiationState) -> dict:
        room = state["room"]
        sellers = orchestrator._message_routing_node(room, state.get("buyer_result"))
        return {"responding_sellers": sellers or []}

    async def parallel_sellers(state: NegotiationState) -> dict:
        room = state["room"]
        results = await orchestrator._parallel_seller_responses_node(
            room, state.get("responding_sellers") or []
        )
        return {
            "seller_results": results or [],
            "events": [{"type": "seller_responses", "count": len(results or [])}],
        }

    async def decision_check(state: NegotiationState) -> dict:
        room = state["room"]
        decision = await orchestrator._decision_check_node(room, state.get("seller_results") or [])
        return {"decision": decision}

    def should_continue(state: NegotiationState) -> Literal["buyer_turn", "__end__"]:
        """The whole termination policy, in one readable place.

        In the original this was three `break` statements in different branches
        of a while loop, which is why an early seller failure could leave the
        room in `active` forever.
        """
        room = state["room"]
        if state.get("stop_reason"):
            return END
        decision = state.get("decision") or {}
        if decision.get("accepted") or decision.get("decided"):
            return END
        if room.current_round >= orchestrator.max_rounds:
            return END
        return "buyer_turn"

    graph = StateGraph(NegotiationState)
    graph.add_node("buyer_turn", buyer_turn)
    graph.add_node("message_routing", message_routing)
    graph.add_node("parallel_sellers", parallel_sellers)
    graph.add_node("decision_check", decision_check)

    graph.add_edge(START, "buyer_turn")
    graph.add_edge("buyer_turn", "message_routing")
    graph.add_edge("message_routing", "parallel_sellers")
    graph.add_edge("parallel_sellers", "decision_check")
    graph.add_conditional_edges(
        "decision_check", should_continue, {"buyer_turn": "buyer_turn", END: END}
    )

    return graph.compile(checkpointer=checkpointer) if checkpointer else graph.compile()
