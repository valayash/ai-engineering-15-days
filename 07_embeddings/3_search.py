"""Step 3: semantic search over a corpus - and what it does when it shouldn't.

usage: uv run 07_embeddings/3_search.py ["your question"]

This is the retrieval half of RAG. There is no database here on purpose: a list
of vectors plus cosine() is genuinely enough for a few thousand chunks. A vector
DB buys an approximate index, persistence and metadata filters - scale and ops,
not correctness.
"""
import math, sys
from llm import embed

# A tiny help centre. In a real system these are CHUNKS of longer documents.
DOCS = [
    "Refunds are processed to the original payment method within 5-7 business "
    "days after we receive the returned item.",
    "You can follow your shipment from the Orders page. Live courier updates "
    "appear once the parcel leaves our warehouse.",
    "Orders can only be cancelled while they are still being prepared. Once "
    "handed to the courier, cancellation is no longer possible.",
    "Standard delivery takes 3-5 working days within India. Metro cities are "
    "usually next-day.",
    "If your item arrives damaged, photograph the packaging and contents within "
    "48 hours and raise a claim from the Orders page.",
    "To reset your password, use the Forgot Password link on the sign-in screen. "
    "The reset link expires after 30 minutes.",
    "We accept UPI, all major credit and debit cards, net banking, and cash on "
    "delivery for orders under Rs 5000.",
    "International shipping is available to 40 countries. Customs duties are "
    "payable by the recipient on arrival.",
    "Bulk and corporate orders over 50 units qualify for tiered discounts. "
    "Contact the sales team for a quote.",
    "Support is available 9am to 9pm IST, seven days a week, by chat and email.",
]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


DOC_VECS = embed(DOCS)              # embed the corpus ONCE, one HTTP call


def rank(qv: list[float], k: int = 3):
    """Rank the corpus against an ALREADY-EMBEDDED query."""
    scored = [(cosine(qv, dv), d) for dv, d in zip(DOC_VECS, DOCS)]
    return sorted(scored, key=lambda p: -p[0])[:k]


def search(query: str, k: int = 3):
    return rank(embed(query)[0], k)


# (question, is it actually answerable from DOCS?)
QUERIES = [
    ("my parcel has not shown up yet",           True),   # no shared keywords
    ("how do I get my money back",               True),   # "refund" never said
    ("I forgot my login details",                True),
    ("can I still stop the shipment going out",  True),
    ("what is the capital of France",            False),  # nowhere near the corpus

    # The realistic failure: questions ADJACENT to the corpus. Every one of
    # these sounds like something this help centre would cover. None is answered
    # by any document above.
    ("can I change my delivery address after ordering", False),
    ("how many days do I have to return an item",       False),
    ("do you deliver to Nepal",                         False),
    ("what happens if nobody is home for the delivery", False),
]

if len(sys.argv) > 1:
    QUERIES = [(sys.argv[1], None)]

# Embed every query in ONE call, then rank locally. Calling embed() per query -
# and twice per query, as the first version of this file did - is the standard
# way to burn a rate limit for no reason. Ranking is pure arithmetic and free.
QUERY_VECS = embed([q for q, _ in QUERIES])

tops = []
for (q, answerable), qv in zip(QUERIES, QUERY_VECS):
    mark = {True: "in corpus ", False: "NOT in corpus", None: ""}[answerable]
    print(f"\nQ: {q!r}   {mark}")
    hits = rank(qv)
    for score, doc in hits:
        print(f"   {score:.3f}  {doc[:66]}...")
    tops.append((answerable, hits[0][0]))

if len(QUERIES) > 1:
    print("\n" + "-" * 70)
    print("top-1 score, by whether the answer is actually in the corpus:")
    for label, flag in [("answerable    ", True), ("NOT answerable", False)]:
        s = [x for a, x in tops if a is flag]
        print(f"  {label}: {[round(x, 3) for x in s]}   best={max(s):.3f}")
    lo_ok = min(x for a, x in tops if a is True)
    hi_no = max(x for a, x in tops if a is False)
    print(f"\nanswerable floor {lo_ok:.3f} vs unanswerable ceiling {hi_no:.3f} -> "
          f"{'OVERLAP: no threshold works' if hi_no >= lo_ok else 'separable, but on how many queries?'}")
