"""Step 3: several tools, and answers that need MORE THAN ONE round.

usage: uv run 05_tools/3_multi.py ["your question"]
"""
import json, sys
from llm import chat
from db import connect

con = connect()


def list_orders(customer: str) -> list:
    rows = con.execute("SELECT order_id, item, status FROM orders "
                       "WHERE customer LIKE ?", (f"%{customer}%",)).fetchall()
    return [dict(r) for r in rows]


def get_order(order_id: str) -> dict:
    row = con.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row) if row else {"error": f"no order {order_id}"}


FUNCS = {"list_orders": list_orders, "get_order": get_order}

TOOLS = [
    {"type": "function", "function": {
        "name": "list_orders",
        "description": "List a customer's orders (id, item, status). Use when you "
                       "have a name but no order ID.",
        "parameters": {"type": "object",
                       "properties": {"customer": {"type": "string"}},
                       "required": ["customer"]}}},
    {"type": "function", "function": {
        "name": "get_order",
        "description": "Full details of ONE order including amount. Needs an order ID.",
        "parameters": {"type": "object",
                       "properties": {"order_id": {"type": "string"}},
                       "required": ["order_id"]}}},
]

DEFAULT = "What did Priya Sharma's cancelled order cost?"
QUESTION = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
print(f"Q: {QUESTION}\n")
messages = [{"role": "user", "content": QUESTION}]

# The loop. You do NOT know in advance how many rounds this takes.
for rnd in range(1, 6):
    msg = chat(messages, tools=TOOLS).choices[0].message

    if not msg.tool_calls:                       # no more tools wanted -> it's done
        print(f"\nround {rnd}: FINAL -> {msg.content}")
        break

    messages.append(msg)
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        result = FUNCS[tc.function.name](**args)
        print(f"round {rnd}: {tc.function.name}({args}) -> {str(result)[:90]}")
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result)})
else:
    print("\ngave up after 5 rounds")            # the runaway-loop guard
