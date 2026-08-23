"""Step 1: the loop from 05, unchanged - meeting a tool that fails.

usage: uv run 06_agents/1_fragile.py ["your question"]

Nothing here is wrong with the MODEL. The loop is what's fragile.
"""
import json, sys
from llm import chat
from tools import TOOLS, FUNCS

DEFAULT = "Where is Neha Gupta's coffee maker right now?"
QUESTION = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
print(f"Q: {QUESTION}\n")

messages = [{"role": "user", "content": QUESTION}]

for rnd in range(1, 6):
    msg = chat(messages, tools=TOOLS).choices[0].message

    if not msg.tool_calls:
        print(f"\nround {rnd}: FINAL -> {msg.content}")
        break

    messages.append(msg)
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)

        # THE BUG. Two unguarded assumptions on one line:
        #   1. FUNCS[name]  - that the model named a tool that exists
        #   2. (**args)     - that it will not raise
        result = FUNCS[tc.function.name](**args)

        print(f"round {rnd}: {tc.function.name}({args}) -> {str(result)[:90]}")
        messages.append({"role": "tool", "tool_call_id": tc.id,
                         "content": json.dumps(result)})
else:
    print("\ngave up after 5 rounds")
