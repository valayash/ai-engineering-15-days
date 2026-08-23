"""Step 1: declare a tool. See what the model ASKS for. Run nothing yet."""
from llm import chat

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_order",
        "description": "Look up one order by its ID. Returns item, amount, status, date.",
        "parameters": {                          # <-- a JSON Schema. same idea as day 04.
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "for example SR-1001"},
            },
            "required": ["order_id"],
        },
    },
}]

for question in ["Where is order SR-1003?", "What is 2 + 2?"]:
    resp = chat([{"role": "user", "content": question}], tools=TOOLS)
    msg = resp.choices[0].message

    print(f"\n=== {question}")
    print("  finish_reason :", resp.choices[0].finish_reason)
    print("  content       :", repr(msg.content))
    if msg.tool_calls:
        for tc in msg.tool_calls:
            print("  TOOL CALL     :", tc.function.name, tc.function.arguments)
            print("  call id       :", tc.id)
    else:
        print("  tool_calls    : None   <- answered on its own")
