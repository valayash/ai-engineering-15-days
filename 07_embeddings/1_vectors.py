"""Step 1: what an embedding actually IS.

usage: uv run 07_embeddings/1_vectors.py ["your text"]

Everything so far sent text to a model and got text back. This is a different
endpoint: text goes in, a list of numbers comes out. No prompt, no sampling.
"""
import sys
from llm import embed, EMBED_MODEL

DEFAULT = "Where is my order?"
text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT

v = embed(text)[0]

print(f"model : {EMBED_MODEL}")
print(f"text  : {text!r}")
print(f"type  : {type(v).__name__} of {type(v[0]).__name__}")
print(f"dims  : {len(v)}")
print(f"first8: {[round(x, 4) for x in v[:8]]}")

# A vector's LENGTH is fixed by the model, not by the input. One word and one
# paragraph both become the same number of floats. That is the whole trick:
# every text is squashed into one fixed-size point, so any two texts are
# comparable with plain arithmetic.
print("\n--- size does not depend on input length ---")
for t in ["hi", "Where is my order?", "Where is my order? " * 50]:
    n = len(embed(t)[0])
    print(f"  {len(t):>5} chars -> {n} dims   {t[:38]!r}")

# Unlike chat(), this is deterministic - no temperature, nothing to sample.
print("\n--- same input, same vector ---")
a, b = embed(DEFAULT)[0], embed(DEFAULT)[0]
print(f"  identical: {a == b}")
print(f"  max diff : {max(abs(x - y) for x, y in zip(a, b))}")

# Batch: one HTTP call for many texts. Matters a lot when you index a corpus.
print("\n--- batching ---")
vs = embed(["first", "second", "third"])
print(f"  3 texts in ONE call -> {len(vs)} vectors of {len(vs[0])} dims")
