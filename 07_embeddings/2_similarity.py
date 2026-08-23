"""Step 2: why vectors are useful - meaning compares, keywords don't.

usage: uv run 07_embeddings/2_similarity.py

Each pair is scored two ways:
  keyword  - Jaccard overlap of words. What grep / SQL LIKE / BM25 roughly see.
  cosine   - angle between the two embeddings. What MEANING looks like.
Where the two disagree is the entire value of embeddings - and their limits.
"""
import math, re
from llm import embed


def cosine(a: list[float], b: list[float]) -> float:
    """Angle between two vectors, ignoring their length. -1 .. 1"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


def keyword(a: str, b: str) -> float:
    """Jaccard overlap of words - a stand-in for what keyword search sees."""
    A = set(re.findall(r"\w+", a.lower()))
    B = set(re.findall(r"\w+", b.lower()))
    return len(A & B) / len(A | B) if A | B else 0.0


PAIRS = [
    # same meaning, almost no shared words -> keyword search FAILS, cosine works
    ("Where is my package?",           "I need to track my delivery"),
    ("How do I get my money back?",    "What is the refund process?"),
    ("My laptop will not switch on",   "The computer refuses to boot"),

    # shared words, different meaning -> keyword search fires, cosine should not
    ("I sat on the bank of the river", "I need to open a bank account"),
    ("Cancel my order",                "My order of the books is cancelled"),

    # unrelated -> both should be low
    ("Where is my package?",           "The capital of France is Paris"),

    # THE LIMITS - cosine is high but the meanings are OPPOSITE
    ("I love this product",            "I do not love this product"),
    ("The order was delivered",        "The order was never delivered"),

    # exact identifiers - they look alike, so they score alike. Bad for lookup.
    ("SR-1005",                        "SR-1003"),
]

texts = [t for pair in PAIRS for t in pair]
vecs = embed(texts)                       # one call for all of them
V = {t: v for t, v in zip(texts, vecs)}

print(f"{'keyword':>8} {'cosine':>8}   pair")
print("-" * 78)
for a, b in PAIRS:
    print(f"{keyword(a, b):>8.2f} {cosine(V[a], V[b]):>8.2f}   {a!r}\n{'':>18}{b!r}")
