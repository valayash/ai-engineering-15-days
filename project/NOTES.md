# Project notes

## The idea

A job finder. Pull postings from companies worth working at, match them against
my profile, and surface only the few worth reading - with a reason, and an honest
"nothing today" when there is nothing.

## Why this one

Considered mail summary and mail auto-reply too. Rejected both:

| idea | killed by |
|------|-----------|
| mail summary | Gmail OAuth + the trust barrier; crowded; low differentiation |
| mail auto-reply | sending on someone's behalf is irreversible - all risk, little learning |
| **job finder** | **I am the user, and it reuses 06/07/08 directly** |

The deciding factor: I use it daily, so I know immediately when it is wrong.

## What it reuses

| from | for |
|------|-----|
| `07_embeddings` | embed job descriptions and my profile |
| `08_rag/rag.py` | retrieve + rerank: 200 postings -> 5 worth reading |
| reranking | the core feature - "does this job ACTUALLY fit", not "is it nearby" |
| citations | "matched on: Python, LLM APIs, RAG [JD-88]" |
| refusal | "nothing good today" beats 5 mediocre matches |
| `06_agents/agent.py` | fetch, filter, track, notify on a schedule |
| `09_evals` | label 50 jobs good/bad myself -> measure precision@5 |

## Data source - VERIFIED 2026-08-23

No scraping. Public ATS APIs, which exist so job aggregators can consume them.

**Greenhouse** - works, 4/4 companies tested:

```
https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true
```

| company | jobs |
|---------|------|
| stripe | 575 |
| databricks | 821 |
| airbnb | 189 |
| figma | 161 |

**Lever** - API is live (`api.lever.co/v0/postings/{company}?mode=json`), but
company slugs must be looked up; guessed ones 404. Add later.

LinkedIn: not used. Against ToS, technically hostile.

### What one job record gives us

```
content       6474 chars of real job description (HTML)
title         "Data Engineer"
location      "San Francisco, CA - New York, NY - United States"
departments   [...]        offices    [...]
updated_at    2026-08-10   first_published
absolute_url  the citation link
```

**One HTTP request per company** returns every posting with its full description.
No pagination, no auth, no rate-limit headaches at this volume. Be polite anyway.

### What this means for the design

- **Metadata comes free**, and it maps straight onto `08_rag/kb.py`'s `Chunk`:
  `updated_at` -> staleness filter, `location`/`departments` -> `where` predicate.
  Filter BEFORE ranking, same as `3_grounded.py`.
- **6.5k chars per JD is too big to embed whole.** Half of it is boilerplate
  company blurb identical across every posting - which is exactly the
  `4_chunking.py` finding: shared text makes vectors converge and destroys
  discrimination. Strip the boilerplate, or embed only the requirements section.
- **Cost is real at this scale.** 4 companies = 1,746 jobs. Embedding every full
  JD is wasteful; embed a distilled version (requirements + title + level) and
  keep the full text for display. That is `08_rag`'s "what you embed does not
  have to be what you show".
- **Reranking is the whole product.** 1,746 postings -> 5 worth reading. Vector
  search alone cannot do that; `4_rerank.py` can, and can also say "nothing
  today".

## Scope for v1

1. pull postings from ~20 target companies
2. store my profile as a document
3. rank + rerank -> top 5 with reasons and gaps
4. label results myself -> an eval set
5. run daily, notify

No UI. A CLI plus a daily message is a complete product. Interface comes after
it is actually finding jobs.

## Deliberately NOT in v1

- a web UI
- multi-user anything
- auto-applying (irreversible, and a bad idea)
- resume rewriting
