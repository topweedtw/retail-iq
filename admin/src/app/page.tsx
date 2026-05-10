import { fetchAPI, IngestStatus, ProductsResponse, ReviewStats } from "@/lib/api";

async function getDashboardData() {
  const [ingest, products, review] = await Promise.all([
    fetchAPI<IngestStatus>("/api/ingest/status"),
    fetchAPI<ProductsResponse>("/api/products"),
    fetchAPI<ReviewStats>("/api/review-queue/stats"),
  ]);
  return { ingest, products, review };
}

export default async function DashboardPage() {
  const { ingest, products, review } = await getDashboardData();

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">儀表板</h1>
        <span className="text-xs text-text-dim font-mono">
          last refresh: {new Date().toLocaleString("zh-TW")}
        </span>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard
          label="文章總數"
          value={ingest.total_articles}
          sub="raw/ 全部"
        />
        <KPICard
          label="已通過"
          value={ingest.by_status["approved"] || 0}
          sub="approved"
          color="text-success"
        />
        <KPICard
          label="產品頁"
          value={products.total}
          sub="wiki/products/"
        />
        <KPICard
          label="Review Queue"
          value={review.total_items}
          sub={`${review.total_proposals} proposals`}
          color={review.total_items > 20 ? "text-warning" : undefined}
        />
      </div>

      {/* Status Distribution */}
      <div className="grid grid-cols-2 gap-4">
        <Panel title="Ingest 狀態分布">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left text-[11px] uppercase tracking-wider text-text-dim pb-2">
                  Status
                </th>
                <th className="text-right text-[11px] uppercase tracking-wider text-text-dim pb-2">
                  Count
                </th>
                <th className="text-right text-[11px] uppercase tracking-wider text-text-dim pb-2">
                  %
                </th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(ingest.by_status)
                .sort(([, a], [, b]) => b - a)
                .map(([status, count]) => (
                  <tr key={status} className="border-t border-border">
                    <td className="py-2">
                      <StatusBadge status={status} />
                    </td>
                    <td className="py-2 text-right font-mono">{count}</td>
                    <td className="py-2 text-right text-text-dim font-mono">
                      {((count / ingest.total_articles) * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="來源分布（Top 10）">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left text-[11px] uppercase tracking-wider text-text-dim pb-2">
                  Source
                </th>
                <th className="text-right text-[11px] uppercase tracking-wider text-text-dim pb-2">
                  Articles
                </th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(ingest.by_source)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 10)
                .map(([source, count]) => (
                  <tr key={source} className="border-t border-border">
                    <td className="py-2 font-mono text-xs">{source}</td>
                    <td className="py-2 text-right font-mono">{count}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Panel>
      </div>

      {/* Week Distribution */}
      <Panel title="每週 Ingest 量">
        <div className="flex items-end gap-2 h-32">
          {Object.entries(ingest.by_week)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([week, count]) => {
              const maxCount = Math.max(...Object.values(ingest.by_week));
              const height = maxCount > 0 ? (count / maxCount) * 100 : 0;
              return (
                <div key={week} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-accent/30 rounded-t"
                    style={{ height: `${height}%` }}
                  >
                    <div
                      className="w-full bg-accent rounded-t"
                      style={{ height: "100%" }}
                    />
                  </div>
                  <span className="text-[10px] text-text-dim font-mono">
                    {week.replace("2026-", "")}
                  </span>
                  <span className="text-[10px] font-mono">{count}</span>
                </div>
              );
            })}
        </div>
      </Panel>

      {/* Products */}
      <Panel title="產品頁一覽">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left text-[11px] uppercase tracking-wider text-text-dim pb-2">
                Product
              </th>
              <th className="text-left text-[11px] uppercase tracking-wider text-text-dim pb-2">
                Category
              </th>
              <th className="text-right text-[11px] uppercase tracking-wider text-text-dim pb-2">
                Sources
              </th>
              <th className="text-right text-[11px] uppercase tracking-wider text-text-dim pb-2">
                Updated
              </th>
            </tr>
          </thead>
          <tbody>
            {products.products.map((p) => (
              <tr key={p.slug} className="border-t border-border">
                <td className="py-2 font-medium">{p.title}</td>
                <td className="py-2 text-text-dim">{p.product_category}</td>
                <td className="py-2 text-right font-mono">{p.source_count}</td>
                <td className="py-2 text-right text-text-dim font-mono text-xs">
                  {p.last_updated}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

// Components

function KPICard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: number;
  sub: string;
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
      <div className="text-xs text-text-dim mt-1">{sub}</div>
    </div>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <h2 className="text-sm font-semibold mb-4">{title}</h2>
      {children}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    approved: "text-success border-success/40",
    "pending-review": "text-warning border-warning/40",
    pending: "text-text-dim border-border",
    "skipped-low-relevance": "text-danger border-danger/40",
    "skipped-duplicate": "text-text-dim border-border",
    "skipped-filtered": "text-text-dim border-border",
  };
  const cls = colors[status] || "text-text-dim border-border";
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded text-[11px] font-mono border ${cls}`}
    >
      {status}
    </span>
  );
}
