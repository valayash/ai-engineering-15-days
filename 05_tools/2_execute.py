"""Step 2: run the function, feed the result back, get a grounded answer.

usage: uv run 05_tools/2_execute.py ["your question"]
"""
import json, sys
from llm import chat
from db import connect

con = connect()


def get_order(order_id: str) -> dict:
    row = con.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row) if row else {"error": f"no order {order_id}"}


TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_order",
        "description": "Look up one order by its ID. Returns item, amount, status, date.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "e.g. SR-1001"}},
            "required": ["order_id"],
        },
    },
}]
FUNCS = {"get_order": get_order}     # name -> real python function

DEFAULT = "Where is order SR-1003 and what did it cost?"
QUESTION = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
messages = [{"role": "user", "content": QUESTION}]
print(f"Q: {QUESTION}\n")

# --- turn 1: model asks for a tool ------------------------------------------
msg = chat(messages, tools=TOOLS).choices[0].message
print("1. model asks :", [(tc.function.name, tc.function.arguments) for tc in msg.tool_calls])

# Record the request in the conversation VERBATIM.
# Don't rebuild it field-by-field: providers attach opaque metadata to tool calls
# (Gemini's "thought_signature") and reject the next request if you drop it.
messages.append(msg)

# --- YOUR code executes it. the model cannot touch the database. ------------
for tc in msg.tool_calls:
    args = json.loads(tc.function.arguments)          # arguments arrive as a STRING
    result = FUNCS[tc.function.name](**args)
    print("2. we run     :", tc.function.name, args, "->", result)

    messages.append({"role": "tool",
                     "tool_call_id": tc.id,           # must match the request id
                     "content": json.dumps(result)})

# --- turn 2: model sees the result and writes the answer --------------------
final = chat(messages, tools=TOOLS)
print("3. model says :", final.choices[0].message.content)
