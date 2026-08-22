"use client";

import React, { useMemo } from "react";
import { cn } from "@/lib/utils";

export type TextShimmerProps = {
  children: string;
  as?: React.ElementType;
  className?: string;
  duration?: number;
  spread?: number;
  shimmerColor?: string;
};

function TextShimmerComponent({
  children,
  as: Component = "span",
  className,
  duration = 2,
  spread = 2,
  shimmerColor,
}: TextShimmerProps) {
  const dynamicSpread = useMemo(() => {
    return children.length * spread;
  }, [children, spread]);

  return (
    <Component
      className={cn(
        "relative inline-block bg-clip-text text-transparent",
        className,
      )}
      style={{
        backgroundImage: `linear-gradient(90deg, transparent calc(50% - ${dynamicSpread}px), ${shimmerColor ?? "currentColor"}, transparent calc(50% + ${dynamicSpread}px)), linear-gradient(color-mix(in oklab, currentColor 55%, transparent), color-mix(in oklab, currentColor 55%, transparent))`,
        backgroundSize: "250% 100%",
        backgroundRepeat: "no-repeat",
        animation: `text-shimmer ${duration}s linear infinite`,
      } as React.CSSProperties}
    >
      {children}
    </Component>
  );
}

export const TextShimmer = React.memo(TextShimmerComponent);
