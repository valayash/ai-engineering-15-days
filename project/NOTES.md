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

## Open question, to verify before designing around it

**Where do postings come from?** LinkedIn scraping is against ToS and hostile -
not building on it. Candidates to test:

- Greenhouse public job board JSON
- Lever public postings API
- RSS / APIs from job boards that publish them
- company career pages directly

Nothing below is decided until this is confirmed.

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
