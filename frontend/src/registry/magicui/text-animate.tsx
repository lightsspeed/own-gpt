import React, { useMemo } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export type AnimationType =
  | "blurIn"
  | "fadeIn"
  | "scaleUp"
  | "slideUp"
  | "slideDown"
  | "blurInUp";

export type SegmentBy = "word" | "character" | "line" | "text";

export interface TextAnimateProps extends React.HTMLAttributes<HTMLElement> {
  children: string;
  animation?: AnimationType;
  by?: SegmentBy;
  as?: React.ElementType;
  delay?: number;
  duration?: number;
  segmentDelay?: number;
  className?: string;
  once?: boolean;
}

const animationVariants: Record<
  AnimationType,
  { initial: Record<string, any>; animate: Record<string, any> }
> = {
  blurIn: {
    initial: { opacity: 0, filter: "blur(14px)", y: 6 },
    animate: { opacity: 1, filter: "blur(0px)", y: 0 },
  },
  fadeIn: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
  },
  scaleUp: {
    initial: { opacity: 0, scale: 0.8 },
    animate: { opacity: 1, scale: 1 },
  },
  slideUp: {
    initial: { opacity: 0, y: 15 },
    animate: { opacity: 1, y: 0 },
  },
  slideDown: {
    initial: { opacity: 0, y: -15 },
    animate: { opacity: 1, y: 0 },
  },
  blurInUp: {
    initial: { opacity: 0, filter: "blur(8px)", y: 10 },
    animate: { opacity: 1, filter: "blur(0px)", y: 0 },
  },
};

export function TextAnimate({
  children,
  animation = "blurIn",
  by = "word",
  as: Component = "span",
  delay = 0,
  duration = 0.4,
  segmentDelay = 0.03,
  className,
  once: _once = true,
  ...props
}: TextAnimateProps) {
  const variant = animationVariants[animation] || animationVariants.blurIn;

  const segments = useMemo(() => {
    if (typeof children !== "string") return [children];
    if (by === "character") {
      return children.split("");
    }
    if (by === "line") {
      return children.split("\n");
    }
    if (by === "word") {
      return children.split(/(\s+)/);
    }
    return [children];
  }, [children, by]);

  const MotionComponent = useMemo(
    () => motion.create(Component as keyof JSX.IntrinsicElements),
    [Component]
  );

  if (by === "text" || typeof children !== "string") {
    return (
      <MotionComponent
        initial={variant.initial}
        animate={variant.animate}
        transition={{
          duration,
          delay,
          ease: "easeOut",
        }}
        className={cn("inline-block", className)}
        {...props}
      >
        {children}
      </MotionComponent>
    );
  }

  return (
    <Component className={cn("inline", className)} {...props}>
      {segments.map((segment, i) => {
        if (/^\s+$/.test(segment)) {
          return <span key={i}>{segment}</span>;
        }

        return (
          <motion.span
            key={i}
            initial={variant.initial}
            animate={variant.animate}
            transition={{
              duration,
              delay: delay + (i / 2) * segmentDelay,
              ease: "easeOut",
            }}
            style={{ display: "inline-block" }}
          >
            {segment}
          </motion.span>
        );
      })}
    </Component>
  );
}
