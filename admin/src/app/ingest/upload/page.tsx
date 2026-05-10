"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function UploadPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [result, setResult] = useState<Record<string, string> | null>(null);
    const [fileName, setFileName] = useState("");

    async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault();
        setLoading(true);
        setError("");
        setResult(null);

        const form = new FormData(e.currentTarget);

        try {
            const res = await fetch(`${API_BASE}/api/ingest/upload`, {
                method: "POST",
                body: form,
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || "Upload failed");
            } else {
                setResult(data);
            }
        } catch (err) {
            setError("Network error");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="p-6 max-w-2xl">
            <h1 className="text-xl font-semibold mb-2">上傳文件</h1>
            <p className="text-sm text-text-dim mb-6">
                上傳 Markdown 或純文字檔案，作為 T1 admin-upload 來源進入 Ingest Pipeline。
                上傳後需跑 Gate 4 才會寫入 wiki。
            </p>

            {error && (
                <div className="mb-4 p-3 rounded border border-danger/40 bg-danger/10 text-danger text-sm">
                    {error}
                </div>
            )}

            {result && (
                <div className="mb-4 p-4 rounded border border-success/40 bg-success/10 text-sm space-y-2">
                    <div className="text-success font-semibold">✅ 上傳成功</div>
                    <div className="text-text-dim font-mono text-xs space-y-1">
                        <div>Path: {result.path}</div>
                        <div>Week: {result.week}</div>
                        <div>Hash: {result.content_hash}</div>
                    </div>
                    <div className="text-text-dim text-xs mt-2">
                        下一步：執行 <code className="bg-surface-2 px-1 rounded">python3 scripts/ingest_agent.py --gate4-only</code> 將內容寫入 wiki
                    </div>
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
                {/* File */}
                <div>
                    <label className="block text-[11px] uppercase tracking-wider text-text-dim mb-1.5">
                        檔案（.md / .txt）
                    </label>
                    <div className="relative">
                        <input
                            type="file"
                            name="file"
                            accept=".md,.txt,.markdown"
                            required
                            onChange={(e) => setFileName(e.target.files?.[0]?.name || "")}
                            className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text-primary file:mr-3 file:px-3 file:py-1 file:rounded file:border-0 file:bg-accent file:text-bg file:font-semibold file:text-xs file:cursor-pointer"
                        />
                    </div>
                    {fileName && (
                        <div className="text-xs text-text-dim mt-1 font-mono">{fileName}</div>
                    )}
                </div>

                {/* Title */}
                <div>
                    <label className="block text-[11px] uppercase tracking-wider text-text-dim mb-1.5">
                        文章標題
                    </label>
                    <input
                        name="title"
                        required
                        placeholder="如：iPhone 17 Pro 內部訓練資料"
                        className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text-primary placeholder:text-text-dim/50 focus:outline-none focus:border-accent"
                    />
                </div>

                {/* Related Products */}
                <div>
                    <label className="block text-[11px] uppercase tracking-wider text-text-dim mb-1.5">
                        相關產品（逗號分隔）
                    </label>
                    <input
                        name="related_products"
                        placeholder="iphone-17-pro, mac-mini"
                        className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text-primary placeholder:text-text-dim/50 focus:outline-none focus:border-accent font-mono text-xs"
                    />
                </div>

                {/* Notes */}
                <div>
                    <label className="block text-[11px] uppercase tracking-wider text-text-dim mb-1.5">
                        備註（選填）
                    </label>
                    <textarea
                        name="notes"
                        rows={3}
                        placeholder="來源說明、上傳原因..."
                        className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text-primary placeholder:text-text-dim/50 focus:outline-none focus:border-accent"
                    />
                </div>

                <div className="flex gap-3 pt-4">
                    <button
                        type="submit"
                        disabled={loading}
                        className="px-4 py-2 rounded-md bg-accent text-bg font-semibold text-sm disabled:opacity-50"
                    >
                        {loading ? "上傳中..." : "上傳檔案"}
                    </button>
                    <button
                        type="button"
                        onClick={() => router.back()}
                        className="px-4 py-2 rounded-md border border-border text-text-dim text-sm hover:bg-surface-2"
                    >
                        取消
                    </button>
                </div>
            </form>
        </div>
    );
}
