import React, { useEffect, useRef, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  rehypeStreamdownAnimate,
  StreamdownAnimateOptions,
} from '@/lib/rehype-streamdown';
import { cn } from '@/lib/utils';

export interface StreamdownProps {
  children: string;
  animated?: boolean | StreamdownAnimateOptions;
  isAnimating?: boolean;
  onAnimationStart?: () => void;
  onAnimationEnd?: () => void;
  className?: string;
  components?: Record<string, any>;
}

/**
 * Streamdown — Smooth per-word markdown text animation for AI streaming responses.
 *
 * Uses a rehype HAST transformer to wrap words in <span data-sd-animate> with
 * CSS custom properties. React reconciliation ensures only newly mounted spans trigger
 * CSS @keyframes sd-blurIn.
 *
 * When isAnimating=false, animation plugin is excluded entirely from the rehype pipeline,
 * leaving zero DOM overhead on completed messages.
 */
export function Streamdown({
  children,
  animated = true,
  isAnimating = true,
  onAnimationStart,
  onAnimationEnd,
  className,
  components,
}: StreamdownProps) {
  const prevAnimatingRef = useRef(isAnimating);

  useEffect(() => {
    if (!prevAnimatingRef.current && isAnimating) {
      onAnimationStart?.();
    } else if (prevAnimatingRef.current && !isAnimating) {
      onAnimationEnd?.();
    }
    prevAnimatingRef.current = isAnimating;
  }, [isAnimating, onAnimationStart, onAnimationEnd]);

  const rehypePlugins = useMemo(() => {
    if (!isAnimating || !animated) return [];

    const animOptions: StreamdownAnimateOptions =
      typeof animated === 'object'
        ? animated
        : { animation: 'blurIn', duration: 220, easing: 'ease-out', sep: 'word' };

    return [[rehypeStreamdownAnimate, animOptions]];
  }, [isAnimating, animated]);

  return (
    <div className={cn('streamdown-container', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={rehypePlugins as any}
        components={components}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
