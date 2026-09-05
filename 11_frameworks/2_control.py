"""Step 2: putting 06_agents' guards back into the framework.

usage: uv run 11_frameworks/2_control.py

1_prebuilt.py crashed on the courier failure exactly like 1_fragile.py did.
This file asks the real question about any framework: when the defaults are not
yours, is reinstating your own behaviour CLEAN or a fight?

LangChain's answer is middleware - objects that wrap the loop's steps. Four of
the five guards you wrote by hand are one line each. The fifth is not there,
and you write it yourself.
"""
import os, pathlib, sys, warnings
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "06_agents"))
load_dotenv()
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware, ToolCallLimitMiddleware, ToolErrorMiddleware,
    wrap_tool_call)
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

import tools as t


@tool
def list_orders(customer: str = None, status: str = None) -> list:
    """List orders (id, customer, item, status). Both filters are optional -
    omit both to list every order. Omit customer if the user didn't name one."""
    return t.list_orders(customer, status)


@tool
def get_order(order_id: str) -> dict:
    """Full details of ONE order including amount. Needs an order ID."""
    return t.get_order(order_id)


@tool
def track_shipment(order_id: str) -> dict:
    """Live courier location for an in-transit order. Needs an order ID."""
    return t.track_shipment(order_id)


# --- guard 5: the one the framework does NOT have --------------------------
# There is no repetition middleware. wrap_tool_call gives you the interception
# point; the logic - and crucially the sort_keys canonicalisation that stops the
# model escaping by reordering arguments - is still yours to write.
REPEAT_LIMIT = 2
_seen: dict[str, int] = {}


@wrap_tool_call
def repetition_guard(request, handler):
    import json
    call = request.tool_call
    try:
        args = json.dumps(call["args"], sort_keys=True)   # 3_loops.py's lesson
    except TypeError:
        args = str(call["args"])
    sig = f"{call['name']}({args})"
    _seen[sig] = _seen.get(sig, 0) + 1

    if _seen[sig] > REPEAT_LIMIT:
        print(f"  [LOOP  ] blocked {sig[:60]}")
        return ToolMessage(                       # refuse; do NOT run the tool
            content=(f"loop guard: you already called this {_seen[sig]-1} times "
                     f"with the same result. Do not call it again. Answer with "
                     f"what you have."),
            tool_call_id=call["id"])
    return handler(request)


def on_tool_error(exc: Exception, request) -> str:
    """2_robust.py's dispatch(), as a callback. The error becomes a tool message
    the model can read and recover from, instead of killing the process."""
    print(f"  [!!    ] {request.tool_call['name']} raised {type(exc).__name__}")
    return f"{request.tool_call['name']} failed: {type(exc).__name__}: {exc}"


model = ChatGoogleGenerativeAI(model=os.environ["LLM_MODEL"],
                               google_api_key=os.environ["LLM_API_KEY"])

SYSTEM = ("You answer questions about an order database using the tools provided. "
          "Never invent argument values. If a tool errors, retry at most once, "
          "then answer with what you know and say what was unavailable.")

# 3_loops.py's runaway prompt, so the repetition guard has something to catch.
STUBBORN = ("You answer questions about an order database using the tools "
            "provided. Live tracking is critical; the user cannot be helped "
            "without it. If a tool fails, try again. Never give up, and never "
            "answer without live tracking data.")

agent = create_agent(
    model, [list_orders, get_order, track_shipment],
    system_prompt=STUBBORN if "--stubborn" in sys.argv else SYSTEM,
    middleware=[
        repetition_guard,                                    # yours, hand-written
        ToolErrorMiddleware(on_error=on_tool_error),         # = dispatch()
        ToolCallLimitMiddleware(run_limit=12),               # = MAX_CALLS
        ModelCallLimitMiddleware(run_limit=6, exit_behavior="end"),  # = MAX_ROUNDS
    ])

positional = [a for a in sys.argv[1:] if not a.startswith("--")]
QUESTION = positional[0] if positional else \
    "Where is Neha Gupta's coffee maker right now?"
print(f"Q: {QUESTION}\n")

result = agent.invoke({"messages": [{"role": "user", "content": QUESTION}]})

for m in result["messages"]:
    if calls := getattr(m, "tool_calls", None):
        for c in calls:
            print(f"  [call  ] {c['name']}({c['args']})")

last = result["messages"][-1]
text = last.content if isinstance(last.content, str) else \
    " ".join(b.get("text", "") for b in last.content if isinstance(b, dict))
print(f"\nFINAL -> {text.strip()[:300]}")
