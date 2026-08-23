# 06 - Agents

An agent is `05_tools`' loop plus the answer to one question: **what happens
when something goes wrong?** Everything here is about that.

| file | teaches |
|------|---------|
| `tools.py` | the shared toolset - 05's DB tools + `track_shipment`, which always fails |
| `1_fragile.py` | 05's loop, unchanged, meeting a tool that raises. It dies. |
| `2_robust.py` | a dispatcher that never raises - failures become context, not crashes |
| `3_loops.py` | repetition detection, two budgets, and a forced final answer |
| `4_write.py` | a tool that MUTATES - approval gates, preconditions, an audit log |

```bash
uv run 06_agents/1_fragile.py            # watch it crash
uv run 06_agents/2_robust.py --selftest  # each guard, no API calls
uv run 06_agents/2_robust.py             # same question, survives
uv run 06_agents/3_loops.py                        # normal
uv run 06_agents/3_loops.py --stubborn             # watch the loop guard fire
uv run 06_agents/4_write.py "Cancel order SR-1005"        # then answer y or n
uv run 06_agents/4_write.py "Cancel Priya Sharma's order" # ambiguous - watch it refuse
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
that error now fails *silently and expensively* instead of loudly.

`--stubborn` swaps in a system prompt that causes it:

> *"Live tracking is critical; the user cannot be helped without it. If a tool
> fails, try again. Never give up, and never answer without live tracking data."*

Every clause is something a reasonable person would write. Together they remove
the model's **exit condition** - the task is defined as impossible to finish, so
the only compliant move is to keep calling. Runaway loops come from prompts that
read as diligent, not from prompts that read as broken.

The missing piece is always the same: *"never answer without X"* with no clause
for what to do when X is unavailable.

## Three guards and an exit

**1. Repetition, by signature.**

```python
f"{tc.function.name}({json.dumps(args, sort_keys=True)})"
```

Same tool + same arguments = same string, counted in a `Counter`. Past the limit
the tool **does not run** - the only guard here that prevents a call rather than
reporting on one.

`sort_keys` is not cosmetic: without it `{"a":1,"b":2}` and `{"b":2,"a":1}` are
different strings and the guard is escaped by key order alone.

`REPEAT_LIMIT = 2` allows two executions and blocks the third - a real retry is
fine, a pattern is not. Counting per *signature*, not per tool name, matters:
`track_shipment(SR-1003)` and `track_shipment(SR-1005)` failing in the same round
is two orders failing once each, not a loop.

**2 and 3. Two budgets, because rounds are not calls.**

```python
MAX_ROUNDS = 6     # how many times it gets to think
MAX_CALLS  = 12    # one round can contain 8 parallel calls
```

Capping rounds alone lets a single round issue 50 calls. Rounds bound your API
bill; calls bound your *side effects*.

**4. A forced final answer instead of "gave up".**

```python
messages.append({"role": "user", "content":
    "Stop calling tools. Using only what you have already retrieved, answer "
    "the original question and state plainly what you could not find out."})
return chat(messages).choices[0].message.content     # note: no tools=
```

Dropping `tools=` leaves no legal move but prose. By then the context holds real
data from earlier rounds, so the user gets *"in_transit, live location
unavailable"* instead of silence. **Every agent needs a degraded-but-useful
exit** - running out of budget is a normal outcome, not an error.

## The loop guard only catches exact repeats

With `--stubborn`, blocking `track_shipment` sent the model to `list_orders({})`
instead - a fresh signature, useless, still billed. `MAX_CALLS` is what stops
that.

> **Guards bound the cost of bad behaviour. They do not produce good behaviour.**

Fix the prompt and the tool surface first. Guards are the seatbelt, not the
steering - and with a sane prompt the guard never fires at all, which is what a
good safety mechanism looks like.

## Reads are cheap to get wrong. Writes are not.

Every guard so far protected your **wallet**. `cancel_order` issues a refund, and
no amount of apologising in round 5 undoes it. Three independent layers, because
any one of them can be talked around.

**1. The tool defends itself.** Preconditions live in the function, not the prompt:

```python
if row["status"] == "cancelled":
    return {"ok": True, "changed": False, "note": "already cancelled"}   # idempotent
if row["status"] == "delivered":
    return {"error": f"{order_id} is already delivered and cannot be cancelled"}
```

A prompt is a suggestion; a function is not. Approving `SR-1001` (delivered) still
changes nothing - the human said yes and the *tool* said no. Idempotency matters
just as much: a retried cancel must not refund twice, so "already cancelled"
returns `ok` with `changed: False` rather than an error.

**2. A human gate on write tools only.**

```python
WRITE_TOOLS = {"cancel_order"}
...
elif name in WRITE_TOOLS:
    if confirm(name, args): ...
```

Reads run unattended - gating them would make the agent useless. Two properties
matter more than the prompt itself:

- **It fails closed.** Anything but an explicit `y` is a no, and `EOFError`
  (cron, CI, piped stdin - nobody there to ask) is also a no. A gate that
  auto-approves when unattended is not a gate.
- **A refusal is data, not a crash.** The denial goes back as a tool message, so
  the model explains it: *"the request was declined by a human reviewer."*

**3. An audit log of approved attempts.**

```
audit log: 1 approved, 0 actually changed the DB
```

Approved and *changed something* are different numbers - conflating them reports
refunds that never happened. This log is also the answer to the partial-batch
problem: `msg.tool_calls` is a list, so a raise partway through leaves some
executions done and some not. Append to the log at the moment of execution and
you still know which.

## Ambiguity is the actual danger

*"Cancel Priya Sharma's order"* - she has three. There is no correct guess, and a
guess costs a real refund. It asked instead:

> *"Could you please clarify which order you would like to cancel?"*

That came from one sentence in the system prompt: *"If the request is ambiguous,
ask which order they mean instead of guessing."* Same shape as `05_tools`'
invented `customer: "Alice"` - **forced choice produces confident garbage**, and
the fix is always to make "I don't know" a legal move.

Note it is only *one* of the three layers, and the weakest. It is why the human
gate exists underneath it.

## Debugging note: check the tool list before blaming the model

First run of this file, the model kept saying it could not cancel anything -
inventing a rule that only `processing` orders are cancellable. That looked like
a refusal to diagnose. It was not:

```python
FUNCS = {..., "cancel_order": cancel_order}      # registered
TOOLS = [...]                                    # NOT declared
```

The function existed, the schema was never added, so the model genuinely had no
such tool and was rationalising its absence. `FUNCS` and `TOOLS` are two lists
that must agree, and nothing checks that they do:

```python
assert sorted(t["function"]["name"] for t in TOOLS) == sorted(FUNCS)
```

Cheap assertion, and it would have saved three confusing runs.
