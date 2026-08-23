"""Step 2: the same pipeline against a realistic corpus.

usage: uv run 08_rag/2_hard.py

1_naive.py works because its corpus is 16 clean, single-topic, non-contradictory
documents. Real knowledge bases are not that. Nothing here changes the code -
only four documents are added, of the kind every company accumulates:

  - a superseded policy nobody deleted
  - marketing copy that contradicts the docs
  - a page mentioning a code without defining it
  - a near-duplicate with different numbers
"""
import math
from llm import ask, embed
from corpus import DOCS, MESSY, vectors, messy_vectors


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


PROMPT = """Answer the customer's question using the context below.

Context:
{context}

Question: {question}"""


def run(query, docs, vecs, k=3):
    qv = embed(query)[0]
    hits = sorted(((cosine(qv, v), d) for d, v in zip(docs, vecs)),
                  key=lambda p: -p[0])[:k]
    ctx = "\n".join(f"- {d}" for _, d in hits)
    return ask([{"role": "user", "content": PROMPT.format(context=ctx, question=query)}]), hits


CLEAN_VECS, MESSY_VECS = vectors(), messy_vectors()

QUESTIONS = [
    ("how long do refunds take",        "5-7 business days"),
    ("how many days do I have to return something", "7 days"),
    ("how much is delivery",            "Rs 99"),
]

for q, truth in QUESTIONS:
    print(f"\n{'=' * 76}\nQ: {q}\n   ground truth: {truth}")
    for label, docs, vecs in [("CLEAN (16 docs)", DOCS, CLEAN_VECS),
                              ("MESSY (20 docs)", MESSY, MESSY_VECS)]:
        reply, hits = run(q, docs, vecs)
        print(f"\n  --- {label} ---")
        for s, d in hits:
            print(f"      {s:.3f} {d[:64]}...")
        print(f"      ANSWER: {reply.strip()[:230]}")
