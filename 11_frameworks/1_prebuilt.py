"""Step 1: 06_agents, rebuilt with a framework.

usage: uv run 11_frameworks/1_prebuilt.py ["your question"]

Same model, same database, same three tools. The only change is who owns the
loop. Read this next to 06_agents/agent.py and count the lines you did not write.

WHY ChatGoogleGenerativeAI AND NOT ChatOpenAI HERE
--------------------------------------------------
The rest of this repo talks to Gemini through its OpenAI-compatible endpoint,
and llm.py works fine that way. Through LangChain it does NOT - the second round
dies with:

    400 Function call is missing a thought_signature in functionCall parts

Exactly the failure 05_tools warned about: "append the assistant message
verbatim; rebuilding it field-by-field drops provider metadata". LangChain
normalises every provider's reply into its own AIMessage, and the normalisation
drops Gemini's opaque thought_signature. Verified: additional_kwargs holds only
{'refusal'}, and the raw tool_calls are None.

The provider-NATIVE integration keeps it (you can see `extras.signature` on the
returned content blocks). So the fix is to stop stacking two lossy abstractions -
an OpenAI-shaped shim under a framework-shaped one - and use the real driver.
"""
import os, pathlib, sys, warnings
from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "06_agents"))
load_dotenv()
warnings.filterwarnings("ignore", message=".*fixed sampling defaults.*")

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

import tools as t                      # 06_agents/tools.py - the SAME functions

# A tool is a decorated function: the docstring becomes the description sent to
# the model, the type hints become the JSON Schema. The hand-written TOOLS list
# from 05_tools disappears - same information, far less typing.
#
# What you lose: that schema is now GENERATED. The `enum` on status and the
# per-argument description that fixed the invented `customer: "Alice"` bug in
# 05_tools have nowhere obvious to go. See 2_control.py.


@tool
def list_orders(customer: str = None, status: str = None) -> list:
    """List orders (id, customer, item, status). Both filters are optional -
    omit both to list every order. Omit customer if the user didn't name one.
    Valid status values: processing, in_transit, delivered, cancelled."""
    return t.list_orders(customer, status)


@tool
def get_order(order_id: str) -> dict:
    """Full details of ONE order including amount. Needs an order ID."""
    return t.get_order(order_id)


@tool
def track_shipment(order_id: str) -> dict:
    """Live courier location for an in-transit order. Needs an order ID."""
    return t.track_shipment(order_id)


model = ChatGoogleGenerativeAI(model=os.environ["LLM_MODEL"],
                               google_api_key=os.environ["LLM_API_KEY"])

SYSTEM = ("You answer questions about an order database using the tools provided. "
          "Never invent argument values. If a tool errors, retry at most once, "
          "then answer with what you know and say what was unavailable.")

# THE WHOLE LOOP. This one call replaces ~90 lines of agent.py: the while loop,
# the finish_reason branch, appending tool results with matching tool_call_ids,
# and the provider-metadata handling.
agent = create_agent(model, [list_orders, get_order, track_shipment],
                     system_prompt=SYSTEM)

def text_of(msg) -> str:
    """Content is a STRING on some providers and a list of blocks on others.
    Another abstraction that leaks: you still write provider-shaped code."""
    c = msg.content
    if isinstance(c, str):
        return c
    return " ".join(b.get("text", "") for b in c if isinstance(b, dict))


def run(question: str):
    print(f"\nQ: {question}")
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    # No trace is printed for you - you dig it out of the returned message list.
    for m in result["messages"]:
        if calls := getattr(m, "tool_calls", None):
            for c in calls:
                print(f"  [call  ] {c['name']}({c['args']})")
        elif m.__class__.__name__ == "ToolMessage":
            print(f"  [result] {str(m.content)[:82]}")
    print(f"  FINAL -> {text_of(result['messages'][-1]).strip()[:220]}")
    print(f"  ({len(result['messages'])} messages in final state)")


if len(sys.argv) > 1:
    run(sys.argv[1])
    sys.exit()

print("=" * 74)
print("1. THE HAPPY PATH - one create_agent() call replaces agent.py's loop")
print("=" * 74)
run("What did Priya Sharma's cancelled order cost?")

print("\n" + "=" * 74)
print("2. THE SAME QUESTION THAT KILLED 06_agents/1_fragile.py")
print("=" * 74)
try:
    run("Where is Neha Gupta's coffee maker right now?")
except Exception as e:
    print(f"\n  CRASHED: {type(e).__name__}: {str(e)[:70]}")
    print("""
  track_shipment raised, and the framework let it escape - exactly like
  1_fragile.py, before you wrote dispatch(). You got the LOOP for free.
  You did NOT get:
      - errors fed back as context instead of crashing  (2_robust.py)
      - a repetition guard on (tool, args)              (3_loops.py)
      - round AND call budgets                          (3_loops.py)
      - a forced final answer when the budget runs out  (3_loops.py)
      - an approval gate on irreversible tools          (4_write.py)

  A framework gives you the part that was easy to write. Getting the guards
  back is 2_control.py.""")
