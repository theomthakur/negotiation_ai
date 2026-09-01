"""Prove the compiled graph runs a full negotiation with a stub orchestrator.

No LLM, no network. The point is the graph topology: does it loop, does it
terminate on acceptance, does it terminate on max rounds.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.agents.negotiation_state_graph import build_negotiation_graph

class Room:
    def __init__(self): self.current_round = 0; self.status = "pending"

class StubOrchestrator:
    """Accepts on round 3."""
    max_rounds = 10
    def __init__(self, accept_on=3): self.accept_on = accept_on; self.calls = []
    async def _buyer_turn_node(self, room):
        self.calls.append(("buyer", room.current_round)); return {"msg": f"offer r{room.current_round}"}
    def _message_routing_node(self, room, buyer_result):
        self.calls.append(("route", room.current_round)); return ["s1", "s2", "s3"]
    async def _parallel_seller_responses_node(self, room, sellers):
        self.calls.append(("sellers", room.current_round)); return [{"seller": s, "price": 100 - room.current_round} for s in sellers]
    async def _decision_check_node(self, room, results):
        self.calls.append(("decide", room.current_round))
        return {"accepted": room.current_round >= self.accept_on, "price": 97}

async def main():
    # 1. terminates on acceptance
    orch = StubOrchestrator(accept_on=3)
    g = build_negotiation_graph(orch)
    out = await g.ainvoke({"room": Room()}, {"recursion_limit": 100})
    rounds = out["room"].current_round
    print(f"  accept-on-3     -> rounds={rounds}  decision={out['decision']}  events={len(out['events'])}")
    assert rounds == 3, f"expected 3 rounds, got {rounds}"
    assert out["decision"]["accepted"] is True

    # 2. terminates on max_rounds when nobody ever accepts
    orch2 = StubOrchestrator(accept_on=999)
    orch2.max_rounds = 4
    g2 = build_negotiation_graph(orch2)
    out2 = await g2.ainvoke({"room": Room()}, {"recursion_limit": 100})
    print(f"  never-accepts   -> rounds={out2['room'].current_round} (max_rounds=4)")
    assert out2["room"].current_round == 4

    # 3. node order is the declared topology, every round
    order = [c[0] for c in orch.calls[:8]]
    print(f"  node order      -> {order}")
    assert order == ["buyer","route","sellers","decide"]*2

    # 4. it is genuinely a compiled LangGraph
    print(f"  graph type      -> {type(g).__module__}.{type(g).__name__}")
    print(f"  nodes           -> {sorted(n for n in g.get_graph().nodes if not n.startswith('__'))}")
    print("\n  ALL ASSERTIONS PASSED")

def test_negotiation_graph():
    """pytest entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
