# serving - the agent behind HTTP

A side-track, not a numbered topic. Takes `06_agents/agent.py` and puts it
behind an API.

| file | |
|------|-|
| `1_api.py` | one-shot: every request starts cold |
| `conversation.py` | `run_turn()` - agent.run() that accepts and returns history |
| `2_session.py` | multi-turn: back-to-back questions that remember |

```bash
uv run uvicorn serving.1_api:app --reload --port 8000
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
     -d '{"question":"Which orders are in transit?"}'
open http://localhost:8000/docs
```

## FastAPI does not deploy anything

| | what it does |
|-|--------------|
| **FastAPI** | turns `run()` into an HTTP endpoint, validates in/out |
| **uvicorn** | the process that actually serves it |
| **Lambda / ECS / a VM** | the thing that runs uvicorn |

Same category error as "deploy the agent on Bedrock". FastAPI is the door, not
the building.

## Why FastAPI specifically, for AI work

- **Pydantic is the validation layer** - the same library as `04_structured_output`.
  Request schemas and LLM output schemas are the same kind of object.
- **`/docs` is generated from the type hints**, not written. That OpenAPI schema
  is also what tool calling and MCP consume - `05_tools`' tool definitions are
  the same JSON Schema.
- **Async matters more here than in CRUD.** An agent is ~99% *waiting on the
  model*, not computing.

## `def`, not `async def`

```python
@app.post("/ask")
def ask(req: Ask) -> Answer:      # NOT async def
```

`llm.py` uses the **synchronous** openai client. In an `async def` handler a
blocking call freezes the whole event loop - the entire server handles one
request at a time. With plain `def`, FastAPI runs the handler in a threadpool
and requests overlap:

```
3 requests: 2.3s + 2.6s + 4.7s = 9.6s of work
wall clock:                       4.9s
```

To use `async def` properly you need `AsyncOpenAI` and `await` all the way down.
Mixing a sync client into async handlers is the most common way to build a
"concurrent" AI service that serves one user at a time.

## The bug this surfaced

First run through HTTP:

```
ProgrammingError: SQLite objects created in a thread can only be
used in that same thread
```

The connection was created at import on the main thread; the handler ran on a
threadpool thread. Code that worked from the CLI broke the moment it went behind
a server - **the threadpool that buys you concurrency is also what broke it.**
Fixed with `check_same_thread=False` in `05_tools/db.py`; concurrent *writes*
over one shared connection would still need a lock or a connection per thread.

Worth noticing what did *not* happen: no 500, no traceback to the client.
`dispatch()`'s blanket `except Exception` turned it into a tool error and the
agent reported it honestly. A guard written for flaky courier APIs caught a
threading bug.

## No writes over HTTP

```python
READ_ONLY = {"list_orders", "get_order", "track_shipment"}
```

`cancel_order` is not exposed at all. `approve=None` would already deny it, but
removing it from the tool surface is the stronger fix - there is no human at an
HTTP endpoint to approve a refund. Any write endpoint needs auth and an
authorisation check *first*, and the model's opinion never substitutes for
either.

## What this deliberately does not do

| missing | why it matters |
|---------|----------------|
| streaming | a 6s blank wait feels broken; agents need SSE progress |
| auth | anyone who can reach the port can spend your API budget |
| per-user rate limits | `llm.py` throttles the *process*, not the caller |
| request timeout | one runaway request holds a thread until the budget ends |
| cost tracking | `Result` has `rounds`/`calls`; nobody is logging them |

That list is `13_production`, and most of it is not AI-specific - it is ordinary
service engineering, which is most of the job.

---

# Multi-turn (2_session.py)

```bash
uv run uvicorn serving.2_session:app --reload --port 8001
```

```bash
curl -s -X POST localhost:8001/chat -H "Content-Type: application/json" -d '{"question":"Which orders are in transit?"}'
```

Then pass the returned `session_id` back:

```bash
curl -s -X POST localhost:8001/chat -H "Content-Type: application/json" -d '{"session_id":"<id>","question":"What did the second one cost?"}'
```

## Why a new runner

`agent.run()` builds `messages` fresh and returns only the answer - there is
nothing to continue from. `conversation.run_turn()` changes exactly two things:

```python
messages = list(history) if history else [{"role": "system", "content": system}]
messages.append({"role": "user", "content": question})
```

and returns `Turn.messages`, the full transcript. `dispatch()` and `signature()`
are **imported** from `agent.py`, not copied - the guards are unchanged.

One subtlety: the repeat counter is per-**turn**, not per-session. Calling
`get_order(SR-1005)` in turn 1 and again in turn 4 is normal conversation, not a
loop. Persisting `seen` across turns would block legitimate repeat questions.

## It works, and the control proves it

```
Q: Which orders are in transit?          -> SR-1003 (Arjun), SR-1005 (Neha)
Q: What did the second one cost?         -> SR-1005, Rs 12,999
Q: Who ordered it?                       -> Neha Gupta
Q: Is that more expensive than the first? -> yes, 12,999 vs 6,499
```

Same follow-up with **no session_id**:

```
Q: What did the second one cost?  ->  "SR-1002, Yoga mat, Rs 1,899"
```

A different order, a different customer, stated with full confidence. No error,
nothing to alert on. That is what "the API is stateless" costs you, and why
losing a session is worse than failing outright.

## The store is deliberately wrong

```python
SESSIONS: dict[str, dict] = {}
```

Three problems, in increasing nastiness:

1. **Dies on restart.** Obvious, tolerable in dev.
2. **Breaks with >1 uvicorn worker.** Turn 2 can land on a different process
   with a different dict, so sessions vanish *intermittently*. Perfect in dev,
   broken under load - the worst kind of bug.
3. **Never evicts.** A memory leak with a session id attached.

The real answer is Redis or a DB, and it is not just `json.dumps`: assistant
messages are **SDK objects carrying provider metadata** (Gemini's
`thought_signature`), and rebuilding them field-by-field 400s - the same trap as
`05_tools`' "append the assistant message verbatim". Pickle them, or store the
provider's own serialization.

## What actually accumulates

`GET /chat/{id}` after 4 turns - 15 messages:

```
system     ...
user       Which orders are in transit?
assistant  ChatCompletionMessage(content=None, tool_calls=[...])
tool       [{"order_id": "SR-1003", ...}]          <- the bulk
assistant  There are 2 orders currently in transit...
...
```

Mostly **tool results**, not chat. Context grew 355 -> 560 -> 592 -> 841 tokens
across four short questions, and every future turn resends all of it. This is
`02_context`'s problem arriving in production: a chatbot grows by a sentence per
turn, an agent grows by a JSON blob per *tool call*.

`MAX_MESSAGES` here is the crudest possible fix - pin the system message, drop
the oldest turns. It is `02_context`'s sliding window, and it will happily cut a
`tool` message away from the `assistant` message that requested it. Summarization
(`02_context/3_summary.py`) is the better answer.

Worth noting turn 3 - *"Who ordered it?"* - used **no tool call at all**. The
answer was already in context. Longer context costs more per turn but can buy
back whole round trips.
