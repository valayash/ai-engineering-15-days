# 06 - Agents

An agent is `05_tools`' loop plus the answer to one question: **what happens
when something goes wrong?** Everything here is about that.

| file | teaches |
|------|---------|
| `tools.py` | the shared toolset - 05's DB tools + `track_shipment`, which always fails |
| `1_fragile.py` | 05's loop, unchanged, meeting a tool that raises. It dies. |
| `2_robust.py` | a dispatcher that never raises - failures become context, not crashes |

```bash
uv run 06_agents/1_fragile.py            # watch it crash
uv run 06_agents/2_robust.py --selftest  # each guard, no API calls
uv run 06_agents/2_robust.py             # same question, survives
```

## The one line that was fragile

```python
result = FUNCS[tc.function.name](**args)
```

Two unguarded assumptions: that the model named a tool that **exists**, and that
calling it **will not raise**. Both are assumptions about the output of a
probabilistic system.

## Errors are context, not exceptions

```
exception  -> process dies      -> earlier rounds wasted, user gets a traceback
tool error -> {"error": "..."}  -> model reads it and decides what to do
```

`dispatch()` guards four failure modes, in the order they occur:

| # | failure | guard |
|---|---------|-------|
| 1 | hallucinated tool name | `FUNCS.get(name)` -> error listing the real ones |
| 2 | arguments aren't valid JSON | `json.JSONDecodeError` -> error |
| 3 | wrong or missing arguments | `inspect.signature(fn).bind(**args)` |
| 4 | the tool itself raises | blanket `except Exception` |

Guard 3 is worth stealing. `bind()` does full signature validation in one line -
missing required args, unknown args, too many - without writing a validator.

**The error string is prompt text.** *"no tool named 'cancel_order'. available:
[...]"* is a recovery instruction. `"KeyError"` is not. Write them for a reader.

## Test the failures, don't wait for them

`--selftest` calls `dispatch()` directly with what a misbehaving model sends -
a hallucinated name, truncated JSON, a camelCase typo. Deterministic, free, no
API call. You cannot write a reliable test that *asks a model to misbehave*, so
inject the malformed call yourself.

## Recovery is behaviour you get for free, but only if you ask

`2_robust.py` on the failing courier:

```
round 2: !! track_shipment -> error
round 3: !! track_shipment -> error      (retried once, as instructed)
round 4:    get_order      -> ok         (fell back on its own)
round 5: FINAL -> "in_transit ... live tracking is unavailable"
```

The fallback to `get_order` is not in the code. It came from the system prompt:

> *"retry at most once. If it still fails, answer with whatever you do know and
> state plainly what was unavailable. Never claim a tool succeeded when it
> returned an error."*

Without those sentences the same loop retries `track_shipment` until the cap and
returns nothing. **In an agent, the system prompt is error-handling policy** -
how hard to retry, when to give up, what to do with partial results, and whether
it is allowed to paper over a failure. That last clause matters: a model with an
error in context will happily invent a plausible tracking location.
