"""Step 3: the read path - recall is semantic search over your own past.

usage: uv run 10_memory/3_recall.py ["your message"]

The machinery is 07/08 pointed inward: embed the incoming message, rank stored
memories against it, inject the relevant ones into the system prompt. Then the
"same" assistant from 1_goldfish.py suddenly remembers Tuesday what it was told
Monday - because WE remembered, and put it back in the prompt.
"""
import json, math, pathlib, sys
from llm import ask, embed

MEMS = json.loads((pathlib.Path(__file__).parent.parent / "data" / "memories.json")
                  .read_text())


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def recall(query_vec, k: int = 3):
    scored = [(cosine(query_vec, m["vector"]), m) for m in MEMS]
    return sorted(scored, key=lambda p: -p[0])[:k]


SYSTEM = ("You are the personal shopping assistant for Swift Retail. "
          "Be brief and warm.\n\n"
          "Facts on file about this user, saved from previous sessions:\n{facts}\n\n"
          "Use them when relevant; don't recite them unprompted. If the user "
          "says something that contradicts a fact on file, what the user says "
          "NOW wins.")

QUERIES = ["Hi, it's Priya again. Where should my order be delivered?",
           "Can you suggest snacks for my movie night?",
           "What should I do in November?"]
if len(sys.argv) > 1:
    QUERIES = [sys.argv[1]]

qvecs = embed(QUERIES)                       # one call, as always

print("what recall RANKS for each message (score | memory):")
for q, qv in zip(QUERIES, qvecs):
    print(f"\n  \"{q}\"")
    for s, m in recall(qv):
        print(f"    {s:.3f}  {m['fact']}")

# Now the actual conversation - goldfish session 2, but with recall wired in.
q, qv = QUERIES[0], qvecs[0]
facts = "\n".join(f"- {m['fact']} (saved {m['created']})" for _, m in recall(qv))
reply = ask([{"role": "system", "content": SYSTEM.format(facts=facts)},
             {"role": "user", "content": q}])
print(f"\n===== SESSION 2, with memory =====\nUSER: {q}\nBOT : {reply.strip()[:300]}")
