# Gate 4 Review Queue

This directory holds Gate 4 proposals that couldn't be auto-applied and need human review.

Structure:
```
wiki/ingest-queue/
├── README.md              ← this file
├── YYYY-Www/              ← one dir per ISO week
│   ├── <product-slug>--<article-basename>.md   ← per (target × article) pair
│   └── _orphans/
│       └── <article-basename>.md               ← articles with no target page
```

## What ends up here

Per `wiki/design/gate4-ingest.md` §3.3, Gate 4 routes a proposal here when:

1. **Section is human-owned** (§3.6) — even if LLM used `action=update/append`, we downgrade to review. Filter reason: `"human-owned section (action was '<X>' → review)"`.
2. **Section is new** (not yet on the page). Reason: `"new section (not in page)"`. A human decides whether to add it.
3. **LLM explicitly used `action=suggest`**. Reason: `"LLM marked as suggest"`.
4. **Fan-out > 3 candidates** — Gate 4 bails on auto-apply and queues for all.
5. **No target found** → goes to `_orphans/`.

## Reviewing a queue item

Each file has one or more `## Proposal N` sections with:
- Why it's here (`Why review`)
- LLM's reasoning (`LLM reason`)
- `Current excerpt` (what the LLM saw on the page)
- `Proposed content` (what the LLM wants to write)
- Decision checkboxes

Workflow:
1. Open the file, read the proposal
2. Tick `[x] apply`, `[x] reject`, or `[x] edit-then-apply`
3. Fill in `Decided by` and `Decided at`
4. If applying: manually paste content into the target wiki page (or use the future `scripts/review_queue.py` CLI tool — v0.5)
5. Commit: the file stays as audit record; consider moving decided items to `_archive/` once reviewer workflow stabilizes

## Orphan handling

Orphan queue items in `_orphans/` typically mean one of:
- Article introduces a product not yet in `wiki/products/` → create a new page
- Existing page's `tags` frontmatter is too narrow → add missing tags, re-run
- Gate 3 approved it but shouldn't have → manually set `ingest_status: skipped-low-relevance` in meta.json

## Hygiene

- **Don't let this grow unbounded.** Weekly digest should report open-queue count.
- **Lint warning at > 20 items.** (Not yet implemented; planned for v0.5.)
- **Archive decided items.** Keep only "open" items in the active week's dir.
