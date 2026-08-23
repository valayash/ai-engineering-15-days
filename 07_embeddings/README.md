# 07 - Embeddings

A different endpoint. `chat()` sends text and gets text; `embed()` sends text and
gets a fixed-length list of floats. No prompt, no sampling, no randomness.

| file | teaches |
|------|---------|
| `1_vectors.py` | what a vector is, fixed size, deterministic, batching |
| `2_similarity.py` | cosine vs keyword overlap - where they disagree |

```bash
uv run 07_embeddings/1_vectors.py
uv run 07_embeddings/2_similarity.py
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
