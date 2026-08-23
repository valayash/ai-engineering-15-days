import sys
from llm_raw import chat

SYSTEM = "You are a terse assistant. Reply in one short sentence."

resp = chat([
    {"role": "system", "content": SYSTEM},
    {"role": "user",   "content": sys.argv[1]},
])

print(resp["choices"][0]["message"]["content"])
