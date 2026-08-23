"""Step 3: metadata + filter-then-rank + citations.

usage: uv run 08_rag/3_grounded.py

Same questions that broke in 2_hard.py. The retriever is unchanged - what
changes is that chunks now carry metadata, so we can EXCLUDE before we RANK.
"""
import math
from llm import ask, embed
from kb import CHUNKS, vectors

VECS = vectors()


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def retrieve(query: str, k: int = 3, where=None):
    """Filter FIRST, then rank.

    Ranking first and filtering after is the common bug: you ask for 3, two are
    superseded, you hand the model one chunk and never notice. Filtering first
    means k always means k.
    """
    pool = [(c, v) for c, v in zip(CHUNKS, VECS) if where is None or where(c)]
    qv = embed(query)[0]
    scored = [(cosine(qv, v), c) for c, v in pool]
    return sorted(scored, key=lambda p: -p[0])[:k]


# Two things this prompt does that the naive one did not:
#   1. numbers each source so a claim can point at one
#   2. tells the model what to do when the context does not answer the question
PROMPT = """Answer the customer's question using ONLY the sources below.

After each claim, cite the source id it came from, like [REF-01].
If the sources do not answer the question, say exactly:
"I don't have that information." Do not use knowledge from outside the sources.

Sources:
{sources}

Question: {question}"""


def answer(query: str, k: int = 3, where=None):
    hits = retrieve(query, k, where)
    sources = "\n".join(f"[{c.id}] {c.text}" for _, c in hits)
    reply = ask([{"role": "user",
                  "content": PROMPT.format(sources=sources, question=query)}])
    return reply, hits


CURRENT_POLICY = lambda c: c.status == "current" and c.authority == "policy"

QUESTIONS = [
    ("how long do refunds take",                    "5-7 business days"),
    ("how many days do I have to return something", "7 days"),
    ("how much is delivery",                        "Rs 99"),
    ("can I change my delivery address",            "NOT IN CORPUS"),
]

for q, truth in QUESTIONS:
    print(f"\n{'=' * 78}\nQ: {q}\n   expected: {truth}")

    for label, where in [("no filter (2_hard behaviour)", None),
                         ("status=current AND authority=policy", CURRENT_POLICY)]:
        reply, hits = answer(q, where=where)
        print(f"\n  --- {label} ---")
        for s, c in hits:
            flag = "" if c.status == "current" and c.authority == "policy" \
                   else f"  <-- {c.status}/{c.authority}"
            print(f"      {s:.3f} [{c.id}] {c.text[:52]}...{flag}")
        print(f"      -> {reply.strip()[:200]}")
