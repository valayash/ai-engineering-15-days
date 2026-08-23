import sys
from llm import client, MODEL

SYSTEM = "You are a terse assistant. Reply in one short sentence."

resp = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM},      # standing rules
        {"role": "user",   "content": sys.argv[1]},  # this turn
    ],
)

print(resp.choices[0].message.content)
