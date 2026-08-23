import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';

export interface ResponseStreamProps {
  /** The full text to render. For streaming, update this prop as chunks arrive. */
  textStream: string;
  /** Animation mode: "blurIn" or "fade". Default: "blurIn" */
  mode?: 'blurIn' | 'fade';
  /** Duration (ms) for each word blur-in transition. Default: 750 */
  fadeDuration?: number;
  /** Pacing delay (ms) between each word reveal. Default: 50 */
  segmentDelay?: number;
  className?: string;
}

/**
 * ResponseStream — renders text with a steady, paced word-by-word reveal
 * and dramatic blurIn / fade animation.
 *
 * Ensures responses reveal slowly and steadily even when backend LLMs stream fast.
 */
export function ResponseStream({
  textStream,
  mode = 'blurIn',
  fadeDuration = 750,
  segmentDelay = 50,
  className,
}: ResponseStreamProps) {
  // Split input into word & whitespace segments
  const allSegments = useMemo(() => {
    if (!textStream) return [];
    return textStream.split(/(\s+)/);
  }, [textStream]);

  // Index of how many segments are currently visible to the user
  const [visibleCount, setVisibleCount] = useState(0);
  const targetCountRef = useRef(allSegments.length);
  targetCountRef.current = allSegments.length;

  // Pace the reveal smoothly word-by-word
  useEffect(() => {
    if (visibleCount >= allSegments.length) {
      setVisibleCount(allSegments.length);
      return;
    }

    const timer = setInterval(() => {
      setVisibleCount((prev) => {
        if (prev < targetCountRef.current) {
          // Advance by 1 segment per tick for steady pacing
          return prev + 1;
        }
        return prev;
      });
    }, segmentDelay);

    return () => clearInterval(timer);
  }, [allSegments.length, segmentDelay, visibleCount]);

  const visibleSegments = useMemo(
    () => allSegments.slice(0, visibleCount),
    [allSegments, visibleCount]
  );

  const durationSec = fadeDuration / 1000;

  return (
    <span className={cn('inline', className)}>
      {visibleSegments.map((segment, i) => {
        // Render whitespace without animation
        if (/^\s+$/.test(segment)) {
          return <span key={i}>{segment}</span>;
        }

        const isBlur = mode === 'blurIn';

        return (
          <motion.span
            key={i}
            initial={
              isBlur
                ? { opacity: 0, filter: 'blur(14px)', y: 6 }
                : { opacity: 0 }
            }
            animate={
              isBlur
                ? { opacity: 1, filter: 'blur(0px)', y: 0 }
                : { opacity: 1 }
            }
            transition={{
              duration: durationSec,
              ease: [0.16, 1, 0.3, 1], // Smooth cubic-bezier spring feel
            }}
            style={{ display: 'inline-block' }}
          >
            {segment}
          </motion.span>
        );
      })}
    </span>
  );
}
