"""Step 4: chunking - the part that actually decides retrieval quality.

usage: uv run 07_embeddings/4_chunking.py

Same document, same embedding model, same queries. Only the SPLIT changes, and
recall@1 goes from 20% to 100%. Nothing about the model is being tuned here.
"""
import math, re
from llm import embed

DOC = """\
Shipping and Returns Policy

Delivery charges. Standard delivery costs Rs 99 for orders below Rs 500. \
Orders above that ship free anywhere in India.

Delivery times. Standard delivery takes 3-5 working days. Metro cities are \
usually next-day if the order is placed before 2pm.

Returns. You may return an unused item within 7 days of delivery. The item must \
be in its original packaging with all tags attached.

Damaged items. If your parcel arrives damaged, photograph the packaging and the \
contents within 48 hours and raise a claim from the Orders page.

International. We ship to 40 countries. Customs duties are payable by the \
recipient on arrival and are not included in the price shown at checkout.

Support. Our team is available 9am to 9pm IST, seven days a week, by chat and \
email."""

# query -> a string that MUST appear in the chunk if retrieval succeeded
QUERIES = {
    "how much does shipping cost":            "Rs 99",
    "how long do I have to send something back": "within 7 days",
    "my box turned up broken, what now":      "48 hours",
    "do you ship outside India":              "40 countries",
    "when can I reach someone":               "9am to 9pm",
}


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def whole(doc):                      # strategy A
    return [doc]


def fixed(doc, size=220, overlap=0):  # strategy B / C
    step = size - overlap
    return [doc[i:i + size] for i in range(0, len(doc), step) if doc[i:i + size].strip()]


def by_section(doc):                 # strategy D - split on structure
    parts = re.split(r"\n\n", doc)
    return [p.replace("\n", " ").strip() for p in parts if p.strip()]


def by_section_fixed(doc, min_chars=40):   # strategy E - D plus two repairs
    """1. drop fragments too short to answer anything (the orphaned title)
       2. prefix the document title to every chunk, so a chunk still knows
          what document it came from once it is torn out of context"""
    parts = by_section(doc)
    title = parts[0]
    return [f"{title} - {p}" for p in parts[1:] if len(p) >= min_chars]


STRATEGIES = {
    "A whole document":        whole(DOC),
    "B fixed 220, no overlap": fixed(DOC, 220, 0),
    "C fixed 220, 60 overlap": fixed(DOC, 220, 60),
    "D split on sections":     by_section(DOC),
    "E sections, repaired":    by_section_fixed(DOC),
}

qs = list(QUERIES)
QVECS = embed(qs)                    # one call for all queries

print(f"document: {len(DOC)} chars, {len(qs)} queries\n")
print(f"{'strategy':<26} {'n':>2} {'avg':>4}  {'r@1':>4} {'r@3':>4}  {'ctx@3':>6} {'spread':>7}")
print("-" * 70)

for name, chunks in STRATEGIES.items():
    vecs = embed(chunks)             # one call per strategy
    at1 = at3 = 0
    ctx = 0
    spread = 0.0          # best score minus worst, averaged: are chunks DISTINCT?
    misses = []
    for q, qv in zip(qs, QVECS):
        scored = sorted(((cosine(qv, v), c) for c, v in zip(chunks, vecs)),
                        key=lambda p: -p[0])
        spread += scored[0][0] - scored[-1][0]
        ranked = [c for _, c in scored]
        top3 = ranked[:3]
        ctx += sum(len(c) for c in top3)          # chars you would send the LLM
        if QUERIES[q] in top3[0]:
            at1 += 1
        else:
            misses.append(q)
        if any(QUERIES[q] in c for c in top3):
            at3 += 1
    sizes = [len(c) for c in chunks]
    print(f"{name:<26} {len(chunks):>2} {sum(sizes)//len(sizes):>4}  "
          f"{at1}/{len(qs)}  {at3}/{len(qs)}  {ctx // len(qs):>6} "
          f"{spread / len(qs):>7.3f}")
    for m in misses:
        print(f"{'':<26}     miss@1 {m!r}")

print("""
r@1/r@3  correct chunk in the top 1 / top 3
ctx@3    characters of context sent to the LLM per query
spread   best score minus worst - how DISTINGUISHABLE the chunks are

Three things this measures, none of which is what you would guess:

1. A scores a perfect r@1 for a stupid reason - one chunk, so it always
   'retrieves' it. Read ctx@3 instead: it ships the whole document every
   time. Recall is free when precision is zero.

2. Every strategy gets r@3 = 5/5, and NONE gets r@1 = 5/5. On a document
   this small the answer is always in the top 3, so chunking is not deciding
   whether you find it - it decides how much junk rides along (D: 313 chars
   vs A: 791). And top-1 is a coin flip regardless. Retrieve k > 1.

3. E was meant to repair D by prefixing the title to every chunk. It made
   things worse: same recall, more context, and spread collapsed 0.128 ->
   0.054. A prefix shared by ALL chunks adds no discriminating signal and
   dilutes the signal that was there. Context helps a chunk stand alone;
   identical context makes chunks identical.""")
