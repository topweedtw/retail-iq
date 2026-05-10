"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
    { label: "儀表板", href: "/", icon: "📊" },
    { label: "產品頁", href: "/products", icon: "📱" },
    { label: "Ingest Pipeline", href: "/ingest", icon: "📥" },
    { label: "上傳文件", href: "/ingest/upload", icon: "📤" },
    { label: "資料來源", href: "/sources", icon: "🌐" },
    { label: "新增來源", href: "/sources/add", icon: "➕" },
    { label: "Review Queue", href: "/review", icon: "⚠️" },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="w-56 border-r border-border bg-surface flex flex-col">
            {/* Logo */}
            <div className="px-4 py-4 border-b border-border">
                <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-400 to-purple-500" />
                    <span className="font-semibold text-sm">RetailIQ</span>
                    <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded border border-border text-text-dim">
                        Admin
                    </span>
                </div>
            </div>

            {/* Nav */}
            <nav className="flex-1 p-2 space-y-0.5">
                {NAV_ITEMS.map((item) => {
                    const active = pathname === item.href;
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${active
                                ? "bg-surface-2 text-accent"
                                : "text-text-dim hover:bg-surface-2 hover:text-text-primary"
                                }`}
                        >
                            <span>{item.icon}</span>
                            <span>{item.label}</span>
                        </Link>
                    );
                })}
            </nav>

            {/* Footer */}
            <div className="p-3 border-t border-border text-[11px] text-text-dim font-mono">
                <div>v0.1.0</div>
            </div>
        </aside>
    );
}
