"""Summarize old turns instead of throwing them away."""
from llm import client, MODEL

SYSTEM = "You are a helpful assistant. Keep replies to one short sentence."
KEEP = 2          # recent messages kept word-for-word
TRIGGER = 4       # summarize once history grows past this

recent, summary = [], ""


def summarize(old, previous):
    """Fold old messages into the running summary. Costs one extra API call."""
    text = "\n".join(f"{m['role']}: {m['content']}" for m in old)
    prompt = (f"Running summary so far:\n{previous or '(none)'}\n\n"
              f"New messages to fold in:\n{text}\n\n"
              "Rewrite the summary. Keep every fact about the user. Two sentences max.")
    return client.chat.completions.create(
        model=MODEL, messages=[{"role": "user", "content": prompt}]
    ).choices[0].message.content.strip()


while True:
    try:
        msg = input("\nyou: ")
    except EOFError:
        break
    if msg in ("quit", "exit"):
        break

    recent.append({"role": "user", "content": msg})

    if len(recent) > TRIGGER:                      # compress the oldest, keep the newest
        old, recent = recent[:-KEEP], recent[-KEEP:]
        summary = summarize(old, summary)
        print(f"     [compressed {len(old)} msgs -> summary: {summary}]")

    system = SYSTEM + (f"\n\nWhat you know so far:\n{summary}" if summary else "")
    sent = [{"role": "system", "content": system}] + recent

    resp = client.chat.completions.create(model=MODEL, messages=sent)
    reply = resp.choices[0].message.content

    recent.append({"role": "assistant", "content": reply})

    print("bot:", reply)
    print(f"     [sent={len(sent)} msgs / {resp.usage.prompt_tokens} tokens]")
