# job_finder

Pull job postings from public ATS APIs, match them against my profile, surface
only the few worth reading - with reasons - and say "nothing today" when there
is nothing.

## Status

Scaffolded. Data source verified (see `../NOTES.md`), nothing built yet.

## Planned files

| file | job |
|------|-----|
| `sources.py` | which companies to pull from |
| `fetch.py` | Greenhouse -> clean records on disk |
| `profile.md` | what I have and what I want - the thing jobs are matched against |
| `index.py` | embed the distilled JDs, cached |
| `match.py` | retrieve -> rerank -> top 5 with reasons and gaps |
| `run.py` | the daily entry point |

## Design decisions already made

- **No scraping.** Public Greenhouse/Lever APIs only.
- **Embed a distilled JD, keep the full text for display.** Company boilerplate is
  identical across every posting at a company; embedding it makes vectors
  converge and kills discrimination (`07_embeddings/4_chunking.py`).
- **Metadata filter before ranking** - staleness, location - not after
  (`08_rag/3_grounded.py`).
- **Reranking is the product**, not a nicety. ~1,700 postings -> 5.
- **An empty result is a valid output.** "Nothing today" beats 5 weak matches.

## Not in v1

a web UI, multi-user anything, auto-applying, resume rewriting
