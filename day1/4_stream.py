import sys, time
from llm import client, MODEL

stream = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": sys.argv[1]}],
    stream=True,                       # <-- the only change
)

t0 = time.time()
first = None

for chunk in stream:
    if not chunk.choices:
        continue
    piece = chunk.choices[0].delta.content    # "delta" = only what's NEW
    if piece:
        if first is None:
            first = time.time() - t0
        print(piece, end="", flush=True)

print(f"\n\n[first token after {first:.2f}s, done at {time.time()-t0:.2f}s]")
