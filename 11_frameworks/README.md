# 11 - Frameworks

Rebuild `06_agents` with LangChain/LangGraph and find out exactly what a
framework buys and what it hides. This comes at 11, not 01, on purpose: you
cannot see what is being abstracted until you have written it by hand.

| file | teaches |
|------|---------|
| `1_prebuilt.py` | `create_agent()` replaces the loop - and what comes back missing |

```bash
uv run 11_frameworks/1_prebuilt.py
uv run 11_frameworks/1_prebuilt.py "which orders are in transit?"
```

## What it buys

```python
agent = create_agent(model, [list_orders, get_order, track_shipment],
                     system_prompt=SYSTEM)
result = agent.invoke({"messages": [{"role": "user", "content": q}]})
```

Two lines replace ~90 in `agent.py`: the while loop, the `finish_reason` branch,
appending tool results with matching `tool_call_id`s, and the message plumbing.
Tools become decorated functions - the docstring is the description, the type
hints are the JSON Schema, so the hand-written `TOOLS` list disappears.

Multi-round chaining works out of the box: *"what did Priya Sharma's cancelled
order cost?"* -> `list_orders` -> `get_order` -> answer.

## Leak 1: the abstraction dropped provider metadata

The obvious way to write this is `ChatOpenAI` pointed at Gemini's
OpenAI-compatible endpoint, since that is what `llm.py` does everywhere else in
this repo. It fails on the second round:

```
400 Function call is missing a thought_signature in functionCall parts
```

Which is `05_tools`' warning, word for word: *"append the assistant message
verbatim - rebuilding it field-by-field drops provider metadata."* LangChain
normalises every provider's reply into its own `AIMessage`, and that
normalisation drops Gemini's opaque `thought_signature`. Verified directly:

```
additional_kwargs keys: ['refusal']
raw tool_calls:         None
'thought_signature' anywhere in the message? False
```

The fix is to stop stacking two lossy abstractions - an OpenAI-shaped shim
underneath a framework-shaped one - and use the provider-native driver
(`langchain-google-genai`), which preserves it as `extras.signature`.

**You could only debug this because you hit the same bug by hand in 05.**
Without that, the error message is unreadable and the framework looks broken.

## Leak 2: you get the loop, not the guards

The second question in the file is the one that killed `06_agents/1_fragile.py`:

```
CRASHED: ConnectionError: courier API: connection timed out after 30s
```

The framework's tool node let the exception escape. So `create_agent` gave you
the loop - the easy part - and none of this:

| your 06_agents code | in the prebuilt agent |
|---------------------|-----------------------|
| `dispatch()` - errors become context, never raise | absent |
| repetition guard on `(tool, args)` | absent |
| `MAX_ROUNDS` **and** `MAX_CALLS` | absent |
| forced final answer on budget exhaustion | absent |
| approval gate on write tools | absent |

Every one of those exists because you watched it fail. A framework's defaults
encode someone else's failures, not yours.

## Leak 3: message content changes shape

`msg.content` is a string on some providers and a list of typed blocks on
others - so `text_of()` in this file is provider-shaped code you are still
writing, inside the abstraction that was supposed to hide the provider.
