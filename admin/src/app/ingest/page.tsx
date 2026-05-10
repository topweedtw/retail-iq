import { fetchAPI, IngestStatus, SourcesResponse } from "@/lib/api";

async function getIngestData() {
    const [status, sources] = await Promise.all([
        fetchAPI<IngestStatus>("/api/ingest/status"),
        fetchAPI<SourcesResponse>("/api/ingest/sources"),
    ]);
    return { status, sources };
}

export default async function IngestPage() {
    const { status, sources } = await getIngestData();

    const enabledSources = sources.sources.filter((s) => s.enabled);
    const disabledSources = sources.sources.filter((s) => !s.enabled);

    return (
        <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-xl font-semibold">Ingest Pipeline</h1>
                <div className="flex items-center gap-3">
                    <span className="text-xs text-text-dim font-mono">
                        {status.total_articles} articles in raw/
                    </span>
                </div>
            </div>

            {/* Pipeline Status */}
            <div className="bg-surface border border-border rounded-lg p-5">
                <h2 className="text-sm font-semibold mb-4">Pipeline 狀態</h2>
                <div className="flex items-center gap-2 text-xs font-mono">
                    <Gate label="1a Hash" status="active" />
                    <Arrow />
                    <Gate label="1b Embed" status="active" />
                    <Arrow />
                    <Gate label="2 Filter" status="active" />
                    <Arrow />
                    <Gate label="3 Score" status="active" />
                    <Arrow />
                    <Gate label="4 Ingest" status="active" />
                </div>
            </div>

            {/* Sources Table */}
            <div className="bg-surface border border-border rounded-lg p-5">
                <h2 className="text-sm font-semibold mb-4">
                    啟用來源（{enabledSources.length}）
                </h2>
                <table className="w-full text-sm">
                    <thead>
                        <tr>
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim pb-2">
                                Name
                            </th>
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim pb-2">
                                Tier
                            </th>
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim pb-2">
                                Method
                            </th>
                            <th className="text-right text-[11px] uppercase tracking-wider text-text-dim pb-2">
                                Articles
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {enabledSources.map((s) => (
                            <tr key={s.name} className="border-t border-border">
                                <td className="py-2.5 font-mono text-xs">{s.display_name}</td>
                                <td className="py-2.5">
                                    <TierBadge tier={s.tier} />
                                </td>
                                <td className="py-2.5 text-text-dim text-xs">{s.fetch_method}</td>
                                <td className="py-2.5 text-right font-mono">
                                    {status.by_source[s.name] || 0}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Disabled Sources */}
            {disabledSources.length > 0 && (
                <div className="bg-surface border border-border rounded-lg p-5 opacity-60">
                    <h2 className="text-sm font-semibold mb-4">
                        停用來源（{disabledSources.length}）
                    </h2>
                    <div className="flex flex-wrap gap-2 text-xs">
                        {disabledSources.map((s) => (
                            <span
                                key={s.name}
                                className="px-2 py-1 rounded border border-border text-text-dim font-mono"
                            >
                                {s.name}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

function Gate({ label, status }: { label: string; status: string }) {
    const color = status === "active" ? "border-success text-success" : "border-border text-text-dim";
    return (
        <div className={`px-3 py-1.5 rounded border ${color}`}>
            {label}
        </div>
    );
}

function Arrow() {
    return <span className="text-text-dim">→</span>;
}

function TierBadge({ tier }: { tier: string }) {
    const colors: Record<string, string> = {
        T1: "text-green-400 border-green-700",
        T2: "text-blue-400 border-blue-700",
        "T2-filtered": "text-blue-300 border-blue-600",
        T3: "text-purple-400 border-purple-700",
    };
    const cls = colors[tier] || "text-text-dim border-border";
    return (
        <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-mono border ${cls}`}>
            {tier}
        </span>
    );
}
