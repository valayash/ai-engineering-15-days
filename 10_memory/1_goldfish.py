"""Step 1: the agent promises memory it does not have.

usage: uv run 10_memory/1_goldfish.py

Two sessions with the same assistant. Watch what it SAYS in session 1 versus
what it KNOWS in session 2. Nothing here is a bug - the API is a stateless
function (01_basics), so "I'll remember that" is a hallucination about its own
abilities. The model has no way to know it won't be there next time.
"""
from llm import ask

SYSTEM = ("You are the personal shopping assistant for Swift Retail. "
          "Be brief and warm.")


def session(name: str, turns: list[str]) -> list[dict]:
    """A FRESH conversation - messages start empty every time, like real life:
    the user closed the tab, and came back tomorrow."""
    messages = [{"role": "system", "content": SYSTEM}]
    print(f"\n===== {name} =====")
    for t in turns:
        messages.append({"role": "user", "content": t})
        reply = ask(messages)
        messages.append({"role": "assistant", "content": reply})
        print(f"\nUSER: {t}")
        print(f"BOT : {reply.strip()[:260]}")
    return messages


session("SESSION 1 - Monday", [
    "Hi! I'm Priya Sharma. Please remember: I'm vegetarian, I prefer refunds "
    "over store credit, and deliveries go to my OFFICE in Indiranagar, "
    "Bengaluru - never to my home.",
    "Also my wedding anniversary is 14 November - closer to the date, remind "
    "me to order a gift.",
])

session("SESSION 2 - Tuesday", [
    "Hi, it's Priya again. Where should my order be delivered?",
])
