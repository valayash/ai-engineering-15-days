# 08 - RAG

Retrieval you already built in `07_embeddings`. RAG is that plus **generation**:

```
retrieve top-k  ->  paste into the prompt  ->  ask the model
```

There is no other step. Everything hard about RAG is in what you retrieve.

| file | teaches |
|------|---------|
| `corpus.py` | the knowledge base + a cached index; `MESSY` adds realistic rot |
| `1_naive.py` | the whole pipeline, against a clean corpus |
| `2_hard.py` | the same code, four extra documents, everything breaks |
| `kb.py` | a chunk as a RECORD - id, source, effective date, status, authority |
| `3_grounded.py` | filter-then-rank + citations - the fix for `2_hard` |
| `4_rerank.py` | retrieve wide, rerank narrow - and a real "found nothing" signal |
| `rag.py` | all of the above as one function - **this is what you ship** |

```bash
uv run 08_rag/corpus.py                 # build the index (cached)
uv run 08_rag/1_naive.py
uv run 08_rag/1_naive.py "what does error E-419 mean"
uv run 08_rag/2_hard.py
uv run 08_rag/3_grounded.py
uv run 08_rag/4_rerank.py
uv run 08_rag/rag.py "what does error E-419 mean"
```

## The index stores the model name

```python
key = {"model": EMBED_MODEL, "n": len(DOCS), "hash": hash(tuple(DOCS))}
```

Vectors from two different embedding models are not comparable - not "less
accurate", **meaningless**. Queries are embedded live, documents were embedded
weeks ago, so changing `LLM_EMBED_MODEL` silently corrupts every search. Storing
the model name next to the vectors forces a re-index instead.

## Naive RAG worked - and I expected it not to

Predicted: with no permission to say "I don't know", the model would answer
out-of-corpus questions from the retrieved junk. It did not. Every one:

| question | answer |
|----------|--------|
| "can I change my delivery address after ordering" | *"there is no information explaining whether..."* |
| "what does error E-500 mean" | *"there is no information explaining what E-500 means"* |
| "what is the GST rate on shipping charges in India" | *"there is no mention of the GST rate..."* |
| "can I use WELCOME10 on my third order" | *"no - it is only valid for your first order"* |

The GST one matters most: the model **knows** that from training and still would
not answer, because the context did not support it. And the WELCOME10 answer is
real inference, not lookup - "third" is never mentioned in any document.

Exact codes retrieved fine too - `E-419`, `REF-2291`, `RMA-`, `WELCOME10` all hit
rank 1. Note this does **not** contradict `07_embeddings`' finding that `SR-1005`
and `SR-1003` score 0.91: that compared two *bare identifiers*. Here the codes sit
inside distinguishing sentences.

So: modern models, given clean grounded context, behave far better than RAG
folklore claims. Which raises the real question - what actually fails?

## The corpus fails, not the model

`1_naive.py` works because its corpus is 16 clean, single-topic,
non-contradictory documents. No real knowledge base is that. `2_hard.py` adds
four documents of the kind every company accumulates - **no code changes**:

- a superseded refund policy nobody deleted (10-14 days vs the current 5-7)
- marketing copy promising 30-day returns when the policy says 7
- a troubleshooting page mentioning `E-402` without defining it
- a near-duplicate delivery-cost doc with different numbers (Rs 49 vs Rs 99)

Every question broke:

| question | clean | messy |
|----------|-------|-------|
| how long do refunds take | "5-7 business days" | **both** 5-7 *and* 10-14 |
| how many days to return | "7 days" | 7 days *or alternatively* 30 |
| how much is delivery | "Rs 99 / free over 500" | **"flat Rs 49"** |

And the scores are the point:

```
0.721  Refunds ... within 10-14 business days     <- stale, RANKED FIRST
0.710  Refunds ... within 5-7 business days       <- current

0.696  Delivery ... flat Rs 49 (mobile app)       <- near-duplicate, RANKED FIRST
0.641  Standard delivery costs Rs 99...           <- correct
```

**The distractor outranked the truth in two of three cases.** Cosine similarity
has no concept of *current*, *authoritative*, or *correct* - only *similar*. A
stale policy is worded almost identically to the live one, so of course it scores
well. That is not a bug in the retriever; it is the retriever working exactly as
designed on a corpus that lies.

## Notice what the model did NOT do

It did not hallucinate. It faithfully reported the contradictory context it was
given, and even flagged the contradiction. **A better prompt cannot fix this** -
both statements really are in the context, and nothing in the text says which is
current.

> Naive RAG fails on real corpora because real corpora are contradictory,
> redundant and out of date - not because models make things up.

