"use client";

import { X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef } from "react";

export function Modal({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const titleId = useId();
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef(close);
  const previouslyFocusedRef = useRef<HTMLElement | null>(
    typeof document !== "undefined" && document.activeElement instanceof HTMLElement ? document.activeElement : null,
  );
  closeRef.current = close;

  useEffect(() => {
    const dialog = dialogRef.current;
    const focusableSelector =
      "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])";
    const focusTarget = dialog?.querySelector<HTMLElement>("input:not([disabled]), select:not([disabled]), textarea:not([disabled])")
      ?? dialog?.querySelector<HTMLElement>(focusableSelector);
    focusTarget?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeRef.current();
      if (event.key !== "Tab" || !dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector));
      const first = focusable[0];
      const last = focusable.at(-1);
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocusedRef.current?.focus();
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(event) => event.target === event.currentTarget && close()}
    >
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-7"
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 id={titleId} className="text-xl font-semibold">{title}</h2>
          <button type="button" aria-label="Close" onClick={close} className="rounded-lg p-2 hover:bg-stone-100">
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
