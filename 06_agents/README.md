# 06 - Agents

An agent is `05_tools`' loop plus the answer to one question: **what happens
when something goes wrong?** Everything here is about that.

| file | teaches |
|------|---------|
| `tools.py` | the shared toolset - 05's DB tools + `track_shipment`, which always fails |
| `1_fragile.py` | 05's loop, unchanged, meeting a tool that raises. It dies. |
| `2_robust.py` | a dispatcher that never raises - failures become context, not crashes |
| `3_loops.py` | repetition detection, two budgets, and a forced final answer |

```bash
uv run 06_agents/1_fragile.py            # watch it crash
uv run 06_agents/2_robust.py --selftest  # each guard, no API calls
uv run 06_agents/2_robust.py             # same question, survives
uv run 06_agents/3_loops.py --stubborn --noguard   # the runaway
uv run 06_agents/3_loops.py --stubborn             # guard beats the prompt
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

## Not crashing is not the same as stopping

`2_robust.py` turned a crash into an error message. A model that keeps retrying
that error now fails *silently and expensively* instead of loudly. Same broken
courier, a "never give up" system prompt, no guard:

```
round 2 !! track_shipment(SR-1005) -> error
round 3 !! track_shipment(SR-1005) -> error
round 4 !! track_shipment(SR-1005) -> error
round 5 !! track_shipment(SR-1005) -> error      <- billed for every one
```

Nothing in that prompt is unreasonable on its own - *"tracking is critical",
"if a tool fails, try again", "never give up"*. That is the trap: runaway loops
come from prompts that read as diligent.

## Three guards

**1. Repetition, by signature.**

```python
f"{tc.function.name}({json.dumps(args, sort_keys=True)})"
```

`sort_keys` is not cosmetic. Without it `{"a":1,"b":2}` and `{"b":2,"a":1}` are
different strings, and the guard is escaped by key order alone.

Past the limit, **do not run the tool** - return an error saying it is looping.
Same principle as `2_robust.py`: a message it can act on, not a wall it hits.

**2. Two budgets, because rounds are not calls.**

```python
MAX_ROUNDS = 6     # how many times it gets to think
MAX_CALLS  = 12    # one round can contain 8 parallel calls
```

Capping rounds alone lets a single round issue 50 calls. Cap both.

**3. A forced final answer instead of "gave up".**

```python
messages.append({"role": "user", "content":
    "Stop calling tools. Using only what you have already retrieved, answer "
    "the original question and state plainly what you could not find out."})
return chat(messages).choices[0].message.content     # note: no tools=
```

Dropping `tools=` leaves it no other move than prose. By this point the context
holds real data from earlier rounds, so the user gets *"in_transit, live location
unavailable"* rather than a stack trace or silence. **Every agent needs a
degraded-but-useful exit.**

## What the guard did not fix

Same bad prompt, guard on:

```
round 4 LOOP track_shipment(SR-1005)   <- blocked
round 5      get_order(SR-1005)        <- fine
round 6      list_orders({})           <- flailing: different signature, useless
```

The loop guard only catches **exact repeats**. Told never to give up, the model
just wandered to calls it had not made yet and still burned the budget - only
`MAX_CALLS` stopped it, and `force_answer` produced the answer.

> **Guards bound the cost of bad behaviour. They do not produce good behaviour.**

Which is the honest ordering: fix the prompt and the tool surface first; guards
are the seatbelt, not the steering.