Which reframes the job. The fixes are not prompt engineering:

- **metadata** - effective dates, versions, source authority, stored *with* each chunk
- **filtering before ranking** - `WHERE status = 'current'`, which is what vector
  DBs' metadata filters are actually for
- **deleting things** - the cheapest and least popular fix
- **reranking** - a model that scores query-vs-document directly, better at
  "which of these two near-identical docs answers the question"
- **citations** - so a human can see *which* document produced the answer

RAG quality is a data-governance problem wearing an ML costume. Most teams tune
prompts and chunk sizes for weeks when the actual defect is that nobody deleted
the 2023 policy.

## A chunk is a record, not a string

`1_naive.py` and `2_hard.py` store bare strings. A string cannot tell you when it
was written or whether it still applies, so a retriever built on strings cannot
either. That is the entire reason a 2023 refund policy outranked the live one.

```python
@dataclass(frozen=True)
class Chunk:
    id: str            # citeable handle
    text: str          # the only field that gets embedded
    source: str        # where to go to verify or fix it
    effective: str     # since when
    status: str        # current | superseded
    authority: str     # policy | marketing | support-note
```

**Only `text` is embedded.** Metadata is for filtering and citing, not for
similarity - embedding `"status: superseded"` would make the word *superseded*
part of what queries match against. Noise, not signal.

`authority` earns its place separately from `status`: the 30-day returns banner
is **current** and **wrong**. It is live marketing copy that contradicts live
policy. No date filter catches that; a source-authority filter does.

## Filter first, then rank

```python
pool = [(c, v) for c, v in zip(CHUNKS, VECS) if where is None or where(c)]
scored = sorted(...)[:k]
```

Ranking first and filtering after is a real bug: you ask for k=3, two come back
superseded, you silently hand the model one chunk and never notice the context
got thin. Filter first and k always means k.

This is what a vector DB's metadata filter is actually *for* - not a convenience
feature, the thing that makes a real corpus usable.

## The result

| question | no filter | `status=current AND authority=policy` |
|----------|-----------|----------------------------------------|
| how long do refunds take | 10-14 **and** 5-7 days | "5-7 business days [REF-01]" |
| how many days to return | 7 days **or** 30 days | "7 days from delivery [RET-01]" |
| how much is delivery | "flat Rs 49" | "Rs 99 below Rs 500 [SHP-01]" |
| can I change my address | *"I don't have that information."* | *"I don't have that information."* |

## When the filter changes nothing

Three of the four questions differ sharply between filtered and unfiltered. The
fourth - *"can I change my delivery address"* - returns **exactly the same
answer both ways**: *"I don't have that information."*

That is correct behaviour, not a broken filter. A filter removes wrong-but-similar
documents from the pool. When the top-k contains no such document, removing
nothing changes nothing. Same shape as `06_agents`' loop guard, which never fires
under a sane prompt:

> **A safety mechanism that is invisible in the normal case is working.**

Judge a filter on the cases where the pool *is* poisoned, and count how often
that happens - not on whether every answer changes.

*(A display bug hid this at first: answers were truncated to 200 characters, and
the unfiltered version's extra claim arrives at the END. It printed a preamble
that looked identical while the contradiction was cut off. Print answers in full
when comparing them.)*

## What filtering did NOT do

The stale chunk still scores **0.721**, higher than the correct one at 0.710.
Filtering does not improve the ranking - it removes the candidate from the pool
before ranking happens. You cannot fix a ranking problem by rewriting the query;
you fix it by not offering the wrong document in the first place.

The last row is worth noting too: the address question was refused **with and
without** filtering. Metadata fixed contradictions, not refusals - those were
already fine. Fix the failure you measured, not the one you assumed.

## Citations make it checkable

```
Refunds are processed within 5-7 business days [REF-01].
```

`REF-01` resolves to `refund-policy.md`, effective 2026-02-01. A support agent
can open that file; an auditor can trace the claim; and when the answer is wrong
you learn whether the **retrieval** or the **generation** failed - which are
different bugs with different fixes.

The prompt also spells out the escape hatch:

> *"If the sources do not answer the question, say exactly: I don't have that
> information."*

Fifth appearance of the same principle - `"required": ["customer"]`, *"never
answer without tracking data"*, `"hi"` with no `other` category, top-k with
nothing relevant, and now this. **Make "I don't know" a legal move.**

## Reranking (4_rerank.py)

`3_grounded.py` always sends exactly k chunks. We watched `RET-01` - a returns
policy - land in a delivery question's top-3 purely to fill a slot. Two costs:
tokens for noise, and no way to know when *nothing* is relevant.

