#!/usr/bin/env python3
"""
scripts/gate4_pipeline.py — Gate 4 end-to-end orchestration

Brings together routing (Phase 1) + proposing (Phase 2) + applying (Phase 3)
+ queue writing (Phase 4) into a single entry point: run_gate4(meta_path).

Called by ingest_agent.py as a post-pass after Gates 1-3, gated by
--skip-gate4 CLI flag.
"""
from __future__ import annotations
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SCRIPTS = Path(__file__).resolve().parent
from .gate4_router import load_products, route, RouteMatch  # noqa: E402
from .gate4_proposer import propose, _load_article          # noqa: E402
from .gate4_applier import apply_to_page, ApplyResult, PRODUCTS_DIR, mark_meta_applied  # noqa: E402
from .gate4_queue import write_review, write_orphan        # noqa: E402
from .llm_client import LLMClient, make_client                          # noqa: E402

REPO_ROOT = SCRIPTS.parent

# Multi-product fan-out cap (design doc D1)
MAX_FANOUT = 3

# Status values eligible for Gate 4
GATE4_ELIGIBLE_STATUSES = {"approved", "pending-review"}


@dataclass
class Gate4Report:
    processed: int = 0                    # articles that went through Gate 4
    applied_articles: int = 0             # articles that produced at least 1 apply
    total_applied_sections: int = 0       # total sections written
    review_items: int = 0                 # queue files written (including orphans)
    orphans: int = 0
    skipped_already_applied: int = 0
    skipped_not_eligible: int = 0
    errors: list[str] = field(default_factory=list)


def run_gate4_for_article(
    meta_path: Path,
    *,
    llm: LLMClient,
    products: list,
    dry_run: bool = False,
) -> tuple[Optional[ApplyResult], list[Path]]:
    """Process one article through Gate 4. Returns (primary_result, written_queue_paths).

    Returns (None, []) if skipped for any reason.
    """
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    status = meta.get("ingest_status")
    if status not in GATE4_ELIGIBLE_STATUSES:
        return None, []
    if meta.get("ingest_log_ref"):
        return None, []  # idempotent: already applied

    basename = meta_path.name.replace(".meta.json", "")

    # Phase 1: routing
    entities = meta.get("key_entities", [])
    matches: list[RouteMatch] = route(entities, products, threshold=1.0)

    # Orphan case
    if not matches:
        article_ref = str(meta_path.relative_to(REPO_ROOT)).replace(".meta.json", "") \
            if str(meta_path).startswith(str(REPO_ROOT)) else basename
        path = write_orphan(
            article_meta=meta, article_ref=article_ref,
            article_basename=basename, dry_run=dry_run,
        )
        return None, [path]

    # Cap fan-out
    if len(matches) > MAX_FANOUT:
        logging.warning(
            f"  article {basename}: {len(matches)} candidates > MAX_FANOUT={MAX_FANOUT}; "
            f"routing all to review queue (no auto-apply)"
        )
        # Write each as orphan-ish entry under target-specific queue
        written: list[Path] = []
        article_ref = str(meta_path.relative_to(REPO_ROOT)).replace(".meta.json", "") \
            if str(meta_path).startswith(str(REPO_ROOT)) else basename
        for m in matches:
            # No proposals yet since we bail before LLM call — minimal record
            path = write_review(
                target_slug=m.product.slug, article_meta=meta,
                article_ref=article_ref, article_basename=basename,
                reviewed_proposals=[],  # empty; human decides
                dry_run=dry_run,
            )
            written.append(path)
        # #15: 設定 ingest_log_ref，防止下次 --gate4-only 重複寫入相同 review 檔案
        if not dry_run:
            mark_meta_applied(
                meta_path,
                wiki_ref="gate4-fanout-review",
                targets=[m.product.slug for m in matches],
            )
        return None, written

    # Load article text once
    _, text = _load_article(meta_path)

    article_ref = str(meta_path.relative_to(REPO_ROOT)).replace(".meta.json", "") \
        if str(meta_path).startswith(str(REPO_ROOT)) else basename

    written_queue_paths: list[Path] = []
    primary_result: Optional[ApplyResult] = None

    for m in matches:
        product_path = PRODUCTS_DIR / f"{m.product.slug}.md"
        page_md = product_path.read_text(encoding="utf-8")
        try:
            pset = propose(
                article_meta=meta, article_text=text,
                product_page_md=page_md, product_slug=m.product.slug,
                client=llm,
            )
        except Exception as e:
            logging.warning(f"  propose failed for {basename} → {m.product.slug}: {e}")
            continue

        result = apply_to_page(
            proposal_set=pset,
            product_path=product_path,
            article_meta_path=meta_path,
            dry_run=dry_run,
        )
        if primary_result is None:
            primary_result = result

        # Write review queue for any review/rejected proposals
        if result.reviewed_proposals or result.rejected_proposals:
            p = write_review(
                target_slug=m.product.slug, article_meta=meta,
                article_ref=article_ref, article_basename=basename,
                reviewed_proposals=result.reviewed_proposals,
                rejected_proposals=result.rejected_proposals,
                dry_run=dry_run,
            )
            written_queue_paths.append(p)

    return primary_result, written_queue_paths


def run_gate4_pass(
    meta_paths: list[Path],
    *,
    llm: LLMClient,
    dry_run: bool = False,
) -> Gate4Report:
    """Run Gate 4 over a list of meta.json paths."""
    report = Gate4Report()
    products = load_products()
    if not products:
        logging.warning("Gate 4: no products loaded, skipping pass")
        return report

    for mp in meta_paths:
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except Exception as e:
            report.errors.append(f"{mp}: {e}")
            continue

        status = meta.get("ingest_status")
        if status not in GATE4_ELIGIBLE_STATUSES:
            report.skipped_not_eligible += 1
            continue
        if meta.get("ingest_log_ref"):
            report.skipped_already_applied += 1
            continue

        report.processed += 1
        try:
            result, queue_paths = run_gate4_for_article(
                mp, llm=llm, products=products, dry_run=dry_run,
            )
        except Exception as e:
            report.errors.append(f"{mp.name}: {e}")
            continue

        if result and result.applied_sections:
            report.applied_articles += 1
            report.total_applied_sections += len(result.applied_sections)
        report.review_items += len(queue_paths)
        # Heuristic: if only queue paths written and it looked like orphan
        if not result and queue_paths and queue_paths[0].parent.name == "_orphans":
            report.orphans += 1

    return report
