# 07 - Embeddings

A different endpoint. `chat()` sends text and gets text; `embed()` sends text and
gets a fixed-length list of floats. No prompt, no sampling, no randomness.

| file | teaches |
|------|---------|
| `1_vectors.py` | what a vector is, fixed size, deterministic, batching |
| `2_similarity.py` | cosine vs keyword overlap - where they disagree |
| `3_search.py` | ranking a corpus, and what it returns when it should return nothing |
| `4_chunking.py` | how the SPLIT changes retrieval - measured, not asserted |

```bash
uv run 07_embeddings/1_vectors.py
uv run 07_embeddings/2_similarity.py
uv run 07_embeddings/3_search.py "how do I get my money back"
uv run 07_embeddings/4_chunking.py
```

`embed()` lives in `llm.py` next to `chat`/`ask`/`parse`. Model comes from
`LLM_EMBED_MODEL` (`gemini-embedding-001`, 3072 dims).

## Fixed size is the whole trick

```
    2 chars -> 3072 dims
   18 chars -> 3072 dims
  950 chars -> 3072 dims
```

One word and one paragraph become the same number of floats. Every text is
squashed to a single point in the same space, so any two texts are comparable
with plain arithmetic - no matter how different their lengths.

Also unlike `chat()`: **deterministic**. Same input, byte-identical vector, max
diff 0.0. There is no temperature because nothing is being sampled.

Batch aggressively - `embed([a, b, c])` is one HTTP call. Indexing a corpus one
text at a time is the most common beginner cost mistake.

## Cosine vs keywords

```python
cosine = dot(a, b) / (norm(a) * norm(b))     # angle, ignores magnitude
```

| keyword | cosine | pair |
|---------|--------|------|
| 0.00 | **0.71** | "How do I get my money back?" / "What is the refund process?" |
| 0.00 | **0.71** | "My laptop will not switch on" / "The computer refuses to boot" |
| 0.11 | **0.72** | "Where is my package?" / "I need to track my delivery" |

Zero shared words, high similarity. That is the whole product: a user asking
*"my laptop will not switch on"* finds an article titled *"computer refuses to
boot"*, which no `LIKE '%laptop%'` will ever return.

## Three failures, all in the same table

**1. There is no absolute threshold.**

```
0.48   "Where is my package?" / "The capital of France is Paris"
```

Completely unrelated text scores 0.48. The floor is high, and it moves with the
model. So **rank, never threshold** - "top 5 nearest" is meaningful, "everything
above 0.5" is not portable between models.

**2. Negation is invisible.**

| keyword | cosine | pair |
|---------|--------|------|
| 0.67 | 0.69 | "I love this product" / "I do **not** love this product" |
| 0.80 | 0.78 | "The order was delivered" / "The order was **never** delivered" |

Scores as high as the genuine matches above, with opposite meanings. Embeddings
capture *topic*, not truth value. Never route a refund on cosine alone.

**3. Identifiers are the worst case.**

```
0.91   "SR-1005" / "SR-1003"
```

The **highest score in the whole table**, for two different orders belonging to
different customers. They are near-identical *strings*, so they are near-identical
*points*. Exact lookup is the one job embeddings are worst at - and `LIKE` does it
perfectly.

> Semantic search finds things that MEAN the same. Keyword search finds things
> that ARE the same. Production systems need both.

That is hybrid search, and it is `08_rag`.

## Searching a corpus (3_search.py)

No database. A list of vectors and `cosine()` is genuinely enough for a few
thousand chunks - a vector DB buys an approximate index, persistence and metadata
filters. Scale and ops, not correctness.

Retrieval works, and keyword search would not have:

| query | top hit |
|-------|---------|
| "my parcel has not shown up yet" | *"follow your shipment from the Orders page..."* |
| "how do I get my money back" | *"Refunds are processed to the original payment method..."* |
| "I forgot my login details" | *"To reset your password, use the Forgot Password link..."* |

Not one shared keyword in any of those. Right document at rank 1 every time.

## Then ask it something the docs cannot answer

```
0.699  "can I change my delivery address after ordering"
       -> "Orders can only be cancelled while they are still being prepared..."
0.692  "how many days do I have to return an item"
       -> "Refunds are processed to the original payment method..."
0.656  "do you deliver to Nepal"
       -> "Standard delivery takes 3-5 working days within India..."
```

Every one of those sounds like something this help centre covers. **None is
answered by any document in the corpus.** And the scores:

```
answerable      floor  0.619
NOT answerable  ceiling 0.699   <- higher
```

