"""Step 2: the write path - extracting what deserves to be remembered.

usage: uv run 10_memory/2_extract.py

Memory is not "store the transcript". A transcript is a log; memory is the
DECISION about what in it will still matter next month. That decision is a
model call with a schema (04_structured_output doing real work again).

Writes data/memories.json - facts + embeddings, ready for recall.
"""
import json, pathlib, time
from typing import Literal
from pydantic import BaseModel, Field
from llm import parse, embed

# In a real system this runs on the live transcript when a session ends.
# Canned here so the file is deterministic and cheap to re-run. Note the noise
# turns - a good extractor must IGNORE most of the conversation.
TRANSCRIPT = """\
USER: Hi! I'm Priya Sharma. Please remember: I'm vegetarian, I prefer refunds \
over store credit, and deliveries go to my OFFICE in Indiranagar, Bengaluru - \
never to my home.
BOT: Noted, Priya! Vegetarian, refunds over store credit, office deliveries.
USER: Also my wedding anniversary is 14 November - closer to the date, remind \
me to order a gift.
BOT: Got it - I'll help you pick something nice in November.
USER: ugh, it's so hot today
BOT: Bengaluru summers! Can I help you find a fan or a cooler?
USER: ha, no thanks. actually while I'm here - is the yoga mat SR-1002 refunded yet?
BOT: Let me check on that for you.
USER: never mind, I'll check tomorrow. bye!
BOT: Take care, Priya!"""


class Memory(BaseModel):
    fact: str = Field(description=(
        "One durable fact, self-contained and in third person - it will be read "
        "months from now with NO other context. 'Priya prefers refunds', never "
        "'I prefer refunds' or 'she said yes to that'."))
    kind: Literal["identity", "preference", "instruction", "event"]


class Extraction(BaseModel):
    memories: list[Memory]


SYSTEM = ("Extract facts worth remembering across future sessions. "
          "Durable only: who the user is, standing preferences, standing "
          "instructions, dated events. NOT small talk, NOT one-off requests "
          "already handled, NOT the assistant's replies. Convert relative "
          "dates to absolute. Fewer, better memories beat many noisy ones.")

result = parse([{"role": "system", "content": SYSTEM},
                {"role": "user", "content": TRANSCRIPT}],
               Extraction, temperature=0)

print(f"{len(result.memories)} memories from a {len(TRANSCRIPT.splitlines())}-line transcript:\n")
for m in result.memories:
    print(f"  [{m.kind:<11}] {m.fact}")

# Store facts WITH their vectors - recall (step 3) is semantic search over
# your own past, which is 07/08 machinery pointed inward.
vecs = embed([m.fact for m in result.memories])
OUT = pathlib.Path(__file__).parent.parent / "data" / "memories.json"
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps([
    {"fact": m.fact, "kind": m.kind,
     "created": time.strftime("%Y-%m-%d"), "vector": v}
    for m, v in zip(result.memories, vecs)]))
print(f"\nstored with embeddings -> {OUT}")
