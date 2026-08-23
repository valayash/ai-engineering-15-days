# AI Engineering in 15 Days — code-first

Stack: Python + Google Gemini (`google-genai`). Key in `.env` as `GOOGLE_API_KEY`.
Run anything with `uv run day1/1_simple.py "your prompt"`.

## Plan

| Day | Topic | You build |
|-----|-------|-----------|
| 1 | Calls, system prompts, context, tokens, streaming | CLI chatbot with real memory |
| 2 | Prompt engineering *as engineering* | A prompt test harness |
| 3 | Structured output you can trust | Text -> typed object extractor |
| 4 | Tool / function calling | LLM that queries a real SQLite DB |
| 5 | The agent loop, from scratch (no framework) | ReAct agent in ~100 lines |
| 6 | Embeddings + vector math | Semantic search over your docs |
| 7 | Chunking + a vector DB | Mini RAG, end to end |
| 8 | RAG that actually works | Hybrid search, reranking, citations |
| 9 | Evaluation | LLM-as-judge + regression suite |
| 10 | Agent memory, planning, multi-step | Multi-step task agent |
| 11 | **LangChain + LangGraph** | Rebuild the Day 5 agent in LangGraph, compare |
| 12 | **MCP (Model Context Protocol)** | Your own MCP server |
| 13 | Production: cost, caching, retries, tracing, guardrails | Hardened client + prompt-injection defense |
| 14 | Capstone | One full app |
| 15 | Interview prep | AI system design + defending your build |

**Why frameworks come at Day 11, not Day 1:** LangChain/LangGraph wrap the
things you build in Days 1-10. Build them by hand first, then the framework is
obvious instead of magic - and you can say in an interview what it bought you
and what it cost.

## The mental model

An LLM API is a **stateless function**. No memory, no learning at request time.
If the model knows something, it was in the training data or *you put it in the
prompt*.

Everything else - chat memory, RAG, agents, tools - is **scaffolding you build
around that stateless function**.

```
+-- CONTEXT WINDOW ------------------------------+
|  system_instruction   <- rules, never grows     |
|  contents[]           <- conversation, grows    |
|  (+ retrieved docs, tool defs, tool results)    |
+-------------------------------------------------+
```

## Two tracks

Every day exists twice:

| folder | client | why |
|--------|--------|-----|
| `dayN/` | `llm.py` - the `openai` SDK | how you'd actually ship it |
| `dayN/raw/` | `llm_raw.py` - plain `httpx` | see every byte on the wire |

Identical behaviour, identical `.env`. The raw version is a plain
`POST {LLM_BASE_URL}/chat/completions` with a JSON body - no magic. Read the raw
one to understand the mechanism, use the SDK one when you want retries and
types for free.

## Progress

- [x] **Day 1** - calls, system prompt, context, streaming
  - `1_simple` `2_system` `3_context` `4_stream`
  - open thread: `messages` grows forever -> trim it on Day 2
- [x] **Day 2a** - context management: `1_problem` `2_window` `3_summary`
  - full history -> quadratic cost; window -> flat but forgets; summary -> lossy but remembers
- [x] **Day 2b** - prompt engineering, measured: `4_measure` `5_hard`
  - v1 naive 0/6 (format, not knowledge) -> v2 constrained 6/6
  - hard set: no escape hatch = confident garbage; few-shot 0-for-2; v4 fixed one case and broke another
  - v5 10/10: define categories, don't patch with rules
- [x] **Day 3** - structured output: `1_naive` `2_json_mode` `3_schema`
  - prompt-only -> markdown fences, crash; json_object -> parses but free-form values
  - Pydantic schema -> constrained decoding: shape + closed vocabulary guaranteed
  - schema guarantees SHAPE, never CORRECTNESS - still need Day 2's eval harness
- [ ] Day 4 - tool calling (same mechanism as schemas)
