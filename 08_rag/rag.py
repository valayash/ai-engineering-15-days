"""The whole of 08, as one importable function. This is what you ship.

    from rag import answer
    r = answer("how much is delivery", chunks=CHUNKS, vectors=VECS)
    r.text, r.sources, r.refused

Nothing here is new - it is 1_naive through 4_rerank with the failures removed.
"""
import math
from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, Field
from llm import ask, embed, parse


@dataclass
class Answer:
    text: str
    sources: list = field(default_factory=list)   # chunks actually cited
    refused: bool = False                          # nothing relevant was found
    considered: int = 0                            # candidates before reranking


class _Judgement(BaseModel):
    id: str
    grade: Literal["answers", "related", "irrelevant"]


class _Ranking(BaseModel):
    judgements: list[_Judgement]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


PROMPT = """Answer the customer's question using ONLY the sources below.
After each claim, cite the source id, like [REF-01].

Sources:
{sources}

Question: {question}"""


def answer(question: str, *, chunks: list, vectors: list, where=None,
           n: int = 6, rerank: bool = True) -> Answer:
    """Filter -> retrieve wide -> rerank -> generate with citations.

    where:  predicate over a chunk. Excludes superseded/low-authority sources
            BEFORE ranking, so k always means k.
    n:      how wide the cheap vector net is cast before the costly rerank.
    rerank: False falls back to plain vector top-3 (cheaper, noisier, and it
            can never tell you it found nothing).
    """
    pool = [(c, v) for c, v in zip(chunks, vectors) if where is None or where(c)]
    if not pool:
        return Answer("I don't have that information.", refused=True)

    qv = embed(question)[0]
    hits = sorted(((cosine(qv, v), c) for c, v in pool), key=lambda p: -p[0])[:n]

    if not rerank:
        keep = [c for _, c in hits[:3]]
    else:
        listing = "\n".join(f"[{c.id}] {c.text}" for _, c in hits)
        graded = parse(
            [{"role": "system", "content":
              "Grade each document for whether it answers the question. Judge each "
              "on its own. Most documents are irrelevant; say so."},
             {"role": "user", "content": f"Question: {question}\n\nDocuments:\n{listing}"}],
            _Ranking, temperature=0)
        grades = {j.id: j.grade for j in graded.judgements}
        keep = [c for _, c in hits if grades.get(c.id) == "answers"]

    # An empty result is a real signal, not an error. Refuse without paying for
    # a generation call - cosine alone can never get you here.
    if not keep:
        return Answer("I don't have that information.", refused=True,
                      considered=len(hits))

    src = "\n".join(f"[{c.id}] {c.text}" for c in keep)
    text = ask([{"role": "user",
                 "content": PROMPT.format(sources=src, question=question)}])
    return Answer(text.strip(), sources=keep, considered=len(hits))


if __name__ == "__main__":
    import sys
    from kb import CHUNKS, vectors

    CURRENT_POLICY = lambda c: c.status == "current" and c.authority == "policy"
    q = sys.argv[1] if len(sys.argv) > 1 else "how much is delivery"

    r = answer(q, chunks=CHUNKS, vectors=vectors(), where=CURRENT_POLICY)
    print(f"Q: {q}\n")
    print(r.text)
    print(f"\n[{len(r.sources)} of {r.considered} candidates cited"
          f"{', REFUSED' if r.refused else ''}]")
    for c in r.sources:
        print(f"   {c.cite()}")
