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

## Recovery is mostly free - measure before you credit the prompt

`2_robust.py` on the failing courier:

```
round 2: !! track_shipment -> error
round 3: !! track_shipment -> error      (retried once)
round 4:    get_order      -> ok         (fell back on its own)
round 5: FINAL -> "in_transit ... live tracking is unavailable"
```

The fallback to `get_order` is not in the code, so it is tempting to credit the
system prompt. **Tested, and that is wrong.** Same file with `SYSTEM` deleted,
three trials, identical every time:

```
round 2: !! track_shipment -> error
round 3:    get_order      -> ok         (no retry, straight to fallback)
round 4: FINAL -> same honest answer
```

Recovery is this model's *default* behaviour once the error is in context. The
only measurable difference the prompt made was **adding a retry** - which for a
permanently-dead service is strictly worse.

So `dispatch()` is doing nearly all the work, and the split is:

| | job | fails how |
|-|-----|-----------|
| `dispatch()` | keep the process alive and put the error in context | hard - traceback |
| `SYSTEM` | policy once the error is there: retry count, when to stop, honesty | soft - bad judgement |

Keep the prompt anyway, for the clause none of these runs exercised:

> *"Never claim a tool succeeded when it returned an error."*

A silent fabricated tracking location is the failure that costs you, and it is
the one you will not notice in a demo. But treat that as a **hypothesis to
test**, not a fact - the same way `03_prompting` made you score prompt versions
instead of trusting them. An untested sentence in a system prompt is decoration.
