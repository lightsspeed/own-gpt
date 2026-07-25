/* ------------------------------------------------------------------ */
/*  Icon tokens — sizing and stroke conventions                        */
/* ------------------------------------------------------------------ */

export const icons = {
  /* Default size for inline icons */
  size: {
    sm:  14,
    md:  16,
    lg:  18,
    xl:  24,
  } as const,

  /* Stroke width */
  stroke: 1.75,

  /* Lucide icon names used in the app (for reference) */
  catalog: {
    search:      'Search',
    send:        'Send',
    copy:        'Copy',
    check:       'Check',
    edit:        'Edit2',
    trash:       'Trash2',
    pin:         'Pin',
    plus:        'Plus',
    settings:    'Settings',
    close:       'X',
    menu:        'Menu',
    file:        'FileText',
    globe:       'Globe',
    book:        'BookOpen',
    lightbulb:   'Lightbulb',
    puzzle:      'Puzzle',
    sparkles:    'Sparkles',
    thumbsUp:    'ThumbsUp',
    thumbsDown:  'ThumbsDown',
    external:    'ExternalLink',
    download:    'FileDown',
    mic:         'Mic',
    image:       'ImagePlus',
    loader:      'Loader2',
    history:     'History',
  } as const,
} as const;
