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

```bash
uv run 08_rag/corpus.py                 # build the index (cached)
uv run 08_rag/1_naive.py
uv run 08_rag/1_naive.py "what does error E-419 mean"
uv run 08_rag/2_hard.py
uv run 08_rag/3_grounded.py
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
