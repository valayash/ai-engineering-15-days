"""Attempt 1: ask for JSON in the prompt and hope."""
import json
from llm import ask

TEXT = """Hi, this is Priya Sharma. I ordered a pair of running shoes (order #SR-88213)
on 3rd August and they still haven't shown up. I paid Rs 4299. Honestly pretty annoyed
at this point - I need them before the weekend. Reach me at priya.s@example.com or 98765 43210."""

PROMPT = ("Extract details from this support email as JSON with keys: "
          "name, email, phone, order_id, amount_inr, category, urgency, sentiment.")

raw = ask([{"role": "system", "content": PROMPT},
           {"role": "user",   "content": TEXT}], temperature=0)

print("=== RAW MODEL OUTPUT ===")
print(repr(raw))

print("\n=== json.loads() ===")
try:
    print(json.loads(raw))
except json.JSONDecodeError as e:
    print("FAILED:", e)
