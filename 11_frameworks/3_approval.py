"""Step 3: the approval gate - where the framework beats the hand-rolled version.

usage: uv run 11_frameworks/3_approval.py

4_write.py's gate was a blocking input() in the middle of the loop. That works
at a terminal and nowhere else: no human at 3am means the process hangs, and a
web request cannot sit open waiting for someone to click yes.

LangGraph models approval as an INTERRUPT instead. The run stops, its full state
is saved to a checkpointer, and the process is free to exit. Later - another
request, another machine, tomorrow - you resume from the saved state with the
decision. That is the shape a real approval queue needs, and it is genuinely
better than what we built by hand.
"""
import os, pathlib, sys, warnings
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "06_agents"))
load_dotenv()
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import tools as t


@tool
def list_orders(customer: str = None, status: str = None) -> list:
    """List orders (id, customer, item, status). Both filters are optional."""
    return t.list_orders(customer, status)


@tool
def cancel_order(order_id: str) -> dict:
    """Cancel ONE order and refund the customer. Permanent - no undo.
    Needs an exact order ID."""
    return t.cancel_order(order_id)          # preconditions still live IN the tool


model = ChatGoogleGenerativeAI(model=os.environ["LLM_MODEL"],
                               google_api_key=os.environ["LLM_API_KEY"])

agent = create_agent(
    model, [list_orders, cancel_order],
    system_prompt=("You manage an order database. cancel_order is permanent. "
                   "Never cancel unless the user named exactly which order."),
    # Only the write tool is gated. Reads run unattended - gating them would
    # make the agent useless (4_write.py's rule, expressed as config).
    middleware=[HumanInTheLoopMiddleware(interrupt_on={"cancel_order": True})],
    # No checkpointer, no interrupt: the state has nowhere to be saved.
    checkpointer=InMemorySaver())


def run(decision: str):
    """Same request twice: once approved, once rejected.

    Valid decisions: approve | reject | edit | respond. `edit` lets the human
    fix the arguments before it runs - something our input() gate could not do.
    """
    t.reset()                                        # demo is repeatable
    cfg = {"configurable": {"thread_id": f"demo-{decision}"}}
    print(f"\n{'=' * 68}\nDECISION: {decision}\n{'=' * 68}")

    out = agent.invoke({"messages": [{"role": "user",
                                      "content": "Cancel order SR-1005"}]}, cfg)

    # The run did not finish - it PAUSED and saved itself.
    if intr := out.get("__interrupt__"):
        req = intr[0].value
        print(f"  PAUSED. state saved; process could exit here.")
        print(f"  approval requested: {str(req)[:150]}")

        # Resume. In production this arrives from a different request entirely.
        out = agent.invoke(Command(resume={"decisions": [{"type": decision}]}), cfg)

    last = out["messages"][-1]
    text = last.content if isinstance(last.content, str) else \
        " ".join(b.get("text", "") for b in last.content if isinstance(b, dict))
    print(f"  FINAL -> {text.strip()[:200]}")
    print(f"  DB now: SR-1005 = {t.get_order('SR-1005')['status']}")


run("approve")
run("reject")
t.reset()
