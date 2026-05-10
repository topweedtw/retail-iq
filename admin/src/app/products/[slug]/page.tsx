import { fetchAPI } from "@/lib/api";
import { notFound } from "next/navigation";

interface ProductDetail {
    slug: string;
    frontmatter: Record<string, unknown>;
    sections: Record<string, string>;
    raw_markdown: string;
}

export default async function ProductDetailPage({
    params,
}: {
    params: Promise<{ slug: string }>;
}) {
    const { slug } = await params;

    let product: ProductDetail;
    try {
        product = await fetchAPI<ProductDetail>(`/api/products/${slug}`);
    } catch {
        notFound();
    }

    const fm = product.frontmatter;
    const sections = Object.entries(product.sections);

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="text-xs text-text-dim font-mono mb-1">
                        wiki/products/{slug}.md
                    </div>
                    <h1 className="text-xl font-semibold">
                        {(fm.title as string) || slug}
                    </h1>
                </div>
                <div className="flex items-center gap-2 text-xs">
                    <span className="px-2 py-0.5 rounded border border-success/40 text-success font-mono">
                        {(fm.status as string) || "active"}
                    </span>
                    <span className="text-text-dim font-mono">
                        {fm.source_count as number || 0} sources
                    </span>
                </div>
            </div>

            {/* Frontmatter */}
            <div className="bg-surface border border-border rounded-lg p-5">
                <h2 className="text-sm font-semibold mb-3">Frontmatter</h2>
                <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                    {Object.entries(fm).map(([key, value]) => (
                        <div key={key} className="flex gap-2">
                            <span className="text-text-dim font-mono text-xs min-w-[160px]">
                                {key}:
                            </span>
                            <span className="text-xs font-mono truncate">
                                {Array.isArray(value)
                                    ? `[${value.join(", ")}]`
                                    : String(value)}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Sections */}
            <div className="space-y-4">
                <h2 className="text-sm font-semibold">
                    Sections（{sections.length}）
                </h2>
                {sections.map(([title, content]) => (
                    <SectionCard key={title} title={title} content={content} />
                ))}
            </div>
        </div>
    );
}

function SectionCard({ title, content }: { title: string; content: string }) {
    const isHumanOwned = [
        "五大賣點",
        "三大獨家 Demo",
        "常見客戶問題與回應",
        "常見反對意見處理",
    ].some((h) => title.includes(h));

    return (
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 bg-surface-2 border-b border-border flex items-center justify-between">
                <h3 className="text-sm font-medium font-mono">## {title}</h3>
                {isHumanOwned && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-warning/40 text-warning">
                        human-owned
                    </span>
                )}
            </div>
            <div className="p-4 text-sm text-text-dim leading-relaxed whitespace-pre-wrap font-mono text-xs max-h-64 overflow-y-auto">
                {content || "(empty)"}
            </div>
        </div>
    );
}
