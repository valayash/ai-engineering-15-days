import sys
from llm import client, MODEL

resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": sys.argv[1]}],
)

print(resp.choices[0].message.content)
print("---")
print("tokens in :", resp.usage.prompt_tokens)
print("tokens out:", resp.usage.completion_tokens)
print("stopped   :", resp.choices[0].finish_reason)
