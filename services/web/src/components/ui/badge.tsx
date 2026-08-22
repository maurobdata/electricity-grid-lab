import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Variant = "default" | "outline" | "warn" | "danger";

const VARIANTS: Record<Variant, string> = {
  default: "bg-muted text-muted-foreground border-transparent",
  outline: "border-border text-muted-foreground",
  warn: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  danger: "border-destructive/40 bg-destructive/10 text-destructive",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5",
        "text-[0.65rem] font-medium whitespace-nowrap",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
