import Link from "next/link";
import type { ReactNode } from "react";

export function ManageHeader({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return (
    <header className="mb-8">
      <nav aria-label="Breadcrumb" className="mb-3 flex items-center gap-2 text-sm text-stone-500">
        <Link className="hover:text-moss" href="/manage">Data Management</Link>
        <span>/</span>
        <span className="text-ink">{title}</span>
      </nav>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-2 max-w-2xl text-stone-600">{description}</p>
        </div>
        {children}
      </div>
    </header>
  );
}
