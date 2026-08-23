"""Step 2: the same broken tool, but the agent survives it.

usage: uv run 06_agents/2_robust.py ["your question"]
       uv run 06_agents/2_robust.py --selftest     # no API calls, proves each guard

One rule: dispatch() NEVER raises. Every failure becomes a tool message, which
means the model can READ it and decide what to do. An exception ends the run;
an error message is just more context.
"""
import inspect, json, sys
from llm import chat
from tools import TOOLS, FUNCS


def dispatch(name: str, raw_args: str) -> dict:
    """Run a tool the model asked for. Four things can go wrong; none escape."""

    fn = FUNCS.get(name)
    if fn is None:                                   # 1. tool doesn't exist
        return {"error": f"no tool named {name!r}. available: {list(FUNCS)}"}

    try:                                             # 2. arguments aren't JSON
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError as e:
        return {"error": f"arguments were not valid JSON: {e}"}

    try:                                             # 3. wrong / missing arguments
        inspect.signature(fn).bind(**args)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}

    try:                                             # 4. the tool itself raises
        return fn(**args)
    except Exception as e:
        return {"error": f"{name} failed: {type(e).__name__}: {e}"}


# Fault injection: call dispatch directly with what a misbehaving model sends.
# Deterministic, instant, free - you don't have to wait for a real model to slip.
if "--selftest" in sys.argv:
    for name, raw in [("cancel_order",   '{"order_id": "SR-1001"}'),   # hallucinated
                      ("get_order",      '{"order_id": '),             # truncated JSON
                      ("get_order",      '{"orderId": "SR-1001"}'),    # camelCase typo
                      ("track_shipment", '{"order_id": "SR-1005"}'),   # tool raises
                      ("get_order",      '{"order_id": "SR-1005"}')]:  # the happy path
        print(f"{name:<15} {raw:<28} -> {str(dispatch(name, raw))[:78]}")
    sys.exit()


DEFAULT = "Where is Neha Gupta's coffee maker right now?"
QUESTION = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
print(f"Q: {QUESTION}\n")

# Errors reaching the model is only half of it - it also needs a policy.
SYSTEM = ("You answer questions about an order database using the tools provided. "
          "Never invent argument values; omit an argument rather than guessing. "
          "If a tool returns an error, retry it at most once. If it still fails, "
          "answer with whatever you do know and state plainly what was unavailable. "
          "Never claim a tool succeeded when it returned an error.")

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": QUESTION}]

for rnd in range(1, 6):
    msg = chat(messages, tools=TOOLS).choices[0].message

    if not msg.tool_calls:
        print(f"\nround {rnd}: FINAL -> {msg.content}")
        break

    messages.append(msg)
    for tc in msg.tool_calls:
        result = dispatch(tc.function.name, tc.function.arguments)
        flag = "!!" if isinstance(result, dict) and "error" in result else "  "
        print(f"round {rnd}: {flag} {tc.function.name}({tc.function.arguments}) "
              f"-> {str(result)[:80]}")
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result)})
else:
    print("\ngave up after 5 rounds")
