/* ------------------------------------------------------------------ */
/*  Motion tokens — timing, easing, and keyframe names                 */
/* ------------------------------------------------------------------ */

export const motion = {
  /* Duration (ms) */
  duration: {
    instant: 0,
    micro:   100,
    fast:    150,
    normal:  200,
    slow:    250,
    reveal:  300,
  } as const,

  /* Easing curves */
  easing: {
    default:  'cubic-bezier(0.4, 0, 0.2, 1)',
    in:       'cubic-bezier(0.4, 0, 1, 1)',
    out:      'cubic-bezier(0, 0, 0.2, 1)',
    'in-out': 'cubic-bezier(0.4, 0, 0.2, 1)',
    bounce:   'cubic-bezier(0.34, 1.56, 0.64, 1)',
  } as const,

  /* Keyframe animation names (defined in tailwind.config / index.css) */
  keyframes: {
    fadeIn:     'fade-in',
    fadeInUp:   'fade-in-up',
    slideDown:  'slide-down',
    scaleIn:    'scale-in',
    scalePulse: 'scale-pulse',
    shimmer:    'shimmer',
    cursorBlink:'cursor-blink',
  } as const,
} as const;

export type MotionDuration = keyof typeof motion.duration;
export type MotionEasing   = keyof typeof motion.easing;

export function animateClass(keyframe: keyof typeof motion.keyframes, duration: MotionDuration = 'normal'): string {
  const name = motion.keyframes[keyframe];
  const ms = motion.duration[duration];
  return `animate-${name} duration-${ms}`;
}
