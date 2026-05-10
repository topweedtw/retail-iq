"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AddSourcePage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault();
        setLoading(true);
        setError("");
        setSuccess("");

        const form = new FormData(e.currentTarget);
        const body = {
            name: form.get("name") as string,
            display_name: form.get("display_name") as string,
            tier: form.get("tier") as string,
            base_url: form.get("base_url") as string,
            fetch_method: form.get("fetch_method") as string,
            rss_url: (form.get("rss_url") as string) || undefined,
            locale: (form.get("locale") as string) || "en-US",
            enabled: true,
            allow_url_patterns: (form.get("allow_url_patterns") as string)
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean),
            deny_url_patterns: (form.get("deny_url_patterns") as string)
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean),
            title_required_regex: (form.get("title_required_regex") as string) || undefined,
            title_blocklist_regex: (form.get("title_blocklist_regex") as string) || undefined,
        };

        try {
            const res = await fetch(`${API_BASE}/api/ingest/sources`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || "Failed to add source");
            } else {
                setSuccess(`✅ Source "${body.name}" added successfully`);
                setTimeout(() => router.push("/sources"), 1500);
            }
        } catch (err) {
            setError("Network error");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="p-6 max-w-2xl">
            <h1 className="text-xl font-semibold mb-6">新增資料來源</h1>

            {error && (
                <div className="mb-4 p-3 rounded border border-danger/40 bg-danger/10 text-danger text-sm">
                    {error}
                </div>
            )}
            {success && (
                <div className="mb-4 p-3 rounded border border-success/40 bg-success/10 text-success text-sm">
                    {success}
                </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
                <Field label="Source ID" name="name" placeholder="my-blog（英文 slug）" required />
                <Field label="顯示名稱" name="display_name" placeholder="My Blog" required />

                <div className="grid grid-cols-2 gap-4">
                    <SelectField
                        label="Tier"
                        name="tier"
                        options={["T1", "T2", "T2-filtered", "T3"]}
                        defaultValue="T2"
                    />
                    <SelectField
                        label="Fetch Method"
                        name="fetch_method"
                        options={["rss", "http", "manual"]}
                        defaultValue="rss"
                    />
                </div>

                <Field label="Base URL" name="base_url" placeholder="https://example.com/" required />
                <Field label="RSS URL" name="rss_url" placeholder="https://example.com/feed/（fetch_method=rss 時填）" />
                <Field label="Locale" name="locale" placeholder="en-US" defaultValue="en-US" />

                <TextareaField
                    label="Allow URL Patterns（每行一個 regex）"
                    name="allow_url_patterns"
                    placeholder={'^https://example\\.com/review/'}
                />
                <TextareaField
                    label="Deny URL Patterns（每行一個 regex）"
                    name="deny_url_patterns"
                    placeholder={'^https://example\\.com/rumors/'}
                />

                <Field
                    label="Title Required Regex"
                    name="title_required_regex"
                    placeholder="(?i)\b(apple|iphone)\b"
                />
                <Field
                    label="Title Blocklist Regex"
                    name="title_blocklist_regex"
                    placeholder="(?i)(leak|rumor)"
                />

                <div className="flex gap-3 pt-4">
                    <button
                        type="submit"
                        disabled={loading}
                        className="px-4 py-2 rounded-md bg-accent text-bg font-semibold text-sm disabled:opacity-50"
                    >
                        {loading ? "新增中..." : "新增來源"}
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

function Field({
    label,
    name,
    placeholder,
    required,
    defaultValue,
}: {
    label: string;
    name: string;
    placeholder?: string;
    required?: boolean;
    defaultValue?: string;
}) {
    return (
        <div>
            <label className="block text-[11px] uppercase tracking-wider text-text-dim mb-1.5">
                {label}
            </label>
            <input
                name={name}
                placeholder={placeholder}
                required={required}
                defaultValue={defaultValue}
                className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text-primary placeholder:text-text-dim/50 focus:outline-none focus:border-accent"
            />
        </div>
    );
}

function SelectField({
    label,
    name,
    options,
    defaultValue,
}: {
    label: string;
    name: string;
    options: string[];
    defaultValue?: string;
}) {
    return (
        <div>
            <label className="block text-[11px] uppercase tracking-wider text-text-dim mb-1.5">
                {label}
            </label>
            <select
                name={name}
                defaultValue={defaultValue}
                className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-accent"
            >
                {options.map((o) => (
                    <option key={o} value={o}>
                        {o}
                    </option>
                ))}
            </select>
        </div>
    );
}

function TextareaField({
    label,
    name,
    placeholder,
}: {
    label: string;
    name: string;
    placeholder?: string;
}) {
    return (
        <div>
            <label className="block text-[11px] uppercase tracking-wider text-text-dim mb-1.5">
                {label}
            </label>
            <textarea
                name={name}
                placeholder={placeholder}
                rows={3}
                className="w-full bg-surface-2 border border-border rounded-md px-3 py-2 text-sm text-text-primary placeholder:text-text-dim/50 focus:outline-none focus:border-accent font-mono text-xs"
                defaultValue=""
            />
        </div>
    );
}
