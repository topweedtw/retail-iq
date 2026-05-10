import Link from "next/link";
import { fetchAPI, ProductsResponse } from "@/lib/api";

export default async function ProductsPage() {
    const data = await fetchAPI<ProductsResponse>("/api/products");

    return (
        <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-xl font-semibold">產品頁（{data.total}）</h1>
            </div>

            <div className="bg-surface border border-border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="bg-surface-2">
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-3">
                                Product
                            </th>
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-3">
                                Category
                            </th>
                            <th className="text-left text-[11px] uppercase tracking-wider text-text-dim px-4 py-3">
                                Status
                            </th>
                            <th className="text-right text-[11px] uppercase tracking-wider text-text-dim px-4 py-3">
                                Sources
                            </th>
                            <th className="text-right text-[11px] uppercase tracking-wider text-text-dim px-4 py-3">
                                Updated
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.products.map((p) => (
                            <tr
                                key={p.slug}
                                className="border-t border-border hover:bg-surface-2 transition-colors"
                            >
                                <td className="px-4 py-3">
                                    <Link
                                        href={`/products/${p.slug}`}
                                        className="text-accent hover:underline font-medium"
                                    >
                                        {p.title}
                                    </Link>
                                </td>
                                <td className="px-4 py-3 text-text-dim">{p.product_category}</td>
                                <td className="px-4 py-3">
                                    <span className="inline-block px-2 py-0.5 rounded text-[11px] font-mono border border-success/40 text-success">
                                        {p.status}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-right font-mono">{p.source_count}</td>
                                <td className="px-4 py-3 text-right text-text-dim font-mono text-xs">
                                    {p.last_updated}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
