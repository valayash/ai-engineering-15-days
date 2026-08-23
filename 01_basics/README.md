# 01 - Basics

An LLM API is a **stateless function**. No memory, no learning at request time.
If the model knows something, it was in the training data or *you put it in the prompt*.

| file | teaches |
|------|---------|
| `1_simple.py` | one call; `usage` tokens; `finish_reason` |
| `2_system.py` | `system` vs `user` role |
| `3_context.py` | conversation memory = a list you resend every turn |
| `4_stream.py` | `stream=True`, deltas, time-to-first-token |
| `raw/` | the same four with plain `httpx` - no SDK |

```bash
uv run 01_basics/1_simple.py "Hello, tell me about yourself"
uv run 01_basics/3_context.py      # interactive
```

## Takeaways

- **It's just HTTP.** `POST {base_url}/chat/completions` with a JSON body.
  The SDK is a typed dict-getter with retries.
- **Roles:** `system` = rules you control. `user` = input the user controls
  (a trust boundary - see prompt injection later). `assistant` = what the model said.
  `tool` arrives in `05_tools`.
- **You write the `assistant` turns.** They don't have to be real - fabricated
  history is a legitimate prompting technique.
- **`finish_reason` matters.** `stop` = complete. `length` = truncated mid-sentence
  and the output *looks* fine. Never `json.loads()` without checking it.
- **Streaming** buys perceived speed (TTFT), and costs you the ability to validate
  before the user sees output. Stream prose; don't stream JSON or tool calls.
- Chunks are **not** tokens - servers batch. The final chunk carries
  `finish_reason` and no content, so `continue` on empty, never `break`.
