/**
 * API client — 打 FastAPI 後端
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchAPI<T>(path: string): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        cache: "no-store",
    });
    if (!res.ok) {
        throw new Error(`API error: ${res.status} ${res.statusText}`);
    }
    return res.json();
}

// Types
export interface Product {
    slug: string;
    title: string;
    status: string;
    product_category: string;
    last_updated: string;
    source_count: number;
}

export interface ProductsResponse {
    products: Product[];
    total: number;
}

export interface IngestStatus {
    total_articles: number;
    by_status: Record<string, number>;
    by_source: Record<string, number>;
    by_week: Record<string, number>;
}

export interface Source {
    name: string;
    tier: string;
    enabled: boolean;
    display_name: string;
    fetch_method: string;
}

export interface SourcesResponse {
    sources: Source[];
    total: number;
}

export interface ReviewStats {
    total_items: number;
    total_proposals: number;
    by_decision: Record<string, number>;
    decided_files: number;
}
