import { fetchAPI, ReviewStats } from "@/lib/api";

interface ReviewItem {
    path: string;
    target_slug: string;
    article_ref: string;
    proposals: {
        section: string;
        action: string;
        new_content: string;
        decision: string;
    }[];
    has_decided: boolean;
    has_applyable: boolean;
}

interface ReviewResponse {
    items: ReviewItem[];
    total: number;
}

export default async function ReviewPage() {
    const [queue, stats] = await Promise.all([
        fetchAPI<ReviewResponse>("/api/review-queue"),
        fetchAPI<ReviewStats>("/api/review-queue/stats"),
    ]);

    const undecided = queue.items.filter((it) => !it.has_decided);
    const decided = queue.items.filter((it) => it.has_decided);

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h1 className="text-xl font-semibold">Review Queue</h1>
                <div className="flex items-center gap-4 text-xs text-text-dim font-mono">
                    <span>{stats.total_items} items</span>
                    <span>{stats.total_proposals} proposals</span>
                    <span>{stats.decided_files} decided</span>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4">
                <StatCard label="Undecided" value={stats.by_decision.undecided} />
                <StatCard label="Apply" value={stats.by_decision.apply} color="text-success" />
                <StatCard label="Reject" value={stats.by_decision.reject} color="text-danger" />
                <StatCard
                    label="Edit-then-apply"
                    value={stats.by_decision["edit-then-apply"]}
                    color="text-warning"
                />
            </div>

            {/* Queue Empty State */}
            {queue.total === 0 && (
                <div className="bg-surface border border-border rounded-lg p-12 text-center">
                    <div className="text-4xl mb-3">✅</div>
                    <div className="text-lg font-medium mb-1">Queue 清空</div>
                    <div className="text-sm text-text-dim">
                        所有 review items 已處理完畢。下次 ingest 後會有新的 items 進來。
                    </div>
                </div>
            )}

            {/* Undecided Items */}
            {undecided.length > 0 && (
                <div className="bg-surface border border-border rounded-lg p-5">
                    <h2 className="text-sm font-semibold mb-4">
                        待審核（{undecided.length}）
                    </h2>
                    <div className="space-y-3">
                        {undecided.map((item) => (
                            <QueueItemCard key={item.path} item={item} />
                        ))}
                    </div>
                </div>
            )}

            {/* Decided Items */}
            {decided.length > 0 && (
                <div className="bg-surface border border-border rounded-lg p-5 opacity-70">
                    <h2 className="text-sm font-semibold mb-4">
                        已決策（{decided.length}）
                    </h2>
                    <div className="space-y-3">
                        {decided.map((item) => (
                            <QueueItemCard key={item.path} item={item} />
                        ))}
                    </div>
                </div>
            )}

            {/* Backlog Warning */}
            {stats.total_items > 20 && (
                <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 text-sm text-warning">
                    ⚠️ Review queue 累積 {stats.total_items} 檔（超過 20 警戒線）— 請優先清理
                </div>
            )}
        </div>
    );
}

function StatCard({
    label,
    value,
    color,
}: {
    label: string;
    value: number;
    color?: string;
}) {
    return (
        <div className="bg-surface border border-border rounded-lg p-4">
            <div className="text-[11px] uppercase tracking-wider text-text-dim mb-1">
                {label}
            </div>
            <div className={`text-2xl font-semibold font-mono ${color || ""}`}>
                {value}
            </div>
        </div>
    );
}

function QueueItemCard({ item }: { item: ReviewItem }) {
    return (
        <div className="bg-surface-2 border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-accent font-mono text-xs">
                        {item.target_slug}
                    </span>
                    <span className="text-text-dim text-xs">←</span>
                    <span className="text-text-dim font-mono text-xs truncate max-w-[300px]">
                        {item.article_ref}
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    {item.has_applyable && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded border border-success/40 text-success">
                            has apply
                        </span>
                    )}
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-border text-text-dim">
                        {item.proposals.length} proposal{item.proposals.length !== 1 ? "s" : ""}
                    </span>
                </div>
            </div>

            {/* Proposals */}
            {item.proposals.length > 0 && (
                <div className="space-y-2 mt-3">
                    {item.proposals.map((p, i) => (
                        <div
                            key={i}
                            className="flex items-start gap-3 text-xs border-t border-border pt-2"
                        >
                            <ActionBadge action={p.action} />
                            <div className="flex-1 min-w-0">
                                <div className="font-mono text-text-primary mb-1">
                                    {p.section}
                                </div>
                                <div className="text-text-dim line-clamp-2 whitespace-pre-wrap">
                                    {p.new_content.slice(0, 150)}
                                    {p.new_content.length > 150 ? "..." : ""}
                                </div>
                            </div>
                            <DecisionBadge decision={p.decision} />
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function ActionBadge({ action }: { action: string }) {
    const colors: Record<string, string> = {
        update: "text-accent border-accent/40",
        append: "text-success border-success/40",
        suggest: "text-warning border-warning/40",
    };
    const cls = colors[action] || "text-text-dim border-border";
    return (
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono border ${cls} whitespace-nowrap`}>
            {action}
        </span>
    );
}

function DecisionBadge({ decision }: { decision: string }) {
    const colors: Record<string, string> = {
        apply: "text-success border-success/40 bg-success/10",
        reject: "text-danger border-danger/40 bg-danger/10",
        "edit-then-apply": "text-warning border-warning/40 bg-warning/10",
        undecided: "text-text-dim border-border",
    };
    const cls = colors[decision] || "text-text-dim border-border";
    return (
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono border ${cls} whitespace-nowrap`}>
            {decision}
        </span>
    );
}
