"""Step 4: memories go stale - supersession on write, filter on read.

usage: uv run 10_memory/4_stale.py

2_extract.py can WRITE and 3_recall.py can READ. Neither can UPDATE or FORGET,
so a correction replaces nothing - it piles a second, contradictory memory on
top of the first, and both embed beautifully. That is 08_rag's superseded refund
policy (0.721 stale beat 0.710 current) pointed inward, and the fix is the same:
give memories metadata, then filter before you rank.

The store lives in memory, so data/memories.json is untouched and this re-runs.
"""
import json, math, pathlib, time
from typing import Literal
from pydantic import BaseModel, Field
from llm import ask, embed, parse

TODAY = time.strftime("%Y-%m-%d")
MEMS = json.loads((pathlib.Path(__file__).parent.parent / "data" / "memories.json")
                  .read_text())
for m in MEMS:
    m.setdefault("status", "current")   # 2_extract.py never wrote one - that IS the bug

# A later session. Priya is not correcting a mistake; the world changed. The
# office memory was never wrong - it just stopped being true.
SAID = ("I've moved teams and work from home now - send everything to my flat "
        "in Koramangala from now on.")
NEW = "Priya Sharma wants deliveries sent to her flat in Koramangala"  # 2_extract's job
QUERY = "Hi, it's Priya again. Where should my order be delivered?"

new_vec, qvec = embed([NEW, QUERY])      # one call for both - batching, as always


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def recall(store, k: int = 3):
    """Filter FIRST, then rank - 08_rag/3_grounded.py, unchanged. Both paths
    below call THIS function: with no `status` metadata the filter removes
    nothing. A read path is only as good as what the write path recorded."""
    pool = [m for m in store if m["status"] == "current"]
    return sorted(((cosine(qvec, m["vector"]), m) for m in pool), key=lambda p: -p[0])[:k]


SYSTEM = ("You are the personal shopping assistant for Swift Retail. "
          "Be brief and warm.\n\n"
          "Facts on file about this user, saved from previous sessions:\n{facts}")


def answer(hits) -> str:
    # 3_recall.py's escape hatch ("what the user says NOW wins") cannot save us:
    # the correction arrived last week, not in this turn. There is nothing in
    # this conversation for the model to prefer.
    facts = "\n".join(f"- {m['fact']} (saved {m['created']})" for _, m in hits)
    return ask([{"role": "system", "content": SYSTEM.format(facts=facts)},
                {"role": "user", "content": QUERY}]).strip()


record = {"fact": NEW, "kind": "instruction", "created": TODAY,
          "status": "current", "vector": new_vec}

# --- 1. naive append: store the new fact, check nothing --------------------
print(f"===== 1. NAIVE APPEND =====\nPriya says: {SAID}\n")
naive = [dict(m) for m in MEMS] + [record]
naive_hits = recall(naive)
for s, m in naive_hits:
    print(f"  {s:.3f}  {m['fact']}")
naive_reply = answer(naive_hits)
print(f"\nUSER: {QUERY}\nBOT : {naive_reply}")

# --- 2. the fix, part one: supersession ON WRITE ---------------------------
# Before storing, ask what the new fact does to each existing one: one call
# grades all of them (4_rerank.py's shape), and `Literal` makes an invalid
# verdict impossible rather than discouraged.


class Verdict(BaseModel):
    id: int
    relation: Literal["CONTRADICTS", "UPDATES", "INDEPENDENT"] = Field(
        description="How the NEW fact relates to this stored one. CONTRADICTS: "
                    "they cannot both be true. UPDATES: same subject, newer "
                    "value. INDEPENDENT: about something else entirely.")


class Review(BaseModel):
    verdicts: list[Verdict]


listing = "\n".join(f"[{i}] {m['fact']}" for i, m in enumerate(MEMS))
review = parse([{"role": "system", "content":
                 "Compare a new memory against each stored memory. Most stored "
                 "memories are INDEPENDENT; say so rather than forcing a link."},
                {"role": "user", "content":
                 f"NEW memory: {NEW}\n\nStored memories:\n{listing}"}],
               Review, temperature=0)

print("\n===== 2. SUPERSESSION ON WRITE =====")
fixed = [dict(m) for m in MEMS]
for v in review.verdicts:
    if not 0 <= v.id < len(fixed):
        continue
    print(f"  {v.relation:<12} [{v.id}] {fixed[v.id]['fact']}")
    if v.relation in ("CONTRADICTS", "UPDATES"):
        # Marked, never deleted: the audit trail is why "we shipped to your old
        # office in March" stays answerable a year from now.
        fixed[v.id].update(status="superseded", superseded_by=NEW,
                           superseded_on=TODAY)
fixed.append(record)

# --- 3. the fix, part two: filter before ranking ON READ -------------------
print("\n===== 3. RECALL OVER status == 'current' =====")
fixed_hits = recall(fixed)
for s, m in fixed_hits:
    print(f"  {s:.3f}  {m['fact']}")
fixed_reply = answer(fixed_hits)
print(f"\nUSER: {QUERY}\nBOT : {fixed_reply}")

# --- 4. before / after -----------------------------------------------------
places = lambda text: " + ".join(p for p in ("Indiranagar", "Koramangala")
                                 if p in text) or "-"

print("\n===== 4. BEFORE / AFTER =====")
print(f"  {'path':<14} {'pool':<6} {'recalled':<26} {'answer says'}")
for label, store, hits, reply in [("naive append", naive, naive_hits, naive_reply),
                                  ("superseded", fixed, fixed_hits, fixed_reply)]:
    pool = sum(1 for m in store if m["status"] == "current")
    facts = " ".join(m["fact"] for _, m in hits)
    print(f"  {label:<14} {pool:<6} {places(facts):<26} {places(reply)}")

# FORGET is a different problem: no supersession check will ever fire on the
# anniversary, because nothing contradicts it. This file builds only the first
# of the two mechanisms.
print("\nnote: the 14 November anniversary is superseded by nothing - it just "
      "expires.\n      Expiry is a second mechanism, not this one.")
