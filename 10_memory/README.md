# 10 - Memory

An LLM API is a stateless function (01_basics). "Memory" is never the model
remembering - it is YOUR system choosing what to keep, and putting it back into
the prompt at the right moment.

| file | teaches |
|------|---------|
| `1_goldfish.py` | the problem: two sessions, and two kinds of lie |
| `2_extract.py` | the write path - what deserves remembering is a model call |
| `3_recall.py` | the read path - semantic search over your own past |

```bash
uv run 10_memory/1_goldfish.py
uv run 10_memory/2_extract.py     # writes data/memories.json
uv run 10_memory/3_recall.py
uv run 10_memory/3_recall.py "any message - see what gets recalled"
```

## The goldfish tells two lies

Session 1: *"I've got all of that saved"* - a promise a stateless API cannot
keep. The model has no way to know it won't exist tomorrow.

Session 2 is worse. Asked where to deliver, it did not say "I don't know" - it
invented **"your default address on file: 42 Maple Street"**. No address, no
file. Forgetting degrades into *fabricated recall*, which the user cannot
distinguish from the real thing.

## The write path: memory is a decision, not a log

Storing the transcript is not memory - it is a log. `2_extract.py` runs the
transcript through a schema-constrained call (04's `parse`) that must decide
what will still matter next month:

- 10-line transcript -> **4 memories**; the weather chat, the already-handled
  order question, and the goodbyes were correctly dropped
- facts are **third person and self-contained** - "Priya prefers refunds",
  never "I prefer refunds" or "she agreed to that" - because they will be read
  with no surrounding context
- relative dates become absolute ("14 November" -> November 14), because
  "tomorrow" is meaningless in three weeks
- `kind` (identity / preference / instruction / event) is metadata for later
  filtering - the `kb.py` lesson again: store it WITH the fact

## The read path: RAG pointed inward

Embed the incoming message, rank stored memories, inject winners into the
system prompt:

```
"where should my order be delivered?"  -> 0.800 office-delivery instruction
"suggest snacks for movie night"       -> 0.550 vegetarian
"what should I do in November?"        -> 0.589 anniversary
```

Same machinery as 07/08, same caveats: the scores are relative (0.492 for a
plainly irrelevant memory - no absolute threshold, rank don't cut), and with 4
memories and k=3 nearly everything is injected anyway. **At small scale, skip
retrieval and inject ALL memories** - the ranking earns its keep at hundreds,
not at four.

The injected block ends with one load-bearing sentence: *"if the user says
something that contradicts a fact on file, what the user says NOW wins."*
Memory must never outrank the person in the room.

## This file's architecture is not hypothetical

It is exactly how Claude Code's own memory works: session ends -> durable facts
extracted to files (third person, absolute dates, typed) -> recalled into
context next session. What you built in three files is the production pattern.

## What is still missing: memories go stale

"Priya moved - deliveries to home now." The office instruction is still on
file, still embeds beautifully, still wins recall. That is `08_rag`'s
superseded-policy problem, pointed inward - and it is `4_stale.py`.
