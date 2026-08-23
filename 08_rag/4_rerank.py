"""Step 4: retrieve wide, then rerank narrow.

usage: uv run 08_rag/4_rerank.py

3_grounded.py always passes exactly k chunks. When only one is relevant, the
other two are noise that still costs tokens - and when NONE is relevant, cosine
cannot tell you, because top-k always returns k.

A reranker scores each candidate against the question DIRECTLY instead of by
vector distance. That is slower and better, so the shape is:

    vector search   cheap, imprecise  ->  cast a wide net (n=6)
    rerank          costly, precise   ->  keep what earns its place
"""
import math
from typing import Literal
from pydantic import BaseModel, Field
from llm import ask, embed, parse
from kb import CHUNKS, vectors

VECS = vectors()
CURRENT_POLICY = lambda c: c.status == "current" and c.authority == "policy"


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def retrieve(query: str, n: int, where=None):
    pool = [(c, v) for c, v in zip(CHUNKS, VECS) if where is None or where(c)]
    qv = embed(query)[0]
    return sorted(((cosine(qv, v), c) for c, v in pool), key=lambda p: -p[0])[:n]


# --- the reranker -----------------------------------------------------------
# One call scoring every candidate, not one call per candidate. The schema is
# 04_structured_output's machinery doing real work: `grade` is a Literal, so an
# invalid grade is not merely discouraged, it is impossible.

class Judgement(BaseModel):
    id: str
    grade: Literal["answers", "related", "irrelevant"] = Field(
        description="'answers' = contains the answer; 'related' = same topic but "
                    "does not answer it; 'irrelevant' = different topic")


class Ranking(BaseModel):
    judgements: list[Judgement]


def rerank(query: str, hits) -> dict[str, str]:
    listing = "\n".join(f"[{c.id}] {c.text}" for _, c in hits)
    r = parse([{"role": "system", "content":
                "Grade each document for whether it answers the question. Judge "
                "each one on its own. Most documents are irrelevant; say so."},
               {"role": "user", "content": f"Question: {query}\n\nDocuments:\n{listing}"}],
              Ranking, temperature=0)
    return {j.id: j.grade for j in r.judgements}


PROMPT = """Answer the customer's question using ONLY the sources below.
After each claim, cite the source id, like [REF-01].

Sources:
{sources}

Question: {question}"""


def generate(query, chunks) -> str:
    src = "\n".join(f"[{c.id}] {c.text}" for c in chunks)
    return ask([{"role": "user", "content": PROMPT.format(sources=src, question=query)}])


QUESTIONS = ["how much is delivery",
             "what does error E-419 mean",
             "can I change my delivery address"]

for q in QUESTIONS:
    print(f"\n{'=' * 78}\nQ: {q}")

    wide = retrieve(q, 6, CURRENT_POLICY)          # cheap wide net
    grades = rerank(q, wide)                        # one call, all candidates

    for s, c in wide:
        print(f"   {s:.3f} [{c.id:<8}] {grades.get(c.id, '?'):<11} {c.text[:44]}...")

    keep = [c for _, c in wide if grades.get(c.id) == "answers"]

    baseline = [c for _, c in wide[:3]]             # what 3_grounded would send
    print(f"\n   vector top-3 : {[c.id for c in baseline]}  "
          f"({sum(len(c.text) for c in baseline)} chars)")
    print(f"   after rerank : {[c.id for c in keep]}  "
          f"({sum(len(c.text) for c in keep)} chars)")

    # The payoff: an empty result is a real signal. Cosine can never produce one.
    if not keep:
        print("\n   -> nothing graded 'answers'. Refusing WITHOUT calling the model.")
        print("      I don't have that information.")
    else:
        print(f"\n   -> {generate(q, keep).strip()}")
