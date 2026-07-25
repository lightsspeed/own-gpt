/* ------------------------------------------------------------------ */
/*  Design system — barrel export                                      */
/*  Import from here: import { colors, spacing, ... } from '@/ds'    */
/* ------------------------------------------------------------------ */

export { colors }       from './colors';
export type { ColorKey } from './colors';

export { typography }           from './typography';
export type { TypeScaleName }   from './typography';

export { spacing, gap, padding } from './spacing';
export type { SpacingToken }     from './spacing';

export { radius, radiusClass }   from './radius';
export type { RadiusToken }      from './radius';

export { shadows, shadowClass }  from './shadows';
export type { ShadowToken }      from './shadows';

export { motion, animateClass }  from './motion';
export type { MotionDuration, MotionEasing } from './motion';

export { breakpoints, mediaMin, mediaMax } from './breakpoints';
export type { Breakpoint }                 from './breakpoints';

export { zIndex, zIndexClass } from './zIndex';
export type { ZIndexLayer }    from './zIndex';

export { icons } from './icons';

export { semantic, hsl, bg } from './semantic';
export type { SemanticColor } from './semantic';

export * as tw from './tailwind';

export {
  answerModes,
  pipelineStages,
  toolStatuses,
  retrievalMethods,
  evidenceFamily,
  answerModeText,
  answerModeBg,
} from './ai';
export type {
  AnswerMode,
  PipelineStage,
  ToolStatus,
  RetrievalMethod,
  EvidenceFamily,
} from './ai';
