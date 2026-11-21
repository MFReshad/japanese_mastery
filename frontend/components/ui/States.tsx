import type { ReactNode } from "react";

export function LoadingState({ label, className, children }: { label?: string; className: string; children?: ReactNode }) {
  return <div aria-label={label} className={className}>{children}</div>;
}

export function ErrorState({ children, className, action }: { children: ReactNode; className?: string; action?: ReactNode }) {
  return <p role="alert" className={className}>{children}{action}</p>;
}

export function EmptyState({ children, className }: { children: ReactNode; className: string }) {
  return <p className={className}>{children}</p>;
}
