# Gate 4 Design — LLM Ingest to Wiki

**Status**: 🟡 Draft (v0.1) — 2026-05-07
**Target**: v0.4 milestone
**Refs**: AGENTS.md §3.6 (Segment Ownership), §8.5 (Gate pipeline), §8.10 (relevance)
**Prereqs**: Gate 1a+1b+2+3 shipped ✅

---

## 1. Problem & Goals

### Problem
Articles in `raw/<source>/<week>/` accumulate with `ingest_status=approved` (or `pending-review`) after Gates 1-3 — but **nothing propagates into `wiki/`**. Human curators must still manually read raw, decide which wiki page to update, write the update, and cite the source.

### Goal (v0.4)
Automate the safe portion of that loop:

1. Given a raw article with `ingest_status ∈ {approved, pending-review}`
2. Identify which `wiki/products/*.md` page(s) it affects
3. Propose section-level updates via LLM
4. **Apply automatically** to `ingest_managed_sections` (safe per §3.6)
5. **Queue for human review** any proposals touching `human_owned_sections` or brand-new sections
6. Update `last_updated` + `source_count` + append `[^N]` citation

### Non-goals (v0.4)
- Rewriting `human_owned_sections` — always goes to review queue
- Translating / re-formatting — LLM must output in existing wiki voice
- Cross-page restructuring (e.g. splitting one product into two)
- Media / image handling

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Gate 4 Pipeline                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  raw/.../<article>.meta.json                                │
│     │ (status=approved or pending-review)                   │
│     │ key_entities=[...]                                    │
│     ▼                                                       │
│  ┌─────────────┐                                            │
│  │  4a. Route  │  match key_entities against product tags   │
│  │             │  → candidate wiki pages                    │
│  └─────────────┘                                            │
│     │                                                       │
│     ▼                                                       │
│  ┌─────────────┐                                            │
│  │  4b. Propose│  LLM(article + target page frontmatter     │
│  │             │       + current section content)           │
│  │             │  → [{section, action, new_content}, ...]   │
│  └─────────────┘                                            │
│     │                                                       │
│     ▼                                                       │
│  ┌─────────────┐                                            │
│  │  4c. Filter │  split proposals by ownership (§3.6):      │
│  │             │    • managed → auto-apply queue            │
│  │             │    • human-owned → review queue            │
│  │             │    • new section → review queue (NEEDS)    │
│  └─────────────┘                                            │
│     │                                                       │
│     ▼                                                       │
│  ┌─────────────┐                                            │
│  │  4d. Apply  │  atomic write to wiki/products/*.md        │
│  │             │  + update frontmatter (last_updated++,     │
│  │             │    source_count++)                         │
│  │             │  + append [^N] citation                    │
│  │             │  + log entry in wiki/log.md                │
│  └─────────────┘                                            │
│     │                                                       │
│     ▼                                                       │
│  wiki/ingest-queue/YYYY-Www/<slug>.md                       │
│     (human review queue for non-managed proposals)          │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Key Design Decisions

### 3.1 Routing: entity-match → LLM narrow

Cheapest reliable router given current schema:

```python
# Step 1: candidates by entity overlap
candidates = []
for product_page in wiki/products/*.md:
    tags = frontmatter.tags  # e.g. ["iphone", "a19", "apple-intelligence"]
    entity_hits = len(set(tags) & set(article.key_entities_normalized))
    if entity_hits > 0:
        candidates.append((product_page, entity_hits))

# Step 2: if >1 candidate, ask LLM to pick
if len(candidates) > 1:
    target = llm_pick_target(article, candidates)
```

**Rationale**: Gate 3 already computes `key_entities`. Tag overlap is free. LLM only runs for ambiguous cases (cost ≈ 0.2s/article).

**Alternatives considered**:
- Pure LLM routing: too expensive, worse grounding
- Product-name regex: too brittle for i18n + aliases

### 3.2 Proposal format: structured JSON

LLM outputs:
```json
{
  "proposals": [
    {
      "section": "核心規格",
      "action": "update",
      "current_excerpt": "A18 Pro chip...",
      "new_content": "A19 Pro chip (3nm+)...\n- 6-core CPU...",
      "reason": "Article confirms A19 spec"
    },
    {
      "section": "五大賣點（Selling Points）",
      "action": "suggest",
      "new_content": "...",
      "reason": "Could add point re 8GB RAM, but this is human-owned"
    },
    {
      "section": "AI 功能",
      "action": "append",
      "new_content": "## AI 功能\n...",
      "reason": "Section does not exist; new content"
    }
  ]
}
```

**Rationale**:
- Structured → easy to audit + respect ownership at filter time
- Actions are bounded (3 types) → predictable
- `current_excerpt` lets us verify LLM saw the right thing before applying
- `reason` feeds log.md for audit trail

**Alternatives**: full-page rewrite (too risky), unified diff (LLM bad at these).

### 3.3 Human review queue: files, not UI

Write proposals to `wiki/ingest-queue/YYYY-Www/<product-slug>.md` per article:

```markdown
# Ingest review: iphone-17-pro ← ars-technica/mac-mini-starting-price

**Article**: raw/ars-technica/2026-W19/mac-mini-starting-price...
**Status at Gate 3**: approved (score=8)
**Target page**: wiki/products/iphone-17-pro.md
**Created**: 2026-05-07T11:20:00+08

## Proposal 1: 五大賣點 (human-owned → review required)
[... content ...]

**Decision**: [ ] apply  [ ] reject  [ ] edit-then-apply
**Decided by**: @___
**Decided at**: ___
```

**Rationale**:
- No web UI to build
- Reviewer can `grep -r "apply" wiki/ingest-queue/` to find actioned items
- Lives in repo, audit via git
- Future v0.5: simple CLI tool to walk queue + apply/reject

**Alternatives**: CLI prompts (blocks ingest_agent on human), auto-PR per proposal (PR noise).

### 3.4 Idempotency: track via `source_count` + citation footnotes

Each applied proposal:
1. Increments `source_count` in frontmatter
2. Appends `[^N]` with unique source ref (`raw/<source>/<week>/<basename>`)
3. Meta.json gains `ingest_log_ref = "<wiki-commit-sha>"`

If the same article is re-processed:
1. `meta.ingest_log_ref` is non-null → Gate 4 skips (log "already applied")

Re-run after rollback: clear `meta.ingest_log_ref`, re-run.

### 3.5 Failure modes (graceful)

| Scenario | Behavior |
|---|---|
| LLM call fails | Skip this article, `ingest_status` unchanged, retry next run |
| LLM returns invalid JSON | Log + skip |
| Proposed section doesn't exist on page | Treat as `append` with NEEDS REVIEW |
| `current_excerpt` doesn't match page | Log mismatch, reject proposal (hallucination guard) |
| No candidate page | Log "orphan article" + skip (T2+ common case) |
| Multiple candidates + LLM can't decide | Write to `wiki/ingest-queue/_orphans/` for human routing |

---

## 4. Schema additions

### 4.1 `meta.json` (`.meta.json` per article)
```diff
  "ingest_status": "approved",
+ "ingest_log_ref": null | "<timestamp>|<wiki-commit-sha>",
+ "ingest_targets": null | ["iphone-17-pro", ...],   // populated by Gate 4
```

### 4.2 Product page frontmatter
```diff
  last_updated: 2026-04-30
  source_count: 4
+ ingest_history:                 # optional, auto-maintained
+   - article: raw/ars-technica/2026-W19/mac-mini-starting-price_20260504
+     applied_at: 2026-05-07T11:20:00+08
+     sections: [核心規格, 起售價]
```

### 4.3 New dir `wiki/ingest-queue/`
```
wiki/ingest-queue/
├── README.md                    # explains queue lifecycle
├── 2026-W19/
│   ├── iphone-17-pro.md        # review items for this product this week
│   └── _orphans/
│       └── <article-slug>.md   # no routing target
```

---

## 5. LLM Prompt Sketch

```
SYSTEM:
You update Apple retail-training wiki pages based on source articles.
You MUST respect section ownership declared in frontmatter:
- ingest_managed_sections: you may propose updates (action: update/append)
- human_owned_sections: you may only suggest (action: suggest) — do not rewrite

Output strict JSON matching the schema below. No extra text.

Schema:
{
  "target_valid": bool,                       // is this the right page for this article?
  "target_valid_reason": string,
  "proposals": [
    {
      "section": string,                       // exact heading text, no ##
      "action": "update" | "append" | "suggest",
      "current_excerpt": string | null,        // first 200 chars of current section if action=update
      "new_content": string,                   // full replacement or new content
      "reason": string                         // ≤ 60 chars
    }
  ]
}

USER:
=== ARTICLE ===
Title: {article.title}
Source: {article.source} (tier {tier})
Score: {article.relevance_score}
Key entities: {article.key_entities}

{article.text}

=== TARGET PAGE: wiki/products/{slug}.md ===
Frontmatter:
  ingest_managed_sections: [...]
  human_owned_sections: [...]

Current content:
{page.body}
```

Expected latency: ~2-4s per article (chat model with ~2-4k tokens context).

---

## 6. Implementation Phases

### Phase 1: Routing (PoC, no writes)
- New `scripts/gate4_router.py`
- Input: one `.meta.json`
- Output: candidate page(s) + rationale, stdout only
- Validate on 8 W19 approved/pending-review articles
- **Exit criteria**: ≥80% of hand-picked expected matches

### Phase 2: LLM proposals (dry-run)
- Add `propose()` using chat model
- Input: article + target page
- Output: structured JSON, print to stdout
- Run on 5 W19 articles, manually score: "would I accept this proposal?"
- **Exit criteria**: ≥60% of managed-section proposals would be accepted by reviewer

### Phase 3: Apply (managed sections only)
- `--apply` flag writes to `wiki/products/*.md`
- Atomic write (sandbox-safe pattern reused)
- `ingest_log_ref` recorded in meta.json
- `wiki/log.md` entry per applied article
- Tests: 15+ covering hallucination guard, idempotency, frontmatter updates

### Phase 4: Review queue + Lint + Integration
- Queue writes to `wiki/ingest-queue/<week>/*.md`
- Lint: human_owned sections never modified except via queue
- Integrate as Gate 4 step in `ingest_agent.py` process_article
- `--skip-gate4` CLI flag parallel to `--skip-gate1b` / `--skip-scoring`

### Phase 5 (optional, v0.5): Review CLI tool
- `scripts/review_queue.py` — walks `wiki/ingest-queue/`, prompts apply/reject/edit
- Git-aware: applies as a commit per decision

---

## 7. Resolved Decisions & Remaining Questions

### Resolved (2026-05-07 review)

**D1. Multi-product fan-out ✅ YES**
One article MAY apply to multiple product pages if entity-overlap passes threshold on each. Each target runs an independent Gate 4 call (own proposals, own review queue entries).
- Rationale: ars-technica Mac mini article genuinely updates both `mac-mini` and (comparatively) `mac-studio`. Losing the cross-page signal would miss real value.
- Implementation: Router returns `list[target]`, Phase 3 loops per target.
- Cost: N× LLM calls per fan-out article. Expected N ≤ 2 for 95%+ articles based on W19 inspection.
- Guard: cap at N=3 per article; anything above → write all to review queue.

**D2. Section heading drift: allow but force review ✅**
LLM may propose sections that don't exist on the target page (e.g. "Specs" when page has "核心規格"). Do NOT enum-restrict in the prompt.
- If proposed section matches an existing heading (exact string match) → normal flow
- If it doesn't match → force `action: append` + NEEDS REVIEW in queue, regardless of ownership
- Rationale: rigid enum hides the fact that source material may justify a new section. Human review catches either (a) genuine new section needed, or (b) LLM confused — both are review-worthy.

**D3. Testing strategy: full fixtures + live LLM ✅**
- `tests/fixtures/gate4/` — frozen (article, page, expected-structure) tuples for deterministic unit tests
- `tests/test_gate4_live.py` — runs against real Apple GenAI proxy, marked as integration, runs in CI when `APPLE_GENAI_MOCK != "1"` AND proxy reachable
- Frozen tests assert JSON schema + structural properties (proposal count, action enum, section-ownership classification)
- Live tests assert end-to-end: article X → proposal Y includes spec update → applied → page has [^N] citation
- CI default: mock mode (fast, reproducible); nightly or pre-release: live mode for regression detection

### Remaining (defer to implementation)

1. **Ordering within a run**: if 3 W19 articles all touch `iphone-17-pro` `核心規格`, apply sequentially so each LLM call sees the latest state. Cost: 3× calls but accuracy matters. (Decided in draft — not contentious.)
2. **Token cost**: ~4k input × 10 approved/week × 52 weeks ≈ 2M tokens/year. Acceptable; add to weekly digest to track trend.
3. **`admin-upload` bypass**: YES, admin-upload articles skip Gate 4. Admin writes directly.
4. **Multi-product threshold**: how many entity hits minimum to qualify as "target"? Initial value: 2. Revise after W20+ data.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| LLM hallucinates facts not in source | `current_excerpt` verification; citations [^N] must link to actual article |
| LLM overwrites carefully-worded managed section with generic content | Lint rule: proposals changing >50% of a section → force review queue |
| Review queue becomes unread backlog | Weekly digest shows open-queue count; lint warning at >20 items |
| Rollback nightmare if bug applies bad updates to 10 pages | `--dry-run` default for first 2 weeks; git revert is the escape hatch |
| Cost blowup from re-running | `ingest_log_ref` idempotency; `--only-unprocessed` flag |

---

## 9. Success Criteria (v0.4 exit)

- [ ] Gate 4 integrated into pipeline; `--skip-gate4` works
- [ ] 5 W19+ articles successfully applied to wiki/products/ auto
- [ ] ≥ 10 NEEDS REVIEW queue items written without false positives
- [ ] Zero unintended modifications to `human_owned_sections` in git history
- [ ] 20+ unit tests (routing + propose JSON schema + filter + apply + idempotency)
- [ ] AGENTS.md schema bumped to v2.0 (v0.4 milestone = full 5-gate pipeline)
- [ ] W19/W20 comparison: before-Gate-4 vs after-Gate-4 wiki page quality (manual eval)

---

## 10. Estimate

| Phase | Effort |
|---|---|
| 1. Routing PoC | 0.5 day |
| 2. Propose (dry-run) | 1 day |
| 3. Apply + tests | 1.5 days |
| 4. Queue + integration | 1 day |
| 5. (optional CLI) | +1 day |
| **Total v0.4 core** | **~4 days** |

Assumes we keep Phase 5 as v0.5 stretch.

---

## Appendix: Related existing code

- `scripts/ingest_agent.py` L410-455 — Gate 3 integration pattern (follow for Gate 4)
- `scripts/backfill_gate3.py::atomic_write_json` — sandbox-safe write pattern
- `scripts/embedding_index.py::EmbeddingIndex` — persistent index pattern (similar for `wiki/ingest-queue/` index?)
- `scripts/relevance_scorer.py::score_article` — LLM-call + JSON-parse reference
