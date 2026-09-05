# 10 - Memory

An LLM API is a stateless function (01_basics). "Memory" is never the model
remembering - it is YOUR system choosing what to keep, and putting it back into
the prompt at the right moment.

| file | teaches |
|------|---------|
| `1_goldfish.py` | the problem: two sessions, and two kinds of lie |
| `2_extract.py` | the write path - what deserves remembering is a model call |
| `3_recall.py` | the read path - semantic search over your own past |
| `4_stale.py` | update and forget - supersession on write, filter on read |

```bash
uv run 10_memory/1_goldfish.py
uv run 10_memory/2_extract.py     # writes data/memories.json
uv run 10_memory/3_recall.py
uv run 10_memory/3_recall.py "any message - see what gets recalled"
uv run 10_memory/4_stale.py
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
file, still embeds beautifully, still gets recalled. That is `08_rag`'s
superseded-policy problem, pointed inward - and it is `4_stale.py`.

## Naive append: the correction loses

A week later Priya says *"I've moved teams and work from home now - send
everything to my flat in Koramangala from now on."* Extract it, append it,
change nothing else. Recall for *"where should my order be delivered?"*:

```
0.828  ...deliveries sent to her flat in Koramangala             <- new
0.800  ...deliveries sent to her office in Indiranagar ... never
       to her home                                               <- stale, still 'current'
```

Both land in the prompt, and the answer comes back:

> *"I've got your office address in Indiranagar, Bengaluru locked in for this
> delivery, just as you prefer!"*

**The new memory outranked the old one and the model still answered with the
old one.** Three runs, three times Indiranagar - not hedged, not flagged, no
mention that a second address was on file. That is worse than `08_rag`'s refund
answer, which at least reported both numbers: the office memory is phrased as an
emphatic standing rule (*"never to her home"*), so it reads as the more
authoritative of the two.

Two things do *not* save you here:

- **ranking.** The retriever worked perfectly - the correct memory was rank 1.
  Retrieval was never the failure; the store containing two live answers was.
- **`3_recall.py`'s escape hatch** - *"what the user says NOW wins"*. The
  correction arrived last week. In this turn there is nothing newer to prefer,
  because the contradiction is entirely inside the memory store.

## Supersession on write

Before storing a new memory, compare it against what is already there. One
`parse()` call grades every existing memory at once (`4_rerank.py`'s shape), and
a `Literal` makes an invalid verdict impossible:

```python
relation: Literal["CONTRADICTS", "UPDATES", "INDEPENDENT"]
```

| stored memory | verdict |
|---------------|---------|
| Priya Sharma is vegetarian | INDEPENDENT |
| Priya Sharma prefers refunds over store credit | INDEPENDENT |
| deliveries to her office in Indiranagar, never her home | **UPDATES** / **CONTRADICTS** |
| wedding anniversary is on November 14 | INDEPENDENT |

That last cell is two values because the delivery memory came back `UPDATES` on
two runs and `CONTRADICTS` on a third - at `temperature=0`. **Temperature 0 is
not determinism.** It costs nothing here only because both verdicts trigger the
same action, which is the design lesson: map several verdicts onto one
behaviour rather than asking for a fine distinction the model cannot hold
stable. If `UPDATES` and `CONTRADICTS` had different consequences, this would be
a coin flip in production.

The other three verdicts matter as much as the hit. An over-eager comparator
that supersedes the vegetarian memory silently destroys a fact nobody was
correcting, so the prompt says most memories are INDEPENDENT and to say so
rather than force a link.

## Marked, not deleted

```python
{"status": "superseded", "superseded_by": <new fact>, "superseded_on": <date>}
```

Deleting is cheaper and it is what `08_rag` recommended for a stale *policy* -
but a memory is not a policy. It is a claim about a person at a point in time,
and *"you shipped my March order to the office"* has to stay answerable a year
from now. Supersession keeps the history and removes it from recall; deletion
loses the audit trail and cannot be undone when the extraction was wrong.

## Filter on read

Same `recall()` function, pool restricted to `status == "current"` - and it is
literally the same function on both paths in the file. With no `status` metadata
the filter removes nothing, which is the point: **a read path is only as good as
what the write path recorded.**

```
0.828  Priya Sharma wants deliveries sent to her flat in Koramangala
0.699  Priya Sharma is vegetarian
0.694  Priya Sharma prefers refunds over store credit
```

| path | pool | recalled | answer says |
|------|------|----------|-------------|
| naive append | 5 | Indiranagar + Koramangala | **Indiranagar** |
| superseded | 4 | Koramangala | **Koramangala** |

This is `08_rag/3_grounded.py` unchanged - filter first, then rank - and it
comes with the same caveat. The stale memory still scores **0.800**. Filtering
did not improve the ranking, it removed the candidate from the pool before
ranking happened, exactly as the superseded refund policy stayed at 0.721 after
the fix. You never fix a ranking problem by ranking harder.

## What it costs

One extra `parse()` call per memory written. That is the right place to pay:
writing happens once per session, recall happens every turn, and a check at
write time makes every future read cheaper and correct. The same check at read
time would be paid forever.

## Expiry is not supersession

Nothing contradicts *"Priya's wedding anniversary is 14 November"*. No
comparator will ever fire on it, however good it is - on 15 November the memory
is simply no longer worth recalling. Those are two different mechanisms:

| | trigger | how |
|---|---------|-----|
| supersession | a new fact arrives | model call at write time |
| expiry | a date passes | a field and a comparison, no model |

Time-based expiry is not built here. The point is only that FORGET is not one
problem - and that a system with supersession still leaks stale memories if it
has no notion of a fact that was true, uncontradicted, and is now over.
