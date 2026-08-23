# 03 - Prompt engineering, measured

You cannot improve what you cannot score. The dataset is the valuable part;
everything else is plumbing.

| file | teaches |
|------|---------|
| `1_measure.py` | ground-truth cases + exact-match scoring across prompt versions |
| `2_hard.py` | a test set built to **break** the prompt |

```bash
uv run 03_prompting/1_measure.py
uv run 03_prompting/2_hard.py
```

## Measured

Easy set (6 cases):

| prompt | score |
|--------|-------|
| v1 naive | **0/6** |
| v2 constrained | 6/6 |
| v3 few-shot | 6/6 |

Hard set (10 adversarial cases):

| prompt | size | score |
|--------|------|-------|
| v2 constrained | ~40 tok | 8/10 |
| v3 few-shot | ~76 tok | 8/10 |
| v4 + other | ~125 tok | 9/10 |
| v5 defined | ~142 tok | **10/10** |

## Takeaways

- **v1 wasn't wrong, it was unformatted.** It knew the answer and wrapped it in
  markdown. Most "the model is dumb" is "I never specified the output shape."
- **No escape hatch = confident garbage.** Forced to pick from 4 categories,
  the model classified `"hi"` as `account`. It never says "I don't know" unless
  you give it a way to.
- **Few-shot went 0-for-2.** Identical scores on both datasets, ~120 wasted
  tokens per call. Not a universal law - just false *here*, which is all that matters.
- **v4 fixed one case and broke another.** The rule *"pick the issue involving
  money"* dragged a display bug into billing. Every instruction has blast radius.
  You only catch it because there's a table.
- **Define categories; don't patch with rules.** Rules stack and interact.
  Definitions don't. That's what got v5 to 10/10.
- Always `temperature=0` in an eval - you're measuring the prompt, not the sampler.
- Adding defenses for failures you haven't *observed* (Hinglish, typos) is how
  prompts bloat. The model handled both with no instruction at all.
