# AI Engineering — code-first

Learning AI engineering by building each piece from scratch, then measuring it.
Every folder is a topic with runnable code and a `README.md` of takeaways.

**Stack:** Python + any OpenAI-compatible API (currently Gemini's free tier).

## Setup

```bash
cp .env.example .env      # paste your key
uv sync
uv run 01_basics/1_simple.py "Hello, tell me about yourself"
```

Provider is config, not code — `.env` holds `LLM_BASE_URL`, `LLM_API_KEY`,
`LLM_MODEL`. Swap to OpenAI, Groq, or a local Ollama model without touching a
line of Python. `.env.example` has ready-to-uncomment blocks.

## Topics

| | topic | status | covers |
|-|-------|--------|--------|
| 01 | [basics](01_basics/) | done | calls, roles, context, streaming, raw HTTP |
| 02 | [context](02_context/) | done | growing-context cost, sliding window, summarization |
| 03 | [prompting](03_prompting/) | done | ground-truth datasets, scoring prompt versions |
| 04 | [structured_output](04_structured_output/) | done | JSON mode, Pydantic schemas, constrained decoding |
| 05 | tools | next | function calling against a real SQLite DB |
| 06 | agents | | the loop, from scratch, no framework |
| 07 | embeddings | | vectors, similarity, semantic search |
| 08 | rag | | chunking, retrieval, reranking, citations |
| 09 | evals | | LLM-as-judge, regression suites |
| 10 | memory | | agent memory, multi-step planning |
| 11 | frameworks | | LangChain + LangGraph (rebuild 06, compare) |
| 12 | mcp | | your own MCP server |
| 13 | production | | cost, caching, retries, tracing, guardrails |
| 14 | capstone | | one full app |

**Why frameworks come at 11, not 01:** LangChain and LangGraph wrap what you
build in 01–10. Build it by hand first and the framework is obvious instead of
magic — and you can say what it bought you and what it cost.

## Shared clients

| file | client |
|------|--------|
| `llm.py` | `openai` SDK + rate limiting. `chat()` `ask()` `parse()` |
| `llm_raw.py` | plain `httpx`. Used only in `01_basics/raw/` to show the wire format |

`LLM_RPM` in `.env` controls the throttle (free tiers are strict).

## The mental model

An LLM API is a **stateless function**. No memory, no learning at request time.
If the model knows something, it was in the training data or *you put it in the
prompt*.

```
+-- CONTEXT WINDOW ------------------------------+
|  system      <- rules you control               |
|  messages[]  <- conversation, grows every turn  |
|  (+ retrieved docs, tool defs, tool results)    |
+-------------------------------------------------+
```

Everything else — chat memory, RAG, agents, tools — is **scaffolding around
that stateless function**. The job is deciding what goes into the context, and
what you do with what comes out.
