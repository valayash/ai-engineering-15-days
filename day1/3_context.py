from llm import client, MODEL

SYSTEM = "You are a helpful assistant. Keep replies to one or two sentences."

messages = [{"role": "system", "content": SYSTEM}]   # <-- this list IS the memory

while True:
    msg = input("\nyou: ")
    if msg in ("quit", "exit"):
        break

    messages.append({"role": "user", "content": msg})

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,                            # send the WHOLE list, every time
    )
    reply = resp.choices[0].message.content

    messages.append({"role": "assistant", "content": reply})

    print("bot:", reply)
    print(f"     [turns={len(messages)}  sent={resp.usage.prompt_tokens} tokens]")
