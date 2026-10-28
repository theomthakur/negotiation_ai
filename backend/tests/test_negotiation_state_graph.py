"""Parity checks for the live asyncio and LangGraph negotiation paths."""

from datetime import datetime

import pytest

from app.agents.graph_builder import NegotiationGraph
from app.agents.negotiation_state_graph import LangGraphNegotiation
from app.models.agent import BuyerConstraints, InventoryItem, Seller, SellerProfile
from app.models.negotiation import NegotiationRoomState
from app.services.visibility_filter import filter_conversation


def make_room() -> NegotiationRoomState:
    sellers = [
        Seller(
            seller_id=seller_id,
            name=name,
            profile=SellerProfile(priority="maximize_profit"),
            inventory=[InventoryItem(
                item_id=f"item-{seller_id}", item_name="Laptop", cost_price=30,
                selling_price=75, least_price=45, quantity_available=2,
            )],
        )
        for seller_id, name in (("s1", "Alpha"), ("s2", "Beta"))
    ]
    return NegotiationRoomState(
        room_id="parity-room", buyer_id="buyer", buyer_name="Buyer",
        buyer_constraints=BuyerConstraints(
            item_id="laptop", item_name="Laptop", quantity_needed=1,
            min_price_per_unit=20, max_price_per_unit=90,
        ),
        sellers=sellers,
    )


class StubOrchestrator(NegotiationGraph):
    """Use the real orchestration code with deterministic agent outcomes."""

    def __init__(self, accept_on: int | None, max_rounds: int = 3):
        super().__init__(provider=None)
        self.accept_on = accept_on
        self.max_rounds = max_rounds
        self.calls = []
        self.seller_views = []

    async def _buyer_turn_node(self, room):
        self.calls.append(("buyer", room.current_round))
        result = {"message": f"Offer in round {room.current_round}", "mentioned_sellers": []}
        room.conversation_history.append({
            "sender_id": room.buyer_id, "sender_type": "buyer",
            "sender_name": room.buyer_name, "content": result["message"],
            "visibility": [room.buyer_id] + [seller.seller_id for seller in room.sellers],
            "timestamp": datetime.now(),
        })
        return result

    def _message_routing_node(self, mentioned_sellers, all_sellers):
        self.calls.append(("route", len(all_sellers)))
        return all_sellers

    async def _parallel_seller_responses_node(self, room, sellers):
        self.calls.append(("sellers", room.current_round))
        results = {}
        for seller in sellers:
            view = filter_conversation(room.conversation_history, seller.seller_id, "seller")
            self.seller_views.append([m["sender_type"] for m in view])
            offer = {"price": 60 if seller.seller_id == "s1" else 55, "quantity": 1}
            results[seller.seller_id] = {"message": "My offer", "offer": offer}
            room.conversation_history.append({
                "sender_id": seller.seller_id, "sender_type": "seller",
                "sender_name": seller.name, "content": "My offer", "offer": offer,
                "visibility": [room.buyer_id, seller.seller_id], "timestamp": datetime.now(),
            })
        return results

    async def _decision_check_node(self, room, seller_results):
        self.calls.append(("decide", room.current_round))
        if self.accept_on == room.current_round:
            return {
                "seller_id": "s2", "offer": seller_results["s2"]["offer"],
                "reason": "Buyer accepted Beta",
            }
        return None


async def run_case(accept_on: int | None, max_rounds: int = 3, max_price: float = 90):
    outcomes = []
    for mode in ("asyncio", "langgraph"):
        room = make_room()
        room.buyer_constraints.max_price_per_unit = max_price
        orchestrator = StubOrchestrator(accept_on, max_rounds)
        runner = orchestrator if mode == "asyncio" else LangGraphNegotiation(orchestrator)
        events = [event async for event in runner.run(room)]
        outcomes.append((room, orchestrator, events, runner))
    return outcomes


@pytest.mark.asyncio
@pytest.mark.parametrize("accept_on,max_rounds", [(2, 3), (None, 2)])
async def test_live_event_contract_matches_asyncio(accept_on, max_rounds):
    (old_room, old, old_events, _), (new_room, new, new_events, runner) = await run_case(
        accept_on, max_rounds
    )
    assert [(e["type"], e["data"]) for e in new_events] == [
        (e["type"], e["data"]) for e in old_events
    ]
    assert new.calls == old.calls
    assert new_room.status == old_room.status == "completed"
    assert new_room.selected_seller_id == old_room.selected_seller_id == "s2"
    assert new_room.current_round == old_room.current_round
    assert all(all(role == "buyer" for role in view) for view in new.seller_views)
    state = await runner.graph.aget_state({"configurable": {"thread_id": new_room.room_id}})
    assert state.values["room"].status == "completed"


@pytest.mark.asyncio
async def test_round_limit_selects_best_valid_offer():
    old, new = await run_case(accept_on=None, max_rounds=1)
    for room, _, events, _ in (old, new):
        assert room.status == "completed"
        assert room.final_offer == {"price": 55, "quantity": 1}
        assert events[-1]["type"] == "negotiation_complete"


@pytest.mark.asyncio
async def test_round_limit_without_valid_offer_matches_asyncio():
    old, new = await run_case(accept_on=None, max_rounds=1, max_price=40)
    assert [(e["type"], e["data"]) for e in new[2]] == [
        (e["type"], e["data"]) for e in old[2]
    ]
    assert new[0].status == old[0].status == "aborted"
    assert new[0].selected_seller_id is None


def test_orchestrator_setting_selects_the_runner():
    from app.agents.graph_builder import NegotiationGraph
    from app.api.v1.endpoints.streaming import make_negotiation_runner
    from app.core.config import Settings

    assert Settings.model_fields["ORCHESTRATOR"].default == "langgraph"
    provider = object()
    assert isinstance(make_negotiation_runner(provider, "langgraph"), LangGraphNegotiation)
    original = make_negotiation_runner(provider, "asyncio")
    assert isinstance(original, NegotiationGraph) and not isinstance(original, LangGraphNegotiation)
