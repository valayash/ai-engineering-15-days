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

```bash
uv run 08_rag/corpus.py                 # build the index (cached)
uv run 08_rag/1_naive.py
uv run 08_rag/1_naive.py "what does error E-419 mean"
uv run 08_rag/2_hard.py
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
