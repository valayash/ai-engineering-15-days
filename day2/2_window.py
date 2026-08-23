"""Sliding window: never send more than the last KEEP messages."""
from llm import client, MODEL

SYSTEM = "You are a helpful assistant. Keep replies to one short sentence."
KEEP = 4                      # remember the last 4 messages = 2 exchanges

messages = [{"role": "system", "content": SYSTEM}]


def window(msgs):
    """Always keep the system prompt; keep only the most recent KEEP turns."""
    return [msgs[0]] + msgs[1:][-KEEP:]


while True:
    try:
        msg = input("\nyou: ")
    except EOFError:
        break
    if msg in ("quit", "exit"):
        break

    messages.append({"role": "user", "content": msg})

    sent = window(messages)                      # <-- the only new line that matters
    resp = client.chat.completions.create(model=MODEL, messages=sent)
    reply = resp.choices[0].message.content

    messages.append({"role": "assistant", "content": reply})

    print("bot:", reply)
    print(f"     [history={len(messages)} msgs | sent={len(sent)} msgs / "
          f"{resp.usage.prompt_tokens} tokens]")
