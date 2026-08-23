"""Step 4: what happens when a tool keeps failing.

usage: uv run 05_tools/4_limits.py ["your question"]
"""
import json, sys
from llm import chat

calls = 0


def get_tracking(order_id: str) -> dict:
    """Deliberately broken - always fails, like a real flaky downstream service."""
    global calls
    calls += 1
    return {"error": "tracking service temporarily unavailable, please retry"}


TOOLS = [{"type": "function", "function": {
    "name": "get_tracking",
    "description": "Live GPS location of a parcel. The only way to know where a parcel is.",
    "parameters": {"type": "object",
                   "properties": {"order_id": {"type": "string"}},
                   "required": ["order_id"]}}}]

MAX_ROUNDS = 5
QUESTION = sys.argv[1] if len(sys.argv) > 1 else "Where exactly is parcel SR-1003 right now?"
# The kind of "be persistent" instruction people really write. Combined with a
# permanently failing tool, it is an infinite loop that bills you by the round.
SYSTEM = ("You are a persistent assistant. Never give up on a task. If a tool "
          "fails, retry it - transient errors usually clear. Do not reply to the "
          "user until you actually have the data they asked for.")

messages = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": QUESTION}]
print(f"Q: {QUESTION}\n")

for rnd in range(1, MAX_ROUNDS + 1):
    msg = chat(messages, tools=TOOLS).choices[0].message

    if not msg.tool_calls:
        print(f"round {rnd}: FINAL -> {msg.content}")
        break

    messages.append(msg)
    for tc in msg.tool_calls:
        result = get_tracking(**json.loads(tc.function.arguments))
        print(f"round {rnd}: get_tracking -> {result['error']}")
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result)})
else:
    print(f"\nHIT THE CAP: {MAX_ROUNDS} rounds, {calls} tool calls, no answer, "
          f"{len(messages)} messages in context.")
