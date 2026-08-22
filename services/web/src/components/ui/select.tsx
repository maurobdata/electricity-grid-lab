import type { SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * A native `<select>`, styled.
 *
 * Not a Radix listbox: a native control is keyboard-accessible and screen-reader-correct
 * for free, works on touch, and costs no dependency. The moment a design needs something
 * a native select cannot express, this is the file to replace.
 */
export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-7 rounded-md border border-border bg-muted px-2 text-xs text-foreground",
        "focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        "disabled:opacity-40",
        className,
      )}
      {...props}
    />
  );
}