```
vector search   cheap, imprecise  ->  cast a wide net (n=6)
rerank          costly, precise   ->  keep what earns its place
```

The reranker scores each candidate against the question **directly** rather than
by vector distance. One call grades all six, using `04_structured_output`'s
machinery for real work:

```python
grade: Literal["answers", "related", "irrelevant"]
```

A `Literal` means an invalid grade is not discouraged, it is **impossible**. And
the three-way split matters - *related* is the trap category. `SHP-03`
("delivery takes 3-5 days") is genuinely about delivery and does not answer
"how much is delivery". Vector search cannot express that difference; it only
knows both are near the query.

## Result

| question | vector top-3 | after rerank |
|----------|--------------|--------------|
| how much is delivery | `SHP-01, INT-01, RET-01` (328 chars) | `SHP-01` (103) |
| what does E-419 mean | `ERR-419, ERR-402, PRO-01` (372 chars) | `ERR-419` (120) |
| can I change my address | `CAN-01, TRK-01, RET-01` (362 chars) | **nothing** (0) |

~70% less context, same answers. Note `ERR-402` on the E-419 question: cosine
ranked it **second** at 0.656, and it is flatly irrelevant - a different error
code. The reranker caught that; no similarity threshold would have.

## The empty result is the point

```
-> nothing graded 'answers'. Refusing WITHOUT calling the model.
```

Back in `07_embeddings` the problem was that top-k always returns k, unrelated
text scores 0.48, and no threshold separates answerable from unanswerable. **A
reranker is the answer to that**, because it returns a *judgement*, not a
distance. An empty list is a real signal that cosine cannot produce at any k.

It also saves the generation call entirely - the refusal costs one rerank instead
of a rerank plus a generate.

## Cost, honestly

Reranking adds an LLM call per query. It buys back some of it (smaller context to
generate from, skipped generation on refusals) but not all. In production you
would use a purpose-built **cross-encoder** reranker - Cohere Rerank, BGE, a
hosted reranking endpoint - which is far cheaper and faster than a general LLM
for exactly this. Using `parse()` here is a stand-in that teaches the shape with
the API we already have.

## Hybrid search, deliberately skipped

The usual next chapter is BM25 + vector fusion for exact terms. It is not here
because **the case for it did not reproduce**: `E-419`, `REF-2291`, `RMA-` and
`WELCOME10` all retrieve at rank 1 by vector alone (`07_embeddings`' 0.91 score
between `SR-1005` and `SR-1003` was two *bare* identifiers, not identifiers
inside distinguishing sentences).

You would reach for hybrid when identifiers appear in many chunks so the
distinguishing signal is the exact token, when the corpus is large enough that
near-duplicates crowd the top-k, or for rare proper nouns the embedding model
never saw. None of those is true of 17 clean chunks - so adding it here would
have been cargo-culting, and `09_evals` is how you would decide rather than guess.

## "Do I have to implement all of this?"

No. This folder has five demo files because it keeps every **failure** around as
runnable evidence - `1_naive.py` and `2_hard.py` exist to prove `3_grounded.py`
is a fix and not arbitrary complexity. You would never ship them.

What you ship is `rag.py`: **71 lines, one function.**

```python
from rag import answer
r = answer("how much is delivery", chunks=CHUNKS, vectors=VECS, where=CURRENT_POLICY)
r.text        # "Rs 99 for orders below Rs 500 ... [SHP-01]"
r.sources     # the chunks actually cited
r.refused     # True when nothing was relevant
```

## Build it in this order, not all at once

| step | lines | add it when |
|------|-------|-------------|
| retrieve top-3, stuff, generate | ~25 | day one, always |
| metadata + `where` filter | +10 | the first time production quotes a stale policy |
| citations in the prompt | +3 | immediately - it is free and makes every bug diagnosable |
| rerank | +20 | context noise costs real money, or you need honest refusals |
| hybrid search | +30 | only after measuring that keyword beats vector on YOUR queries |

Each row is a response to a failure you have actually observed. Building all of
them upfront means carrying complexity you cannot justify and cannot tune,
because you have no evidence about which part is doing the work.

## Where the real difficulty is

Not in these 71 lines. It is in:

- **the corpus pipeline** - ingesting documents, chunking, re-embedding when they
  change, and *deleting* what is stale. This is bigger than the RAG code and
  nobody puts it in tutorials.
- **knowing which knob to turn.** Every decision here - k, chunk size, filter,
  rerank on/off - looks reasonable. Eyeballing a few answers has been wrong three
  times across this repo. That is `09_evals`, and it is what turns the ladder
  above from guesswork into a decision.

The code is the easy part. The data governance and the measurement are the job.
