# serving - the agent behind HTTP

A side-track, not a numbered topic. Takes `06_agents/agent.py` and puts it
behind an API.

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
| sessions | every call starts cold - multi-turn needs a conversation store |
| cost tracking | `Result` has `rounds`/`calls`; nobody is logging them |

That list is `13_production`, and most of it is not AI-specific - it is ordinary
service engineering, which is most of the job.
