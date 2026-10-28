"""LangGraph implementation of the live negotiation event contract.

The graph delegates buyer, routing, seller, and decision work to the existing
orchestrator. Each node returns a fresh room snapshot so checkpoints do not
share mutable conversation history with later rounds.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import random
from typing import Annotated, AsyncIterator, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from ..models.negotiation import NegotiationEvent, NegotiationRoomState
from ..services.deal_calculator import compute_deal_context
from ..services.wallet_loader import get_wallet_for_session
from .graph_builder import _get_latest_offers_per_seller, _match_inventory_item


def _append(current: list, incoming: list) -> list:
    return (current or []) + (incoming or [])


def _event(kind: str, data: dict) -> NegotiationEvent:
    return {"type": kind, "data": data, "timestamp": datetime.now()}


class NegotiationState(TypedDict, total=False):
    room: NegotiationRoomState
    buyer_result: dict | None
    responding_sellers: list
    seller_results: dict
    decision: dict | None
    stop_reason: str | None
    events: Annotated[list[NegotiationEvent], _append]


def _accept_events(room: NegotiationRoomState, decision: dict) -> list[NegotiationEvent]:
    """Use the same decision payload and card calculation as the asyncio path."""
    seller = next((s for s in room.sellers if s.seller_id == decision["seller_id"]), None)
    seller_name = seller.name if seller else "Unknown Seller"
    offer = decision["offer"]
    room.status = "completed"
    room.selected_seller_id = decision["seller_id"]
    room.final_offer = offer
    room.decision_reason = decision.get("reason", "Best offer selected")

    total_cost = offer["price"] * offer["quantity"]
    effective_total = total_cost
    recommended_card = None
    card_savings = 0.0
    if room.session_id:
        inventory = _match_inventory_item(seller, room.buyer_constraints) if seller else None
        wallet = get_wallet_for_session(room.session_id)
        context = compute_deal_context(
            price_per_unit=offer["price"],
            quantity=offer["quantity"],
            item_name=room.buyer_constraints.item_name,
            seller_name=seller_name,
            seller_cost_per_unit=inventory.cost_price if inventory else 0.0,
            wallet=wallet,
        )
        effective_total = context.buyer_effective_total
        recommended_card = context.recommended_card_name
        card_savings = context.buyer_savings

    return [
        _event("decision", {
            "decision": "accept",
            "chosen_seller_id": decision["seller_id"],
            "chosen_seller_name": seller_name,
            "final_price": offer["price"],
            "final_quantity": offer["quantity"],
            "total_cost": total_cost,
            "effective_total": effective_total,
            "recommended_card": recommended_card,
            "card_savings": card_savings,
            "reason": room.decision_reason,
        }),
        _event("negotiation_complete", {
            "selected_seller_id": decision["seller_id"],
            "selected_seller_name": seller_name,
            "final_offer": offer,
            "reason": decision.get("reason"),
            "rounds": room.current_round,
        }),
    ]


def _limit_events(room: NegotiationRoomState) -> list[NegotiationEvent]:
    """Apply the existing lowest-valid-offer fallback when the round cap is hit."""
    offers = sorted(
        (
            offer for offer in _get_latest_offers_per_seller(room)
            if room.buyer_constraints.min_price_per_unit
            <= offer["price"]
            <= room.buyer_constraints.max_price_per_unit
        ),
        key=lambda offer: offer["price"],
    )
    if not offers:
        room.status = "aborted"
        return [_event("negotiation_complete", {
            "selected_seller_id": None,
            "final_offer": None,
            "reason": "Max rounds reached",
            "rounds": room.current_round,
        })]

    best = offers[0]
    decision = {
        "seller_id": best["seller_id"],
        "offer": {"price": best["price"], "quantity": best["quantity"]},
        "reason": (
            f"Auto-selected best offer from {best['seller_name']}: "
            f"${best['price']:.2f}/unit after {room.current_round} rounds"
        ),
    }
    return _accept_events(room, decision)


def build_negotiation_graph(orchestrator, checkpointer=None):
    """Compile the graph; caller supplies a per-run checkpointer and thread ID."""

    def start_round(state: NegotiationState) -> dict:
        room = deepcopy(state["room"])
        room.current_round += 1
        return {
            "room": room,
            "buyer_result": None,
            "responding_sellers": [],
            "seller_results": {},
            "decision": None,
            "stop_reason": None,
            "events": [_event("round_start", {
                "round_number": room.current_round,
                "max_rounds": orchestrator.max_rounds,
            })],
        }

    async def buyer_turn(state: NegotiationState) -> dict:
        room = deepcopy(state["room"])
        result = await orchestrator._buyer_turn_node(room)
        if not result:
            return {"room": room, "buyer_result": None, "stop_reason": "buyer produced no message"}
        return {
            "room": room,
            "buyer_result": result,
            "events": [_event("buyer_message", {
                "sender_id": room.buyer_id,
                "sender_name": room.buyer_name,
                "sender_type": "buyer",
                "message": result["message"],
                "mentioned_sellers": result["mentioned_sellers"],
                "round": room.current_round,
            })],
        }

    def message_routing(state: NegotiationState) -> dict:
        room = state["room"]
        sellers = orchestrator._message_routing_node(
            state["buyer_result"]["mentioned_sellers"], room.sellers
        )
        return {
            "responding_sellers": sellers,
            "stop_reason": None if sellers else "no sellers to respond",
        }

    async def parallel_sellers(state: NegotiationState) -> dict:
        room = deepcopy(state["room"])
        results = await orchestrator._parallel_seller_responses_node(
            room, state["responding_sellers"]
        )
        events = []
        for seller_id, result in results.items():
            if result:
                seller = next((s for s in room.sellers if s.seller_id == seller_id), None)
                events.append(_event("seller_response", {
                    "seller_id": seller_id,
                    "sender_name": seller.name if seller else "Unknown Seller",
                    "sender_type": "seller",
                    "message": result["message"],
                    "offer": result.get("offer"),
                    "round": room.current_round,
                }))
        return {"room": room, "seller_results": results, "events": events}

    async def decision_check(state: NegotiationState) -> dict:
        room = deepcopy(state["room"])
        decision = await orchestrator._decision_check_node(room, state["seller_results"])
        if decision:
            events = _accept_events(room, decision)
        else:
            events = [_event("heartbeat", {
                "message": f"Round {room.current_round} complete",
                "round": room.current_round,
            })]
        return {"room": room, "decision": decision, "events": events}

    def finish_at_limit(state: NegotiationState) -> dict:
        room = deepcopy(state["room"])
        events = _limit_events(room)
        return {"room": room, "events": events}

    def begin(state: NegotiationState) -> str:
        return "finish_at_limit" if state["room"].current_round >= orchestrator.max_rounds else "start_round"

    def after_buyer(state: NegotiationState) -> str:
        return END if state.get("stop_reason") else "message_routing"

    def after_routing(state: NegotiationState) -> str:
        return END if state.get("stop_reason") else "parallel_sellers"

    def after_decision(state: NegotiationState) -> str:
        if state.get("decision"):
            return END
        if state["room"].current_round >= orchestrator.max_rounds:
            return "finish_at_limit"
        return "start_round"

    graph = StateGraph(NegotiationState)
    graph.add_node("begin", lambda state: {})
    graph.add_node("start_round", start_round)
    graph.add_node("buyer_turn", buyer_turn)
    graph.add_node("message_routing", message_routing)
    graph.add_node("parallel_sellers", parallel_sellers)
    graph.add_node("decision_check", decision_check)
    graph.add_node("finish_at_limit", finish_at_limit)
    graph.add_edge(START, "begin")
    graph.add_conditional_edges("begin", begin)
    graph.add_edge("start_round", "buyer_turn")
    graph.add_conditional_edges("buyer_turn", after_buyer)
    graph.add_conditional_edges("message_routing", after_routing)
    graph.add_edge("parallel_sellers", "decision_check")
    graph.add_conditional_edges("decision_check", after_decision)
    graph.add_edge("finish_at_limit", END)
    return graph.compile(checkpointer=checkpointer)


class LangGraphNegotiation:
    """Adapt LangGraph node updates to the existing SSE event interface."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.checkpointer = InMemorySaver()
        self.graph = build_negotiation_graph(orchestrator, self.checkpointer)

    async def run(self, room_state: NegotiationRoomState) -> AsyncIterator[NegotiationEvent]:
        if room_state.seed is not None:
            random.seed(room_state.seed)
        room_state.status = "active"
        yield _event("heartbeat", {
            "message": "Negotiation started", "round": room_state.current_round,
        })
        config = {
            "configurable": {"thread_id": room_state.room_id},
            "recursion_limit": max(25, self.orchestrator.max_rounds * 6 + 5),
        }
        try:
            async for update in self.graph.astream(
                {"room": deepcopy(room_state), "events": []},
                config=config,
                stream_mode="updates",
            ):
                for delta in update.values():
                    if not delta:
                        continue
                    if "room" in delta:
                        room_state.__dict__.update(deepcopy(delta["room"].__dict__))
                    for event in delta.get("events", []):
                        yield event
        except Exception as exc:
            room_state.status = "aborted"
            yield _event("error", {"error": str(exc), "round": room_state.current_round})
