# 04 - Structured output

Getting JSON you can actually rely on.

| file | teaches |
|------|---------|
| `1_naive.py` | ask for JSON in the prompt -> markdown fences -> crash |
| `2_json_mode.py` | `response_format={"type":"json_object"}` -> parses, values still free-form |
| `3_schema.py` | Pydantic schema -> shape **and** vocabulary guaranteed |

```bash
uv run 04_structured_output/3_schema.py
```

## The three levels

| level | guarantees | fails when |
|-------|------------|------------|
| ask in the prompt | nothing | ```` ```json ```` fences, preamble prose |
| `json_object` | parseable JSON | keys/values are whatever it feels like |
| Pydantic schema | exact shape + closed vocabulary | - |

## Takeaways

- **Levels 1-2 ask. Level 3 constrains the sampler.** With a schema attached the
  API masks out every token that would make the output invalid *before* sampling.
  Not obedience - mechanically impossible to violate.
- One line of schema replaces a paragraph of prompt, and is stronger:

  ```python
  category: Literal["shipping", "billing", "account", "bug", "other"]
  ```

- **Schema guarantees SHAPE, never CORRECTNESS.** It can still confidently return
  `billing` for a shipping issue. Use `03_prompting`'s harness to check *right*.
- `Field(description=...)` is sent to the model - it's real prompt space.
- Fallback when a provider only supports `json_object`:
  `Model.model_validate_json(raw)` + retry on `ValidationError`.
- **Tool calling is this same mechanism**, pointed at functions instead of output.
