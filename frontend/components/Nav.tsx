"use client";

import { BarChart3, BookOpen, Database, Home, Library, Play, BookText } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Home", icon: Home },
  { href: "/practice", label: "Practice", icon: Play },
  { href: "/library", label: "Library", icon: Library },
  { href: "/study", label: "Study", icon: BookText },
  { href: "/progress", label: "Progress", icon: BarChart3 },
  { href: "/manage", label: "Data", icon: Database },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 z-20 border-b border-stone-200 bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <BookOpen size={22} className="text-moss" />
          Japanese Mastery
        </Link>
        <div className="flex gap-1 overflow-x-auto">
          {links.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href} className={`flex min-h-10 items-center gap-2 rounded px-3 text-sm ${pathname === href || (["/study", "/manage"].includes(href) && pathname.startsWith(`${href}/`)) ? "bg-ink text-white" : "hover:bg-stone-100"}`}>
              <Icon size={17} />
              <span className="hidden sm:inline">{label}</span>
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}
