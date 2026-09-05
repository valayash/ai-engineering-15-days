# 11 - Frameworks

Rebuild `06_agents` with LangChain/LangGraph and find out exactly what a
framework buys and what it hides. This comes at 11, not 01, on purpose: you
cannot see what is being abstracted until you have written it by hand.

| file | teaches |
|------|---------|
| `1_prebuilt.py` | `create_agent()` replaces the loop - and what comes back missing |
| `2_control.py` | putting 06's guards back, as middleware |
| `3_approval.py` | the write gate - where the framework beats the hand-rolled version |

```bash
uv run 11_frameworks/1_prebuilt.py
uv run 11_frameworks/1_prebuilt.py "which orders are in transit?"
uv run 11_frameworks/2_control.py
uv run 11_frameworks/2_control.py --stubborn    # watch the loop guard fire
uv run 11_frameworks/3_approval.py
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

## Getting the guards back (2_control.py)

The real question about any framework is not "what does it do for free" but
"when the defaults are not yours, is changing them clean or a fight?"

LangChain's answer is **middleware** - objects that wrap steps of the loop.
Four of the five guards from `06_agents` are one line each:

| 06_agents, by hand | LangChain |
|--------------------|-----------|
| `dispatch()` - errors become context | `ToolErrorMiddleware(on_error=...)` |
| `MAX_CALLS` | `ToolCallLimitMiddleware(run_limit=12)` |
| `MAX_ROUNDS` | `ModelCallLimitMiddleware(run_limit=6)` |
| approval gate on writes | `HumanInTheLoopMiddleware(interrupt_on=...)` |
| **repetition guard on `(tool, args)`** | **not provided - write it** |

That is a good showing. Rerun the question that crashed `1_prebuilt.py` and the
agent now survives, retries once, and answers honestly - the same behaviour as
the hand-built `2_robust.py`.

### The fifth guard is still yours

There is no repetition middleware. `@wrap_tool_call` gives you the interception
point; the logic is yours:

```python
@wrap_tool_call
def repetition_guard(request, handler):
    sig = f"{call['name']}({json.dumps(call['args'], sort_keys=True)})"
    if seen[sig] > REPEAT_LIMIT:
        return ToolMessage(content="loop guard: ...", tool_call_id=call["id"])
    return handler(request)
```

`sort_keys` is still load-bearing - the framework has no opinion about argument
canonicalisation, so without it the model escapes the guard by reordering keys.
`--stubborn` proves it fires:

```
[!!    ] track_shipment raised ConnectionError
[!!    ] track_shipment raised ConnectionError
[LOOP  ] blocked track_shipment({"order_id": "SR-1005"})
-> rerouted to get_order, answered honestly
```

Same output as `06_agents/3_loops.py --stubborn`. **A framework covers the
failures its authors met. Yours are still yours.**

## Where the framework is genuinely better (3_approval.py)

`4_write.py`'s gate was a blocking `input()` inside the loop. That works at a
terminal and nowhere else - no human at 3am means the process hangs, and an HTTP
request cannot sit open waiting for someone to click yes.

LangGraph models approval as an **interrupt**:

```
invoke()  -> agent runs, hits cancel_order, STOPS
          -> full state written to a checkpointer
          -> the process is free to exit
          ...
invoke(Command(resume={"decisions": [{"type": "approve"}]}), same_thread_id)
          -> resumes from saved state and continues
```

Measured, both paths:

| decision | answer | DB after |
|----------|--------|----------|
| `approve` | "SR-1005 has been successfully cancelled and refunded" | `cancelled` |
| `reject` | "was not canceled because you rejected the cancellation" | `in_transit` |

This is **better than what we built by hand**, and worth admitting plainly. The
resume can arrive from a different request, a different process, or tomorrow -
which is the shape a real approval queue needs. The decision vocabulary is also
richer than yes/no: `approve | reject | edit | respond`, where `edit` lets a
human fix the arguments before the tool runs. Our `input()` could not do that.

Note what did NOT move into the framework: `cancel_order`'s preconditions
(delivered orders cannot be cancelled, cancelling twice does not refund twice)
still live inside the function. That was the right call in `4_write.py` and it
stays right here - **a prompt is a suggestion and middleware is configuration,
but a function is not.**

## Two API details that cost time

Both were found by reading the source, not the docs:

- resume payload is `{"decisions": [...]}`, not a bare list
- the decision word is `approve`, not `accept` - `accept` raises

Version churn is the standing tax on frameworks. The error messages were good,
but only because we already knew what the code was supposed to do.
