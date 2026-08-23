"""The problem: you resend the ENTIRE conversation every turn."""
from llm import client, MODEL


def est_tokens(messages):
    """~4 chars per token. Rough, but free and good enough for capacity planning."""
    return sum(len(m["content"]) for m in messages) // 4


messages = [{"role": "system", "content": "You are a helpful support agent. " * 10}]

billed = 0
for turn in range(1, 21):
    messages.append({"role": "user", "content": "Question about my order? " * 4})
    messages.append({"role": "assistant", "content": "Here is a detailed answer. " * 12})

    sent = est_tokens(messages)      # what THIS request costs you
    billed += sent                   # what you've paid across the whole chat

    if turn % 5 == 0:
        print(f"turn {turn:3}:  this request = {sent:6} tokens   |  billed so far = {billed:7}")

print(f"\nTurn 20 costs {est_tokens(messages) // est_tokens(messages[:3])}x what turn 1 did.")

# is that 4-chars-per-token guess any good? check against the real tokenizer.
# note: messages[:2] not [:3] - Gemini rejects a request ending on an assistant turn.
probe = messages[:2]
real = client.chat.completions.create(model=MODEL, messages=probe, max_tokens=1)
print(f"\nestimate={est_tokens(probe)}  actual={real.usage.prompt_tokens}")
