"""Step 1: RAG, written the way everyone writes it first.

usage: uv run 08_rag/1_naive.py ["your question"]

    retrieve top-k  ->  paste into the prompt  ->  ask the model

That is the whole of RAG. There is no magic step. The interesting part is what
it does when retrieval brings back nothing useful - which it cannot tell you.
"""
import math, sys
from llm import ask, embed
from corpus import DOCS, vectors

DOC_VECS = vectors()


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def retrieve(query: str, k: int = 3) -> list[tuple[float, str]]:
    qv = embed(query)[0]
    scored = [(cosine(qv, dv), d) for dv, d in zip(DOC_VECS, DOCS)]
    return sorted(scored, key=lambda p: -p[0])[:k]


# The naive prompt. Note what is NOT in it: any permission to say "I don't know".
PROMPT = """Answer the customer's question using the context below.

Context:
{context}

Question: {question}"""


def answer(query: str, k: int = 3) -> tuple[str, list]:
    hits = retrieve(query, k)
    context = "\n".join(f"- {d}" for _, d in hits)
    reply = ask([{"role": "user",
                  "content": PROMPT.format(context=context, question=query)}])
    return reply, hits


# (question, is it answerable from the corpus?)
QUESTIONS = [
    ("how much does delivery cost",                    True),
    ("what does error E-402 mean",                     True),
    ("can I change my delivery address after ordering", False),
    ("what does error E-500 mean",                     False),
    ("do you deliver to Nepal",                        False),
]

if len(sys.argv) > 1:
    QUESTIONS = [(sys.argv[1], None)]

for q, answerable in QUESTIONS:
    reply, hits = answer(q)
    tag = {True: "ANSWERABLE", False: "NOT IN CORPUS", None: ""}[answerable]
    print(f"\n{'=' * 74}\nQ: {q}   [{tag}]")
    for s, d in hits:
        print(f"   retrieved {s:.3f}  {d[:60]}...")
    print(f"\nA: {reply.strip()}")
