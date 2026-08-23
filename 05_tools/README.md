# 05 - Tool calling

The model **cannot do anything**. It has no DB, no network, no filesystem.
Tool calling is a protocol where it *asks*, and **your code** executes.

| file | teaches |
|------|---------|
| `db.py` | seeds `data/orders.db` - real data the model was never trained on |
| `1_declare.py` | declare a tool; the model decides whether it needs one |
| `2_execute.py` | run it, feed the result back, get a grounded answer |
| `3_multi.py` | several tools + a loop, because one round isn't enough |

```bash
uv run 05_tools/db.py                      # inspect the data
uv run 05_tools/3_multi.py                 # uses the default question
uv run 05_tools/3_multi.py "Which of Arjun Mehta's orders is in transit?"
```

All three scripts take an optional question and fall back to a default.
Round count varies with the question - "cancelled order cost" needs 2 tool
calls, "which order is in transit" needs 1, because `list_orders` already
returns status. Same code, different plan, decided at runtime.

## The round trip

```
user question
  -> model: finish_reason="tool_calls", content=None, get_order({"order_id":"SR-1003"})
  -> YOUR code runs the SQL
  -> you append {"role":"tool", "tool_call_id":..., "content": json}
  -> model: finish_reason="stop", writes the answer
```

`messages` ends up as `user` -> `assistant(tool_calls)` -> `tool` -> `assistant`.
Still just a list you append to.

## Takeaways

- **A tool definition is JSON Schema** - the same machinery as `04_structured_output`.
  Tool calling *is* structured output, describing a function's arguments instead
  of your output shape.
- **`description` is prompt text.** In `3_multi.py` the model planned
  name -> `list_orders` -> `get_order` -> answer purely from two description
  sentences. Vague descriptions are the #1 cause of wrong tool choice.
- **`arguments` is a JSON string**, not a dict. `json.loads` it.
- **`tool_call_id` must match** - the model can request several tools at once.
- **Append the assistant message verbatim** (`messages.append(msg)`). Rebuilding it
  field-by-field drops provider metadata - Gemini attaches an opaque
  `thought_signature` to tool calls and 400s without it.
- **`finish_reason`** is the branch: `"tool_calls"` = it wants something,
  `"stop"` = it answered.
- **You cannot know the number of rounds in advance.** Hence a loop, hence
  `range(1, 6)` as a runaway guard. A model stuck on a failing tool will call it
  forever and bill you for it.
- Tool results pile into `messages`, so long agent runs blow the context window.
  `02_context` applies here too.

## Tool design decides agent behaviour

`list_orders` originally had `"required": ["customer"]`. Asked *"which orders are
still in transit?"* - a question with no customer in it - the model **invented
`customer: "Alice"`**, got `[]`, and gave up.

That is not the model being dumb. Constrained decoding *forces* a string into a
required field; inventing one was the only legal move. Three fixes, in order of
how much they mattered:

1. **`"required": []`** - make genuinely optional arguments optional. The escape hatch.
2. **`"enum": [...]` on `status`** - makes an invalid value impossible, and silently
   documents your data so the model uses `in_transit`, not `"In Transit"`.
3. **A system prompt** - *"never invent argument values, omit them instead."*
   Weakest of the three: a prompt can be ignored, a schema cannot.

> **When an agent misbehaves, look at the tool surface before the prompt.**

Same root cause as `03_prompting` classifying `"hi"` as `account` with no `other`
category available: **forced choice produces confident garbage.**

## A tool is any function you let the model trigger

Not database-specific: plain functions, HTTP APIs, filesystem, shell commands,
vector search (that's RAG, `08_rag`), or another LLM (sub-agents, `10_memory`).
SQLite was chosen because it needs no server and gives real external truth.
