import sys, time
from llm_raw import stream

t0, first, text, done = time.time(), None, "", None

for chunk in stream([{"role": "user", "content": sys.argv[1]}]):
    if not chunk["choices"]:
        continue
    choice = chunk["choices"][0]

    piece = choice["delta"].get("content")
    if piece:
        first = first or time.time() - t0
        text += piece
        print(piece, end="", flush=True)

    if choice.get("finish_reason"):        # arrives on the LAST chunk only
        done = choice["finish_reason"]

print(f"\n\n[first={first:.2f}s total={time.time()-t0:.2f}s finish={done}]")
