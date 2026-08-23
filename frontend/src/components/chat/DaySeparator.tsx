import React from "react";
import { cn } from "@/lib/utils";

interface DaySeparatorProps {
  date: Date;
  className?: string;
}

/**
 * DaySeparator — renders a styled date line between chat messages
 * whenever the calendar day changes between consecutive messages.
 *
 * Inspired by @assistant-ui/elements-day-separator.
 */
export function DaySeparator({ date, className }: DaySeparatorProps) {
  const label = formatDateLabel(date);

  return (
    <div
      className={cn(
        "flex items-center gap-3 select-none my-4 px-1",
        className
      )}
      aria-label={`Messages from ${label}`}
    >
      <div className="flex-1 h-px bg-white/[0.06]" />
      <span className="text-[11px] font-medium text-white/30 tracking-wide px-1 whitespace-nowrap">
        {label}
      </span>
      <div className="flex-1 h-px bg-white/[0.06]" />
    </div>
  );
}

/** Returns a human-readable label for a date. */
function formatDateLabel(date: Date): string {
  const now = new Date();
  const today = startOfDay(now);
  const yesterday = startOfDay(new Date(now.getTime() - 864e5));
  const target = startOfDay(date);

  if (target.getTime() === today.getTime()) return "Today";
  if (target.getTime() === yesterday.getTime()) return "Yesterday";

  const diffDays = Math.floor(
    (today.getTime() - target.getTime()) / 864e5
  );
  if (diffDays < 7) {
    return date.toLocaleDateString([], { weekday: "long" }); // e.g. "Monday"
  }
  if (now.getFullYear() === date.getFullYear()) {
    return date.toLocaleDateString([], { month: "long", day: "numeric" });
  }
  return date.toLocaleDateString([], {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Returns true if two dates fall on different calendar days. */
export function isDifferentDay(a: Date | undefined, b: Date | undefined): boolean {
  if (!a || !b) return false;
  return (
    a.getFullYear() !== b.getFullYear() ||
    a.getMonth() !== b.getMonth() ||
    a.getDate() !== b.getDate()
  );
}
