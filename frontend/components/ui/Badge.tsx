import type { ReactNode } from "react";

type BadgeTone = "neutral" | "green" | "amber" | "blue";

const toneClasses: Record<BadgeTone, string> = {
  neutral: "bg-stone-100 text-stone-700",
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-800",
  blue: "bg-sky-100 text-sky-800",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: BadgeTone }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${toneClasses[tone]}`}>
      {children}
    </span>
  );
}
