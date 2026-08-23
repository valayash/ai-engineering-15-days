"""Prompt engineering, measured. Same task, three prompts, one score."""
from llm import ask

# ground truth: the whole point. you cannot improve what you cannot score.
CASES = [
    ("My order hasn't arrived and it's been two weeks", "shipping"),
    ("I was charged twice for the same order",          "billing"),
    ("How do I reset my password?",                     "account"),
    ("The app crashes when I open my cart",             "bug"),
    ("Do you ship to Canada?",                          "shipping"),
    ("I want a refund for order 8821",                  "billing"),
]

PROMPTS = {
    "v1 naive": "Classify this support ticket.",

    "v2 constrained":
        "Classify the support ticket into exactly one of: shipping, billing, account, bug.\n"
        "Reply with only the category word in lowercase. No punctuation, no explanation.",

    "v3 few-shot":
        "Classify the support ticket into exactly one of: shipping, billing, account, bug.\n"
        "Reply with only the category word in lowercase. No punctuation, no explanation.\n\n"
        "Examples:\n"
        "'Where is my package?' -> shipping\n"
        "'My card was declined' -> billing\n"
        "'I can't log in' -> account\n"
        "'The page is blank on Safari' -> bug",
}


def classify(system, ticket):
    return ask(
        [{"role": "system", "content": system},
         {"role": "user",   "content": ticket}],
        temperature=0,                       # deterministic: we're measuring the PROMPT
    ).strip().lower()


for name, system in PROMPTS.items():
    print(f"\n=== {name} ===")
    hits = 0
    for ticket, want in CASES:
        got = classify(system, ticket)
        ok = got == want
        hits += ok
        print(f"  {'PASS' if ok else 'FAIL'}  want={want:9} got={got[:45]!r}")
    print(f"  SCORE: {hits}/{len(CASES)}")
