from llm_raw import chat

SYSTEM = "You are a helpful assistant. Keep replies to one or two sentences."

messages = [{"role": "system", "content": SYSTEM}]

while True:
    msg = input("\nyou: ")
    if msg in ("quit", "exit"):
        break

    messages.append({"role": "user", "content": msg})

    resp = chat(messages)
    reply = resp["choices"][0]["message"]["content"]

    messages.append({"role": "assistant", "content": reply})

    print("bot:", reply)
    print(f"     [turns={len(messages)}  sent={resp['usage']['prompt_tokens']} tokens]")
