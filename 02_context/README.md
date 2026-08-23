# 02 - Context management

You resend the **entire** conversation every turn. So cost per request grows
linearly, and cost across a conversation grows **quadratically**.

| file | teaches |
|------|---------|
| `1_problem.py` | measure the growth (no API calls - a local simulation) |
| `2_window.py` | sliding window: keep only the last N messages |
| `3_summary.py` | rolling summarization: compress old turns into a string |

```bash
uv run 02_context/1_problem.py
uv run 02_context/3_summary.py     # interactive
```

## Measured

20-turn simulated conversation:

| turn | this request | billed so far |
|------|--------------|---------------|
| 5    | 612          | 2,000         |
| 10   | 1,142        | 6,650         |
| 20   | 2,202        | 23,900        |

Turn 20 costs **11x** turn 1. Nobody notices this in testing, because you test
with 3-turn conversations and users have 50-turn ones.

`len(text) // 4` estimates tokens within ~15% - free and instant, good enough to
reject oversized input before paying for a round-trip.

## Takeaways

| strategy | tokens/turn | remembers |
|----------|-------------|-----------|
| full history | grows forever -> 400 | everything |
| sliding window | flat | last N only - **it will forget your name** |
| summary + window | slow growth | key facts, lossily |

- Summarization costs **an extra API call** and is **lossy in ways you don't
  control**. If the summary prompt doesn't ask for order IDs, they vanish silently.
- "AI memory" is not a database - it's **text you paste into the system prompt**.
- The complete answer is retrieval: keep everything, fetch only what's relevant.
  See `08_rag`. Real systems layer all three.
