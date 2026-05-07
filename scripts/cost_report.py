"""cost_report.py — Cross-week LLM cost trend report for RetailIQ.

Reads committed weekly-digest files and extracts the cost section
(Gate 3 calls / Gate 4 calls / tokens / latency) that v2.0+ digests
emit. Produces a multi-week trend table that highlights week-over-week
deltas, so the team can spot runaway token consumption, budget threshold
breaches, or Gate 4 adoption trends.

The source of truth is **committed markdown**, not raw/ re-scanning. This
makes the trend stable across re-runs (same git SHA → same report) and
independent of whether raw/ files still exist.

Usage:
  python3 scripts/cost_report.py              # print trend to stdout
  python3 scripts/cost_report.py --out FILE   # write to markdown
  python3 scripts/cost_report.py --budget 100000  # flag weeks > N tokens
  python3 scripts/cost_report.py --json       # machine-readable output
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIGEST_DIR = REPO_ROOT / "wiki" / "weekly-digest"

# Regexes tuned to the v2.0 digest template rendered by
# scripts/generate_weekly_digest.py render_digest().
_WEEK_RE = re.compile(r"(\d{4}-W\d{2})-digest\.md$")
_G3_RE = re.compile(r"\*\*Gate 3 LLM 呼叫\*\*：(\d+)")
_G4_RE = re.compile(r"\*\*Gate 4 LLM 呼叫\*\*：(\d+)")
_TOKENS_RE = re.compile(r"\*\*估算 token 總量\*\*：([\d,]+)")
_LATENCY_RE = re.compile(r"\*\*估算 LLM 時間\*\*：([\d.]+)s")
_EMPTY_WEEK_RE = re.compile(r"^empty_week:\s*true", re.MULTILINE)


@dataclass
class WeekCost:
    week: str
    gate3_calls: int
    gate4_calls: int
    tokens: int
    latency_sec: float
    path: str  # relative to repo root for display


def parse_digest(path: Path) -> WeekCost | None:
    """Return WeekCost or None if file is empty-week / pre-v2.0 / unparseable."""
    m = _WEEK_RE.search(path.name)
    if not m:
        return None
    text = path.read_text(encoding="utf-8")
    if _EMPTY_WEEK_RE.search(text):
        return None
    g3 = _G3_RE.search(text)
    g4 = _G4_RE.search(text)
    toks = _TOKENS_RE.search(text)
    lat = _LATENCY_RE.search(text)
    if not (g3 and g4 and toks and lat):
        return None
    try:
        try:
            rel = str(path.relative_to(REPO_ROOT))
        except ValueError:
            rel = str(path)  # file outside repo (e.g. tempfile in tests)
        return WeekCost(
            week=m.group(1),
            gate3_calls=int(g3.group(1)),
            gate4_calls=int(g4.group(1)),
            tokens=int(toks.group(1).replace(",", "")),
            latency_sec=float(lat.group(1)),
            path=rel,
        )
    except (ValueError, AttributeError):
        return None


def collect_weeks(digest_dir: Path = DIGEST_DIR) -> list[WeekCost]:
    weeks: list[WeekCost] = []
    for p in sorted(digest_dir.glob("*-digest.md")):
        wc = parse_digest(p)
        if wc is not None:
            weeks.append(wc)
    return weeks


def compute_delta_pct(current: int, previous: int) -> float | None:
    """Return W/W % delta, or None if previous is 0 (undefined)."""
    if previous == 0:
        return None
    return (current - previous) / previous * 100.0


def render_trend(weeks: list[WeekCost], budget: int | None = None) -> str:
    if not weeks:
        return "# Cost Trend Report\n\n⚠️ No v2.0+ digest files with cost sections found.\n"

    lines = [
        "# RetailIQ Cost Trend Report",
        "",
        f"> Generated from {len(weeks)} week(s) of committed digests. "
        "Source: `wiki/weekly-digest/*-digest.md` cost sections (v2.0+).",
        "",
        "## Per-week breakdown",
        "",
        "| Week | G3 calls | G4 calls | Tokens | Latency | Δ tokens vs prev |",
        "|---|---|---|---|---|---|",
    ]
    for i, w in enumerate(weeks):
        if i == 0:
            delta = "—"
        else:
            d = compute_delta_pct(w.tokens, weeks[i - 1].tokens)
            delta = "undef (prev=0)" if d is None else f"{d:+.1f}%"
        flag = ""
        if budget is not None and w.tokens > budget:
            flag = f" 🚨 over {budget:,}"
        lines.append(
            f"| {w.week} | {w.gate3_calls} | {w.gate4_calls} | "
            f"{w.tokens:,}{flag} | {w.latency_sec:.0f}s | {delta} |"
        )

    tot_g3 = sum(w.gate3_calls for w in weeks)
    tot_g4 = sum(w.gate4_calls for w in weeks)
    tot_tok = sum(w.tokens for w in weeks)
    tot_lat = sum(w.latency_sec for w in weeks)
    lines += [
        f"| **Total** | **{tot_g3}** | **{tot_g4}** | "
        f"**{tot_tok:,}** | **{tot_lat:.0f}s** | — |",
        "",
    ]

    # Highlights
    if len(weeks) >= 2:
        last = weeks[-1]
        prev = weeks[-2]
        d_tok = compute_delta_pct(last.tokens, prev.tokens)
        if d_tok is not None:
            direction = "up" if d_tok >= 0 else "down"
            lines += [
                "## Week-over-week",
                "",
                f"- Latest week ({last.week}) tokens {direction} "
                f"**{abs(d_tok):.1f}%** vs {prev.week} "
                f"({prev.tokens:,} → {last.tokens:,}).",
            ]
            if last.gate4_calls == 0 and prev.gate4_calls > 0:
                lines.append(f"- ⚠️ Gate 4 activity dropped to 0 this week.")
            elif prev.gate4_calls == 0 and last.gate4_calls > 0:
                lines.append(
                    f"- 🟢 Gate 4 started contributing this week "
                    f"({last.gate4_calls} calls).")
            lines.append("")

    if budget is not None:
        over = [w for w in weeks if w.tokens > budget]
        if over:
            lines += [
                f"## Budget alerts (> {budget:,} tokens/week)",
                "",
            ]
            for w in over:
                lines.append(f"- 🚨 **{w.week}**: {w.tokens:,} tokens")
            lines.append("")
        else:
            lines += [
                f"## Budget status",
                "",
                f"✅ All {len(weeks)} week(s) under {budget:,}-token budget.",
                "",
            ]

    lines += [
        "---",
        "",
        "> Notes:",
        "> - Token + latency values are estimates (Gate 3: 2.3k tok/call, "
        "1.5s; Gate 4: 5k tok/call, 4s) calibrated from early W2 runs.",
        "> - Empty-week digests (`empty_week: true` in frontmatter) and "
        "pre-v2.0 `*-relevance.md` files are intentionally skipped.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-week LLM cost trend report")
    ap.add_argument("--out", help="write markdown to path instead of stdout")
    ap.add_argument("--budget", type=int, default=None,
                    help="flag weeks above N tokens (e.g. --budget 100000)")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON instead of markdown")
    args = ap.parse_args()

    weeks = collect_weeks()

    if args.json:
        payload = {
            "weeks": [asdict(w) for w in weeks],
            "totals": {
                "gate3_calls": sum(w.gate3_calls for w in weeks),
                "gate4_calls": sum(w.gate4_calls for w in weeks),
                "tokens": sum(w.tokens for w in weeks),
                "latency_sec": sum(w.latency_sec for w in weeks),
            },
        }
        out = json.dumps(payload, indent=2, ensure_ascii=False)
    else:
        out = render_trend(weeks, budget=args.budget)

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(out, encoding="utf-8")
        rel = path.relative_to(REPO_ROOT) if str(path).startswith(str(REPO_ROOT)) else path
        print(f"✅ wrote {rel} ({len(weeks)} week(s))")
    else:
        print(out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
