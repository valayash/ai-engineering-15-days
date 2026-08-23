import sys
from llm_raw import chat

resp = chat([{"role": "user", "content": sys.argv[1]}])

print(resp["choices"][0]["message"]["content"])
print("---")
print("tokens in :", resp["usage"]["prompt_tokens"])
print("tokens out:", resp["usage"]["completion_tokens"])
print("stopped   :", resp["choices"][0]["finish_reason"])
