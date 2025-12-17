"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  {
    title: "Getting started",
    items: [
      { name: "Introduction", href: "/" },
      { name: "Architecture", href: "/architecture" },
      { name: "Quick start", href: "/quickstart" },
    ],
  },
  {
    title: "Household",
    items: [
      { name: "Calculate", href: "/endpoints/household" },
      { name: "Impact comparison", href: "/endpoints/household-impact" },
    ],
  },
  {
    title: "Economic analysis",
    items: [
      { name: "Economic impact", href: "/endpoints/economic-impact" },
      { name: "Aggregates", href: "/endpoints/aggregates" },
      { name: "Change aggregates", href: "/endpoints/change-aggregates" },
    ],
  },
  {
    title: "Data",
    items: [
      { name: "Datasets", href: "/endpoints/datasets" },
      { name: "Policies", href: "/endpoints/policies" },
      { name: "Dynamics", href: "/endpoints/dynamics" },
      { name: "Simulations", href: "/endpoints/simulations" },
    ],
  },
  {
    title: "Metadata",
    items: [
      { name: "Tax benefit models", href: "/endpoints/tax-benefit-models" },
      { name: "Variables", href: "/endpoints/variables" },
      { name: "Parameters", href: "/endpoints/parameters" },
    ],
  },
  {
    title: "Reference",
    items: [
      { name: "Models", href: "/reference/models" },
      { name: "Status codes", href: "/reference/status-codes" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-64 bg-white border-r border-[var(--color-border)] overflow-y-auto">
      <div className="p-6 border-b border-[var(--color-border)]">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--color-pe-green)] flex items-center justify-center">
            <span className="text-white font-bold text-sm">PE</span>
          </div>
          <div>
            <div className="font-semibold text-[var(--color-text-primary)]">PolicyEngine</div>
            <div className="text-xs text-[var(--color-text-muted)]">API v2</div>
          </div>
        </Link>
      </div>

      <nav className="p-4">
        {navigation.map((section) => (
          <div key={section.title} className="mb-6">
            <h3 className="px-3 mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
              {section.title}
            </h3>
            <ul className="space-y-1">
              {section.items.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
                        isActive
                          ? "bg-[var(--color-pe-green)] text-white font-medium"
                          : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-sunken)] hover:text-[var(--color-text-primary)]"
                      }`}
                    >
                      {item.name}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}