The ranges overlap, so **no cosine threshold separates them.** Cut at 0.60 and
four unanswerable questions get through; cut at 0.70 and almost every real
question is rejected.

Note that "capital of France" scored 0.500 and was easy to reject. The dangerous
queries are not the absurd ones - they are the **adjacent** ones, which is
exactly what real users ask.

Feed those three hits to an LLM and it will answer confidently about a
cancellation policy when the user asked about changing an address.

> Retrieval does not tell you whether it found the answer. It tells you what was
> nearest.

Fourth appearance of the same root cause: `"required": ["customer"]` inventing
`"Alice"`, *"never answer without tracking data"* looping forever, `"hi"`
classified as `account`, and now top-k with nothing relevant to return.
**Forced choice produces confident garbage.**

The fixes are not a threshold: a reranker (a model that scores
query-vs-document directly), or an explicit *"answer only from the context below;
if it is not there, say so"* - and then measuring how often it actually says so.
That is `08_rag` and `09_evals`.

## Batch, or burn your rate limit

The first version of this file called `embed()` twice per query - once to print,
once to score. 20 API calls, ~70 seconds, most of it rate-limit sleep.

```python
QUERY_VECS = embed([q for q, _ in QUERIES])   # ONE call
hits = rank(qv)                               # pure arithmetic, free
```

2 calls, 5.3 seconds. Separating "embed" from "rank" is not a micro-optimisation
- the embedding is the only part that costs anything, and it is the only part
you can cache.

## Chunking (4_chunking.py)

One document, one embedding model, five queries. **Only the split changes.**

| strategy | n | avg | r@1 | r@3 | ctx@3 | spread |
|----------|---|-----|-----|-----|-------|--------|
| A whole document | 1 | 791 | 5/5 | 5/5 | 791 | 0.000 |
| B fixed 220, no overlap | 4 | 197 | 3/5 | 5/5 | 588 | 0.114 |
| C fixed 220, 60 overlap | 5 | 206 | 2/5 | 5/5 | 604 | 0.123 |
| **D split on sections** | 7 | 111 | 3/5 | 5/5 | **313** | **0.165** |
| E sections + title prefix | 6 | 155 | 3/5 | 5/5 | 470 | 0.102 |

`r@k` = correct chunk in the top k. `ctx@3` = characters sent to the LLM.
`spread` = best score minus worst, i.e. how *distinguishable* the chunks are.

### A's perfect score is a trap

One chunk means it always "retrieves" it - r@1 is meaningless at n=1. Read
`ctx@3`: it ships the entire document on every query. **Recall is free when
precision is zero.** Whenever a retrieval metric looks perfect, check what it
would have had to *not* return.

### Chunking is not deciding whether you find it

Every strategy scores r@3 = 5/5. Not one scores r@1 = 5/5. So on this corpus the
split is not changing *whether* the answer is retrievable - it changes **how much
junk rides along**: 313 chars for D against 791 for A, for the same answers.

*Caveat: this document is 791 chars in 6 sections, so everything lands in the top
3 trivially. Across thousands of chunks r@3 is where strategies separate. What
generalises here is the shape of the metrics, not the numbers.*

### Top-1 is a coin flip

Nothing reaches r@1 = 5/5. Two examples of why:

```
"how much does shipping cost"  -> 0.653 "Shipping and Returns Policy"   <- the TITLE
                                  0.649 "Delivery charges. ... Rs 99 ..."  <- the answer
"do you ship outside India"    -> 0.681 "Delivery charges. ... free anywhere in India"
                                  0.681 "International. We ship to 40 countries..."
```

The first is an **orphan fragment**: a bare heading with no information, winning
on topical density because it is short. The second is an exact **tie** decided by
sort order. Neither is fixable by tuning the chunker.

> This is why RAG retrieves top-k, not top-1, and why rerankers exist.

### The repair that backfired

E was supposed to fix D: drop fragments under 40 chars (killing the orphan title)
and prefix the document title to every chunk so each one stands alone. Result:

- recall: **unchanged**
- context: **worse** (470 vs 313)
- spread: **collapsed** 0.165 -> 0.102

Every chunk now begins with the same 27 characters, so every chunk moved toward
the same point. **Context helps a chunk stand alone; identical context makes
chunks identical.** Contextual prefixing is a real technique - but the prefix has
to be *specific to the chunk* (its section, its parent heading), never a constant.

Which is the actual lesson of the file: this was a hypothesis that measurement
killed. Same as the `06_agents` system prompt that turned out not to be
load-bearing. Chunking advice is everywhere and almost none of it is measured -
`09_evals` is how you stop guessing.
