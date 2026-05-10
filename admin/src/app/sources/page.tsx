import { fetchAPI, SourcesResponse, IngestStatus } from "@/lib/api";

export default async function SourcesPage() {
    const [sources, status] = await Promise.all([
        fetchAPI<SourcesResponse>("/api/ingest/sources"),
        fetchAPI<IngestStatus>("/api/ingest/status"),
    ]);

    const enabled = sources.sources.filter((s) => s.enabled);
    const disabled = sources.sources.filter((s) => !s.enabled);

    return (
        <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-xl font-semibold">
                    資料來源（{sources.total}）
                </h1>
                <span className="text-xs text-text-dim font-mono">
                    {enabled.length} enabled / {disabled.length} disabled
                </span>
            </div>

            {/* Enabled */}
            <div className="bg-surface border border-border rounded-lg overflow-hidden">
                <div className="px-4 py-3 bg-surface-2 border-b border-border">
                    <h2 className="text-sm font-semibold">啟用中（{enabled.length}）</h2>
                </div>
                <table className="w-full text-sm">
                    <thead>
                        <tr>
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                Name
                            </th>
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                Display
                            </th>
                            <th className="text-center text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                Tier
                            </th>
                            <th className="text-center text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                Method
                            </th>
                            <th className="text-right text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                Articles
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {enabled.map((s) => (
                            <tr key={s.name} className="border-t border-border hover:bg-surface-2">
                                <td className="px-4 py-2.5 font-mono text-xs">{s.name}</td>
                                <td className="px-4 py-2.5">{s.display_name}</td>
                                <td className="px-4 py-2.5 text-center">
                                    <TierBadge tier={s.tier} />
                                </td>
                                <td className="px-4 py-2.5 text-center text-text-dim text-xs font-mono">
                                    {s.fetch_method}
                                </td>
                                <td className="px-4 py-2.5 text-right font-mono">
                                    {status.by_source[s.name] || 0}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Disabled */}
            {disabled.length > 0 && (
                <div className="bg-surface border border-border rounded-lg overflow-hidden opacity-60">
                    <div className="px-4 py-3 bg-surface-2 border-b border-border">
                        <h2 className="text-sm font-semibold">
                            停用（{disabled.length}）
                        </h2>
                    </div>
                    <table className="w-full text-sm">
                        <thead>
                            <tr>
                                <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                    Name
                                </th>
                                <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                    Display
                                </th>
                                <th className="text-center text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                    Tier
                                </th>
                                <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-2">
                                    Reason
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {disabled.map((s) => (
                                <tr key={s.name} className="border-t border-border">
                                    <td className="px-4 py-2.5 font-mono text-xs">{s.name}</td>
                                    <td className="px-4 py-2.5">{s.display_name}</td>
                                    <td className="px-4 py-2.5 text-center">
                                        <TierBadge tier={s.tier} />
                                    </td>
                                    <td className="px-4 py-2.5 text-text-dim text-xs">
                                        RSS 故障 / 低相關度
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
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
        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-mono border ${cls}`}>
            {tier}
        </span>
    );
}
